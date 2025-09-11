# carrito.py
from kivy.metrics import dp
from kivy.app import App
from kivy.uix.screenmanager import Screen, NoTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.textinput import TextInput
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
import sqlite3, os, json, time, re, random

print("[CART] Cargando módulo desde:", __file__)

# ---- UI / Constantes ----
ROW_MIN_H = dp(48)
BTN_W     = dp(44)
IVA       = 0.19

# ---- BD ----
def _db_path():
    base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "bd_sqlite", "todoferre.db")

def _ensure_tables():
    con = sqlite3.connect(_db_path()); cur = con.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS order_drafts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user TEXT NOT NULL,
        cliente_rowid INTEGER NOT NULL,
        payload_json TEXT NOT NULL,
        updated_at INTEGER NOT NULL,
        UNIQUE(user, cliente_rowid)
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_no TEXT NOT NULL,
        user TEXT NOT NULL,
        cliente_rowid INTEGER NOT NULL,
        cliente_display TEXT NOT NULL,
        mode TEXT NOT NULL,          -- retiro|despacho
        region TEXT NOT NULL,
        subtotal INTEGER NOT NULL,
        iva INTEGER NOT NULL,
        total INTEGER NOT NULL,
        created_at INTEGER NOT NULL,
        -- columnas nuevas (snapshot del cliente y ejecutor)
        cliente_rut TEXT,
        cliente_direccion TEXT,
        cliente_comuna TEXT,
        cliente_ciudad TEXT,
        cliente_estado TEXT,
        cliente_email TEXT,
        forma_pago TEXT,
        direccion_despacho TEXT,
        realizado_por_usuario TEXT,
        realizado_por_nombre TEXT
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        sku TEXT NOT NULL,
        product TEXT NOT NULL,
        unit_price INTEGER NOT NULL,
        qty INTEGER NOT NULL,
        total INTEGER NOT NULL,
        FOREIGN KEY(order_id) REFERENCES orders(id)
    )
    """)
    # detalle adicional para PDF / sincronización
    cur.execute("""
    CREATE TABLE IF NOT EXISTS detalle_productos_orden (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      order_no TEXT NOT NULL,
      region TEXT,
      sku TEXT NOT NULL,
      product TEXT NOT NULL,
      marca TEXT,
      categoria TEXT,
      unit_price INTEGER NOT NULL,
      qty INTEGER NOT NULL,
      total INTEGER NOT NULL
    )
    """)
    con.commit(); con.close()

def _price_to_int(v):
    if v is None: return 0
    if isinstance(v, (int, float)): return int(v)
    s = re.sub(r"[^\d]", "", str(v))
    return int(s or 0)

class CartScreen(Screen):
    # ---------- Helpers de UI ----------
    def _wrap_button(self, text, on_release):
        btn = Button(text=text, size_hint_y=None, height=ROW_MIN_H, halign="left", valign="middle")
        btn.text_size = (0, None)
        btn.bind(size=lambda inst, *_: setattr(inst, "text_size", (inst.width - dp(16), None)))
        btn.bind(texture_size=lambda inst, *_: setattr(inst, "height", max(ROW_MIN_H, inst.texture_size[1] + dp(12))))
        btn.bind(on_release=on_release)
        return btn

    def _wrap_label(self, text):
        lbl = Label(text=text, size_hint_y=None, halign="left", valign="middle")
        lbl.text_size = (0, None)
        lbl.bind(size=lambda inst, *_: setattr(inst, "text_size", (inst.width - dp(8), None)))
        lbl.bind(texture_size=lambda inst, *_: setattr(inst, "height", max(ROW_MIN_H, inst.texture_size[1] + dp(8))))
        return lbl

    # ---------- Ciclo ----------
    def on_pre_enter(self, *args):
        _ensure_tables()
        self.app = App.get_running_app()
        self.user = getattr(self.app, "current_user", "usuario")

        ctx = getattr(self.app, "order_ctx", {}) or {}
        self.ctx = ctx
        self.region          = ctx.get("region")
        self.mode            = ctx.get("mode")
        self.cliente_rowid   = ctx.get("cliente_rowid")
        self.cliente_display = ctx.get("cliente_display", "Cliente")

        # snapshot del cliente (vienen desde resumen_cliente.py)
        self.snap_cliente_rut       = ctx.get("cliente_rut")
        self.snap_cliente_dir       = ctx.get("cliente_direccion")
        self.snap_cliente_comuna    = ctx.get("cliente_comuna")
        self.snap_cliente_ciudad    = ctx.get("cliente_ciudad")
        self.snap_cliente_estado    = ctx.get("cliente_estado")
        self.snap_cliente_email     = ctx.get("cliente_email")
        self.snap_forma_pago        = ctx.get("forma_pago")
        self.snap_dir_despacho      = ctx.get("direccion_despacho")

        self.cart = []
        self._build_ui()

        if ctx.get("from_draft"):
            self._load_draft()

        self._refresh_totals()

    def _go_back(self, *_):
        if self.manager:
            self.manager.transition = NoTransition()
            self.manager.current = "resumen_cliente"

    def _build_ui(self):
        self.clear_widgets()
        root = BoxLayout(orientation="vertical", padding=10, spacing=8)

        root.add_widget(Label(text=f"[b]Precios para región:[/b] {self.region}", markup=True, size_hint=(1,None), height=24))
        root.add_widget(Label(text=f"[b]Cliente:[/b] {self.cliente_display}",   markup=True, size_hint=(1,None), height=24))

        self.q = TextInput(hint_text="Buscar producto (SKU o descripción)…", size_hint=(1,None), height=44)
        self.q.bind(text=lambda *_: self._suggest(self.q.text))
        root.add_widget(self.q)

        self.suggestions = GridLayout(cols=1, size_hint_y=None, spacing=6, padding=(0,6))
        self.suggestions.bind(minimum_height=self.suggestions.setter("height"))
        ssv = ScrollView(size_hint=(1, 0.38)); ssv.add_widget(self.suggestions)
        root.add_widget(ssv)

        self.cart_box = GridLayout(cols=1, size_hint_y=None, spacing=6, padding=(0,6))
        self.cart_box.bind(minimum_height=self.cart_box.setter("height"))
        csv = ScrollView(size_hint=(1, 0.34)); csv.add_widget(self.cart_box)
        root.add_widget(csv)

        self.lbl_sub = Label(text="Subtotal: $0", size_hint=(1,None), height=24)
        self.lbl_iva = Label(text="IVA (19%): $0", size_hint=(1,None), height=24)
        self.lbl_tot = Label(text="[b]Total:[/b] $0", markup=True, size_hint=(1,None), height=30)
        root.add_widget(self.lbl_sub); root.add_widget(self.lbl_iva); root.add_widget(self.lbl_tot)

        btns = BoxLayout(size_hint=(1,None), height=50, spacing=8)
        back = Button(text="< Volver", on_release=self._go_back)
        nextb= Button(text="Finalizar Órden", on_release=lambda *_: self._finalize_order())
        btns.add_widget(back); btns.add_widget(nextb)
        root.add_widget(btns)

        self.add_widget(root)

    # ---------- Sugerencias ----------
    def _suggest(self, term):
        self.suggestions.clear_widgets()
        t = (term or "").strip()
        if len(t) < 2: return

        con = sqlite3.connect(_db_path()); cur = con.cursor()
        like = f"%{t}%"
        cur.execute("""
            SELECT sku, reglas_de_lista_de_precios_producto, reglas_de_lista_de_precios_precio_fijo
            FROM pricelist
            WHERE region = ?
              AND (sku LIKE ? OR reglas_de_lista_de_precios_producto LIKE ?)
            ORDER BY sku LIMIT 50
        """, (self.region, like, like))
        rows = cur.fetchall(); con.close()

        for sku, nombre, precio in rows:
            p = _price_to_int(precio)
            text = f"[b]{sku}[/b]\n{(nombre or '').strip()}   •   ${p:,}".replace(",", ".")
            btn = self._wrap_button(text, on_release=lambda b, s=sku, n=nombre, pr=p: self._pick_product(s, n, pr))
            btn.markup = True
            self.suggestions.add_widget(btn)

    def _pick_product(self, sku, nombre, unit_price):
        self._add_to_cart(sku, nombre, unit_price, qty=1)

    # ---------- Carrito ----------
    def _add_to_cart(self, sku, nombre, unit_price, qty=1):
        for it in self.cart:
            if it["sku"] == sku:
                it["qty"] += int(qty)
                break
        else:
            self.cart.append({
                "sku": sku,
                "name": (nombre or "").strip(),
                "unit_price": int(unit_price),
                "qty": int(qty),
            })
        self._render_cart()
        self._persist_draft()

    def _render_cart(self):
        self.cart_box.clear_widgets()
        for idx, it in enumerate(self.cart):
            row = BoxLayout(size_hint=(1,None), height=ROW_MIN_H + dp(12), spacing=8)

            txt = (f"[b]{it['sku']}[/b]  {it['name']}\n"
                   f"${it['unit_price']:,}  ×{it['qty']}  =  [b]${(it['unit_price']*it['qty']):,}[/b]").replace(",", ".")
            lbl = self._wrap_label(txt); lbl.markup = True
            row.add_widget(lbl)

            menos = Button(text="–", size_hint=(None,None), width=BTN_W, height=BTN_W)
            mas   = Button(text="+", size_hint=(None,None), width=BTN_W, height=BTN_W)
            bor   = Button(text="X", size_hint=(None,None), width=BTN_W, height=BTN_W)
            menos.bind(on_release=lambda *_ , i=idx: self._chg_qty(i, -1))
            mas.bind(  on_release=lambda *_ , i=idx: self._chg_qty(i, +1))
            bor.bind(  on_release=lambda *_ , i=idx: self._del_item(i))
            row.add_widget(menos); row.add_widget(mas); row.add_widget(bor)

            def _sync_height(*_):
                row.height = max(ROW_MIN_H + dp(12), lbl.height + dp(12))
            lbl.bind(height=lambda *_: _sync_height()); _sync_height()

            self.cart_box.add_widget(row)
        self._refresh_totals()

    def _chg_qty(self, idx, delta):
        if 0 <= idx < len(self.cart):
            self.cart[idx]["qty"] = max(1, self.cart[idx]["qty"] + delta)
            self._render_cart(); self._persist_draft()

    def _del_item(self, idx):
        if 0 <= idx < len(self.cart):
            self.cart.pop(idx); self._render_cart(); self._persist_draft()

    def _refresh_totals(self):
        sub = sum(it["unit_price"] * it["qty"] for it in self.cart)
        iva = int(round(sub * IVA)); tot = sub + iva
        self.lbl_sub.text = f"Subtotal: ${sub:,}".replace(",", ".")
        self.lbl_iva.text = f"IVA (19%): ${iva:,}".replace(",", ".")
        self.lbl_tot.text = f"[b]Total:[/b] ${tot:,}".replace(",", ".")

    # ---------- Borradores ----------
    def _persist_draft(self):
        payload = {
            "mode": self.mode, "region": self.region,
            "cliente_rowid": self.cliente_rowid, "cliente_display": self.cliente_display,
            "cart": self.cart,
        }
        _ensure_tables()
        con = sqlite3.connect(_db_path()); cur = con.cursor()
        cur.execute("""
            INSERT INTO order_drafts(user, cliente_rowid, payload_json, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user, cliente_rowid)
            DO UPDATE SET payload_json=excluded.payload_json, updated_at=excluded.updated_at
        """, (self.user, int(self.cliente_rowid or 0), json.dumps(payload), int(time.time())))
        con.commit(); con.close()

    def _load_draft(self):
        con = sqlite3.connect(_db_path()); cur = con.cursor()
        cur.execute("SELECT payload_json FROM order_drafts WHERE user=? AND cliente_rowid=?",
                    (self.user, int(self.cliente_rowid or 0)))
        row = cur.fetchone(); con.close()
        if not row: return
        data = json.loads(row[0])
        self.mode            = data.get("mode")   or self.mode
        self.region          = data.get("region") or self.region
        self.cart            = data.get("cart")   or []
        self.cliente_display = data.get("cliente_display") or self.cliente_display
        self._build_ui(); self._render_cart()

    # ---------- Finalizar ----------
    def _finalize_order(self):
        if not self.cart:
            return

        order_no = f"{self.user}{random.randint(10000, 99999)}"
        sub = sum(it["unit_price"] * it["qty"] for it in self.cart)
        iva = int(round(sub * IVA)); tot = sub + iva

        _ensure_tables()
        con = sqlite3.connect(_db_path()); cur = con.cursor()

        # nombre real del usuario (para "Realizado por")
        cur.execute("SELECT nombre_real FROM usuarios WHERE username_ferro=? LIMIT 1", (self.user,))
        row_user = cur.fetchone()
        realizado_por_nombre = (row_user[0] if row_user and row_user[0] not in (None, "") else self.user)

        # INSERT dinámico a prueba de conteo
        cols = [
            "order_no","user","cliente_rowid","cliente_display","mode","region",
            "subtotal","iva","total","created_at",
            "cliente_rut","cliente_direccion","cliente_comuna","cliente_ciudad",
            "cliente_estado","cliente_email","forma_pago","direccion_despacho",
            "realizado_por_usuario","realizado_por_nombre",
        ]
        params = [
            order_no, self.user, int(self.cliente_rowid or 0), self.cliente_display, self.mode, self.region,
            sub, iva, tot, int(time.time()),
            self.snap_cliente_rut, self.snap_cliente_dir, self.snap_cliente_comuna, self.snap_cliente_ciudad,
            self.snap_cliente_estado, self.snap_cliente_email, self.snap_forma_pago, self.snap_dir_despacho,
            self.user, realizado_por_nombre,
        ]
        ph = ",".join(["?"] * len(cols))
        sql = f"INSERT INTO orders({','.join(cols)}) VALUES({ph})"
        print("[CART][DEBUG] placeholders:", sql.count("?"), "values:", len(params))
        cur.execute(sql, params)
        order_id = cur.lastrowid

        # Detalle por línea (compatibilidad + tabla para PDF)
        for it in self.cart:
            cur.execute("""
                INSERT INTO order_items(order_id, sku, product, unit_price, qty, total)
                VALUES(?,?,?,?,?,?)
            """, (order_id, it["sku"], it["name"], it["unit_price"], it["qty"], it["unit_price"] * it["qty"]))

            cur.execute("SELECT marca, categoria_de_producto FROM productos WHERE sku=? LIMIT 1", (it["sku"],))
            row_prod = cur.fetchone()
            marca = row_prod[0] if row_prod and row_prod[0] not in (None, "") else None
            categoria = row_prod[1] if row_prod and row_prod[1] not in (None, "") else None

            cur.execute("""
                INSERT INTO detalle_productos_orden(
                    order_no, region, sku, product, marca, categoria, unit_price, qty, total
                ) VALUES(?,?,?,?,?,?,?,?,?)
            """, (order_no, self.region, it["sku"], it["name"], marca, categoria,
                  int(it["unit_price"]), int(it["qty"]), int(it["unit_price"] * it["qty"])))

        # limpiar completamente el borrador de ordenes y volver
        cur.execute("DELETE FROM order_drafts WHERE user=?", (self.user,))
        con.commit(); con.close()

        if self.manager:
            self.manager.transition = NoTransition()
            self.manager.current = "tomar_pedido"
