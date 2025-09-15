# tomar_pedido.py
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from kivy.app import App
from kivy.metrics import dp
from kivy.properties import StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.screenmanager import NoTransition, Screen
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput

print("[TP] Cargando módulo desde:", __file__)

# Ruta de la base de datos
DB_PATH = Path("bd_sqlite/todoferre.db").expanduser().resolve()


# --------------------------- BÚSQUEDA EN SQLITE ---------------------------

def search_clients(term: str, limit: int = 30) -> List[Dict[str, Any]]:
    """
    Busca en la tabla 'clientes' por nombre_fantasia / nombre_completo / RUT.
    Devuelve dicts con claves:
      display, nombre_fantasia, nombre_completo, comuna, ciudad, email,
      numero_identificacion_fiscal, cliente_id (rowid)
    Es tolerante a columnas faltantes (devuelve '' cuando no existen).
    """
    if not DB_PATH.exists():
        print("[SEARCH_CLIENTS] DB no existe:", DB_PATH)
        return []

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()

        # Descubrir columnas reales
        cur.execute("PRAGMA table_info(clientes)")
        cols = {row["name"] for row in cur.fetchall()}

        want = [
            "nombre_fantasia", "nombre_completo", "comuna",
            "ciudad", "email", "numero_identificacion_fiscal"
        ]

        # SELECT seguro con alias si falta columna
        select_parts = []
        for c in want:
            if c == "email":
                if "correo_electronico" in cols:
                    select_parts.append("correo_electronico AS email")
                elif "email" in cols:
                    select_parts.append("email")
                else:
                    select_parts.append("'' AS email")
            else:
                select_parts.append(c if c in cols else f"'' AS {c}")
        select_clause = ", ".join(select_parts)

        # Preferencia para 'display'
        if "nombre_fantasia" in cols and "nombre_completo" in cols:
            display_expr = "COALESCE(NULLIF(TRIM(nombre_fantasia),''), nombre_completo)"
        elif "nombre_fantasia" in cols:
            display_expr = "nombre_fantasia"
        elif "nombre_completo" in cols:
            display_expr = "nombre_completo"
        else:
            return []

        like = f"%{(term or '').strip()}%"
        where_terms, params = [], []
        if "nombre_fantasia" in cols:
            where_terms.append("nombre_fantasia LIKE ? COLLATE NOCASE")
            params.append(like)
        if "nombre_completo" in cols:
            where_terms.append("nombre_completo LIKE ? COLLATE NOCASE")
            params.append(like)
        if "numero_identificacion_fiscal" in cols:
            where_terms.append("numero_identificacion_fiscal LIKE ? COLLATE NOCASE")
            params.append(like)

        if not where_terms:
            return []

        sql = f"""
        SELECT
            {display_expr} AS display,
            {select_clause},
            rowid AS cliente_id
        FROM clientes
        WHERE {' OR '.join(where_terms)}
        ORDER BY display
        LIMIT ?
        """
        params.append(limit)

        cur.execute(sql, params)
        rows = cur.fetchall()

        results: List[Dict[str, Any]] = []
        for r in rows:
            results.append({
                "display": r["display"] or "",
                "nombre_fantasia": r["nombre_fantasia"] or "",
                "nombre_completo": r["nombre_completo"] or "",
                "comuna": r["comuna"] or "",
                "ciudad": r["ciudad"] or "",
                "email": r["email"] or "",
                "cliente_id": r["cliente_id"],
                "numero_identificacion_fiscal": r["numero_identificacion_fiscal"] or "",
            })
        print(f"[SUGGEST] {len(results)} resultados para '{term}'")
        return results

    except Exception as e:
        print("[SEARCH_CLIENTS][ERROR]", e)
        return []
    finally:
        conn.close()


# ------------------------------ PANTALLA -----------------------------------

class TakeOrderScreen(Screen):
    current_user = StringProperty("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.selected_client: Optional[Dict[str, Any]] = None
        self._last_items: List[Dict[str, Any]] = []

        # cache para 'retomar'
        self._resume_cliente_rowid: Optional[int] = None
        self._resume_payload_json: Optional[str] = None

        root = BoxLayout(orientation="vertical", padding=24, spacing=16)

        # Título + saludo
        title = Label(text="Tomar Pedido", font_size=24, size_hint=(1, 0.10), color=(1, 1, 1, 1))
        self.hello = Label(text="¡Hola!", font_size=18, size_hint=(1, 0.08), color=(1, 1, 1, 1))
        self.client_lbl = Label(text="Cliente: —", size_hint=(1, 0.06), color=(1, 1, 1, 1))

        # Campo de búsqueda
        self.search_inp = TextInput(
            hint_text="Buscar cliente por Nombre o RUT...",
            multiline=False,
            size_hint=(1, 0.10),
            foreground_color=(0, 0, 0, 1),
            hint_text_color=(0.8, 0.8, 0.8, 1),
            cursor_color=(1, 1, 1, 1),
        )
        self.search_inp.bind(text=self._on_search_text)

        # Lista de resultados
        self.sv = ScrollView(size_hint=(1, None), height=dp(360), do_scroll_x=False, do_scroll_y=True)
        self.grid = GridLayout(cols=1, size_hint_y=None, spacing=dp(6), padding=[0, 0, 0, dp(6)])
        self.grid.bind(minimum_height=self.grid.setter("height"))
        self.sv.add_widget(self.grid)

        # --- Botón "Retomar orden" (KISS). Visible solo si hay borrador para el usuario ---
        self.resume_btn = Button(text="Retomar orden", size_hint=(1, None), height=0, disabled=True)
        self.resume_btn.bind(on_release=self._resume_order)

        # Botones inferiores
        btns = BoxLayout(orientation="horizontal", spacing=12, size_hint=(1, 0.14))
        logout_btn = Button(text="Cerrar sesión")
        logout_btn.bind(on_release=self._logout)
        hist_btn = Button(text="Historial", size_hint=(1, None), height=46)
        hist_btn.bind(on_release=lambda *_: setattr(self.manager, "current", "historial"))
        self.next_btn = Button(text="Siguiente >", disabled=True)
        self.next_btn.bind(on_release=self._next)
        btns.add_widget(logout_btn)
        btns.add_widget(hist_btn)
        btns.add_widget(self.next_btn)

        # Ensamblar (orden correcto)
        root.add_widget(title)
        root.add_widget(self.hello)
        root.add_widget(self.client_lbl)
        root.add_widget(self.search_inp)
        root.add_widget(self.sv)
        root.add_widget(self.resume_btn)  # entre la lista y los botones
        root.add_widget(btns)
        self.add_widget(root)

    # ---- API usada por login.py ----
    def set_user(self, username: str):
        self.current_user = username
        self.hello.text = f"¡Hola, {username}!"
        # Refresca visibilidad del botón 'Retomar'
        self._update_resume_button()

    def on_pre_enter(self, *args):
        # Al entrar a la pantalla, refrescamos por si cambió la tabla
        self._update_resume_button()

    # ---- Callbacks de UI ----
    def _on_search_text(self, *_):
        term = self.search_inp.text
        if len((term or "").strip()) < 2:
            self._populate_list([])
            return
        items = search_clients(term, limit=30)
        self._populate_list(items)

    def _populate_list(self, items: List[Dict[str, Any]]):
        self._last_items = items[:]
        self.grid.clear_widgets()

        if not items:
            lbl = Label(text="Sin resultados", size_hint_y=None, height=dp(40), color=(1, 1, 1, 0.7))
            self.grid.add_widget(lbl)
            return

        for it in items:
            btn = Button(
                text=f"{it['display']}\n{it['numero_identificacion_fiscal']}",
                size_hint_y=None,
                height=dp(48),
                background_normal="",
                background_color=(0.25, 0.25, 0.25, 1),
                color=(1, 1, 1, 1),
                halign="left",
                valign="middle",
            )
            btn.text_size = (0, None)
            btn.bind(size=lambda b, *_: setattr(b, "text_size", (b.width - dp(20), None)))

            def _make_on_release(item: Dict[str, Any]):
                def _handler(*_a):
                    self.on_pick(item)
                return _handler

            btn.bind(on_release=_make_on_release(it))
            self.grid.add_widget(btn)

        print("[UI] items mostrados:", len(items))

    def on_pick(self, item: Dict[str, Any]):
        """Cuando se toca un resultado."""
        self.selected_client = item
        self.client_lbl.text = f"Cliente: {item['display']}"
        self.next_btn.disabled = False
        print("[PICK]", item.get("display"), " -> ", item)

    def _logout(self, *_):
        if self.manager:
            self.manager.transition = NoTransition()
            self.manager.current = "login"

    def _next(self, *_):
        # Debe existir un cliente elegido
        if not getattr(self, "selected_client", None):
            return

        # Pasar el cliente seleccionado a la pantalla de resumen
        summary = self.manager.get_screen("resumen_cliente")
        summary.set_client(self.selected_client)   # método existente

        # Navegar al resumen
        self.manager.current = "resumen_cliente"

    # ---------------------- NUEVO: Retomar orden ----------------------
    # ---- Si la APP, se cerró repentinamente mientras se estaba incluyendo productos en la orden (código carrito.py) ----------------------
    # ---- La app busca en la tabla order_drafts si hay algún registro que recuperar, de ser así, se habilita el botón ----------------------
    # ---- Retomar Orden, y al hacer click en el, la APP, te lleva directamente al carrito.py para continuar de llenar esa orden pendiente ----------------------
    # ---- Cuando se completa la orden en carrito.py, (se presiona el botón de completar orden), se borran todos los registros de la tabla order_drafts


    def _update_resume_button(self):
        """Muestra/oculta el botón 'Retomar orden' si existe borrador (order_drafts) para el usuario."""
        if not self.current_user:
            self._resume_cliente_rowid = None
            self._resume_payload_json = None
            self.resume_btn.disabled = True
            self.resume_btn.height = 0
            return

        con = sqlite3.connect(DB_PATH)
        try:
            cur = con.cursor()
            cur.execute("""
                SELECT cliente_rowid, payload_json
                FROM order_drafts
                WHERE user=?
                ORDER BY id DESC
                LIMIT 1
            """, (self.current_user,))
            row = cur.fetchone()
        finally:
            con.close()

        if row:
            self._resume_cliente_rowid = int(row[0] or 0)
            self._resume_payload_json = row[1]
            self.resume_btn.disabled = False
            self.resume_btn.height = dp(44)   # visible
        else:
            self._resume_cliente_rowid = None
            self._resume_payload_json = None
            self.resume_btn.disabled = True
            self.resume_btn.height = 0        # oculto

    def _resume_order(self, *_):
        """Carga el contexto desde el borrador y navega a carrito (from_draft=True)."""
        if not self._resume_payload_json:
            return

        try:
            data = json.loads(self._resume_payload_json)  # {'mode','region','cliente_rowid','cliente_display',...}
        except Exception:
            # Si el JSON está corrupto, no intentamos retomar
            return

        app = App.get_running_app()
        app.order_ctx = {
            "mode": data.get("mode"),
            "region": data.get("region"),
            "cliente_rowid": data.get("cliente_rowid"),
            "cliente_display": data.get("cliente_display"),
            "from_draft": True,
        }

        # Ir directo al carrito si existe una orden pendiente en la tabla order_drafts en la base de datos todoferretero.db
        if self.manager:
            self.manager.transition = NoTransition()
            self.manager.current = "carrito"
