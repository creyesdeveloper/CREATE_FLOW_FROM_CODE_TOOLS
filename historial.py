# historial.py
from kivy.app import App
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.metrics import dp
from kivy.utils import platform

import sqlite3, os, time, sys, webbrowser

# PDF
from pdf_pedido import export_order_pdf

# --- Import condicional de jnius (solo en Android) ---
_autoclass = None
_cast = None
if platform == "android":
    try:
        from jnius import autoclass as _autoclass, cast as _cast  # type: ignore[import-not-found]
    except Exception:
        _autoclass = None
        _cast = None

DB_PATH = os.path.join(os.path.dirname(__file__), "bd_sqlite", "todoferre.db")


class HistoryScreen(Screen):
    def on_pre_enter(self, *args):
        self.clear_widgets()
        self.user = getattr(App.get_running_app(), "current_user", "usuario")

        root = BoxLayout(orientation="vertical", padding=10, spacing=8)

        # Título
        root.add_widget(Label(
            text=f"[b]Historial de pedidos de {self.user}[/b]",
            markup=True, size_hint=(1, None), height=dp(28)
        ))

        # Buscador
        self.q = TextInput(
            hint_text="Buscar por nombre, fantasía, RUT u orden…",
            multiline=False, size_hint=(1, None), height=dp(44)
        )
        self.q.bind(text=lambda *_: self._reload())
        root.add_widget(self.q)

        # 👇 salto de línea / espacio visual
        root.add_widget(Label(size_hint=(1, None), height=dp(10)))

        # Lista (scroll + grid)
        self.grid = GridLayout(cols=1, size_hint_y=None, spacing=dp(6), padding=(0, dp(6), 0, dp(6)))
        self.grid.bind(minimum_height=self.grid.setter("height"))
        sv = ScrollView(size_hint=(1, 1))
        sv.add_widget(self.grid)
        root.add_widget(sv)

        # Volver
        back = Button(text="< Volver", size_hint=(1, None), height=dp(46))
        back.bind(on_release=lambda *_: setattr(self.manager, "current", "tomar_pedido"))
        root.add_widget(back)

        self.add_widget(root)
        self._reload()

    # ---------- Helpers UI ----------
    def _add_row(self, order_no: str, cliente: str, total: int, ts: int):
        fecha = time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))
        total_fmt = f"${int(total):,}".replace(",", ".")
        txt = f"[b]{order_no}[/b]  ·  {cliente}\n{total_fmt}  ·  {fecha}"

        row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(60), spacing=dp(8))

        lbl = Label(text=txt, markup=True, size_hint=(1, None), halign="left", valign="middle")
        lbl.text_size = (0, None)
        lbl.bind(size=lambda w, *_: setattr(w, "text_size", (w.width - dp(8), None)))
        lbl.bind(texture_size=lambda w, *_: setattr(row, "height", max(dp(60), w.texture_size[1] + dp(10))))

        btn = Button(text="Generar PDF", size_hint=(None, None), width=dp(140), height=dp(42))
        btn.bind(on_release=lambda *_: self._generate_pdf(order_no))

        row.add_widget(lbl)
        row.add_widget(btn)
        self.grid.add_widget(row)

    def _open_file(self, path: str):
        """Abre el archivo en Android (ACTION_VIEW) o en escritorio via webbrowser."""
        # Escritorio (macOS/Windows/Linux): usar webbrowser
        try:
            if sys.platform.startswith(("darwin", "linux", "win")):
                webbrowser.open(f"file://{os.path.abspath(path)}")
                return
        except Exception:
            pass

        # Android: usar Intent ACTION_VIEW si jnius está disponible
        try:
            if platform == "android" and _autoclass and _cast:
                PythonActivity = _autoclass('org.kivy.android.PythonActivity')
                Intent = _autoclass('android.content.Intent')
                Uri = _autoclass('android.net.Uri')
                File = _autoclass('java.io.File')

                file_obj = File(os.path.abspath(path))
                uri = Uri.fromFile(file_obj)  # Nota: para Android 7+ idealmente FileProvider

                intent = Intent(Intent.ACTION_VIEW)
                intent.setDataAndType(uri, "application/pdf")
                currentActivity = _cast('android.app.Activity', PythonActivity.mActivity)
                currentActivity.startActivity(intent)
                return
        except Exception:
            pass

        # Último recurso: abrir también con webbrowser
        try:
            webbrowser.open(f"file://{os.path.abspath(path)}")
        except Exception:
            pass

    def _generate_pdf(self, order_no: str):
        try:
            pdf_path = export_order_pdf(order_no)
            # Popup con 2 botones
            content = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(10))
            content.add_widget(Label(text=f"Archivo creado:\n{pdf_path}", halign="center", valign="middle", size_hint=(1, 1)))
            btns = BoxLayout(size_hint=(1, None), height=dp(44), spacing=dp(8))
            abrir = Button(text="Abrir PDF")
            cerrar = Button(text="Cerrar")
            btns.add_widget(abrir); btns.add_widget(cerrar)
            content.add_widget(btns)

            popup = Popup(title="PDF generado", content=content, size_hint=(0.85, 0.5), auto_dismiss=False)
            abrir.bind(on_release=lambda *_: (popup.dismiss(), self._open_file(pdf_path)))
            cerrar.bind(on_release=lambda *_: popup.dismiss())
            popup.open()
        except Exception as e:
            # En caso de error mostramos un popup simple
            Popup(title="Error",
                  content=Label(text=str(e)),
                  size_hint=(0.8, 0.4)).open()

    # ---------- Carga/consulta ----------
    def _reload(self):
        term = (self.q.text or "").strip()
        like = f"%{term}%"

        con = sqlite3.connect(DB_PATH); cur = con.cursor()
        try:
            if term == "":
                cur.execute("""
                    SELECT o.order_no, o.cliente_display, o.total, o.created_at
                    FROM orders o
                    WHERE o.user=?
                    ORDER BY o.id DESC
                    LIMIT 200
                """, (self.user,))
            else:
                cur.execute("""
                    SELECT o.order_no, o.cliente_display, o.total, o.created_at
                    FROM orders o
                    LEFT JOIN clientes c ON c.rowid = o.cliente_rowid
                    WHERE o.user=?
                      AND (
                           o.order_no LIKE ? COLLATE NOCASE
                        OR o.cliente_display LIKE ? COLLATE NOCASE
                        OR c.nombre_fantasia LIKE ? COLLATE NOCASE
                        OR c.nombre_completo LIKE ? COLLATE NOCASE
                        OR c.numero_identificacion_fiscal LIKE ? COLLATE NOCASE
                      )
                    ORDER BY o.id DESC
                    LIMIT 200
                """, (self.user, like, like, like, like, like))

            rows = cur.fetchall()
        finally:
            con.close()

        self.grid.clear_widgets()
        if not rows:
            self.grid.add_widget(Label(text="(sin resultados)", size_hint=(1, None), height=dp(40)))
            return

        for order_no, cliente, total, created_at in rows:
            self._add_row(order_no, cliente, total, created_at)
