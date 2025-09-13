#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_drawio.py — v3.2 (limpio y estable)

- Analiza 1+ archivos .py (usado per-file por gen_all_flows.sh).
- Nodos = funciones (incluye métodos de clase).
- Edges f->f y f->DB (SQLite) con labels de SQL (SELECT/INSERT/UPDATE/DELETE).
- Lane por módulo + lane DATASOURCES a la derecha.
- Resalta en rojo nodos que tocan DB.
- Layout sugiyama-lite sencillo (por columnas).
- Exporta draw.io y opcionalmente Mermaid.

Uso típico (desde la raíz del repo):
  python3 tools_main/generate_drawio.py --files carrito.py --include_db \
    --layout sugi-lite --rank-origin in --theme midnight --arrow block \
    --edge-style orthogonal --line-jumps on --size-mode degree --legend on \
    --cols 0 --export drawio mermaid --outfile docs/flow.drawio
"""
from __future__ import annotations
from collections import defaultdict


import argparse, ast, html, math, pathlib, re, time
from collections import defaultdict, deque
from typing import Dict, Iterable, List, Optional, Set, Tuple

# ---------------- Paths base ----------------
ROOT = pathlib.Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
DOCS.mkdir(exist_ok=True)
IGNORE_DIRS = {
    ".venv","venv","__pycache__","build","dist",".buildozer","jni","external",
    ".git",".idea",".vscode"
}

# ---------------- Detección SQL/DB ----------------
SQL_RE = re.compile(
    r"(?is)\b("
    r"SELECT|INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|PRAGMA|BEGIN|COMMIT|ROLLBACK"
    r")\b"
)

DB_NAME_RE = re.compile(r'(?i)([A-Za-z0-9_\-./]+?\.(?:db|sqlite3?|sqlite))')

# ---------------- Estilos draw.io ----------------
def style_palette(theme: str) -> Dict[str, str]:
    t = (theme or "light").lower()
    if t == "midnight":
        return {
            "bg":"#0F172A","lane_fill":"#111827","func_fill":"#1F2937","func_stroke":"#93C5FD",
            "db_fill":"#FCA5A5","db_stroke":"#7F1D1D","text":"#E5E7EB","edge":"#93C5FD",
            "edge_db":"#FCA5A5","legend":"#334155",
        }
    if t == "solarized":
        return {
            "bg":"#FDF6E3","lane_fill":"#EEE8D5","func_fill":"#E1F5FE","func_stroke":"#268BD2",
            "db_fill":"#FFCDD2","db_stroke":"#CB4B16","text":"#073642","edge":"#268BD2",
            "edge_db":"#CB4B16","legend":"#D6D6C2",
        }
    return {
        "bg":"#FFFFFF","lane_fill":"#F3F4F6","func_fill":"#E8F1FF","func_stroke":"#1F77B4",
        "db_fill":"#FFEBEB","db_stroke":"#D43C3C","text":"#111827","edge":"#1F2937",
        "edge_db":"#D43C3C","legend":"#ECECEC",
    }

def drawio_edge_style(edge_style: str, arrow: str, color: str, dashed: bool, line_jumps: bool) -> str:
    edge_style = (edge_style or "orthogonal").lower()
    if edge_style == "straight":
        es = "edgeStyle=straight;orthogonalLoop=1;"
    elif edge_style == "curved":
        es = "edgeStyle=orthogonalEdgeStyle;curved=1;orthogonalLoop=1;"
    else:
        es = "edgeStyle=orthogonalEdgeStyle;orthogonalLoop=1;"
    arrow = (arrow or "block").lower()
    if arrow == "open": end_arrow = "open"
    elif arrow == "classic": end_arrow = "classic"
    else: end_arrow = "block"
    dash = "dashed=1;" if dashed else ""
    jumps = "jumpStyle=arc;jumpSize=8;" if line_jumps else ""
    return f"endArrow={end_arrow};rounded=1;jettySize=auto;{es}{jumps}{dash}strokeColor={color};{dash}"

# ---------------- Constantes SQL/DB ----------------
class ConstCollector(ast.NodeVisitor):
    """Recoge constantes tipo:
        SQL_TX = "select ..."
        DB_PATH = "bd_sqlite/x.db"
        DB_PATH = Path("bd_sqlite/x.db")    # pathlib / from pathlib import Path
    """
    def __init__(self):
        self.sql_of: Dict[str,str] = {}
        self.db_of:  Dict[str,str] = {}

    def _extract_path_str(self, node: ast.AST) -> Optional[str]:
        if not isinstance(node, ast.Call):
            return None
        fn = None
        if isinstance(node.func, ast.Name):
            fn = node.func.id
        elif isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
            fn = f"{node.func.value.id}.{node.func.attr}"
        if fn not in {"Path", "pathlib.Path"}:
            return None
        if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
            return node.args[0].value
        return None

    def visit_Assign(self, node: ast.Assign):
        s_val: Optional[str] = None

        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            s_val = node.value.value
        elif isinstance(node.value, ast.Call):
            ps = self._extract_path_str(node.value)
            if ps:
                s_val = ps

        if s_val is None:
            return

        m  = SQL_RE.search(s_val)
        m2 = DB_NAME_RE.search(s_val)
        sql = m.group(1).upper() if m else None
        db  = m2.group(1) if m2 else None
        if not sql and not db:
            return

        for t in node.targets:
            if isinstance(t, ast.Name):
                if sql: self.sql_of[t.id] = sql
                if db:  self.db_of[t.id]  = db

# ---------------- Imports ----------------
class ImportResolver(ast.NodeVisitor):
    def __init__(self):
        self.name_to_module: Dict[str,str] = {}
    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            mod = alias.name
            asname = alias.asname or mod.split(".")[-1]
            self.name_to_module[asname] = mod
    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.module is None: return
        base = node.module
        for alias in node.names:
            local = alias.asname or alias.name
            self.name_to_module[local] = base

# ---------------- Visitor principal ----------------
class V(ast.NodeVisitor):
    def __init__(self, mod: str, src: str, imap: Dict[str,str], csql: Dict[str,str], cdb: Dict[str,str]):
        self.mod = mod
        self.src = src
        self.imap = imap
        self.csql = csql
        self.cdb  = cdb
        self.class_stack: List[str] = []
        self.stack: List[str] = []
        self.funcs: Set[str] = set()
        self.func_class_of: Dict[str, Optional[str]] = {}
        self.edges: Set[Tuple[str,str,str,Optional[str]]] = set()  # (u, tgt_mod, tgt_fn, label)
        self.databases: Set[str] = set()
        self.db_edges: List[Tuple[str,str,Optional[str]]] = []     # (u, db, SQL)
        self.methods_by_class: Dict[str, Set[str]] = defaultdict(set)  # <- NUEVO


    def cur(self): return self.stack[-1] if self.stack else None
    def _qual(self, fn: str) -> str:
        if self.class_stack: return f"{self.mod}.{self.class_stack[-1]}.{fn}"
        return f"{self.mod}.{fn}"

    def visit_ClassDef(self, n: ast.ClassDef):
        self.class_stack.append(n.name); self.generic_visit(n); self.class_stack.pop()

    def visit_FunctionDef(self, n: ast.FunctionDef):
        fn = self._qual(n.name)
        self.funcs.add(fn)
        # guarda mapeo función->clase (ya estaba)
        self.func_class_of[fn] = self.class_stack[-1] if self.class_stack else None
        # registra que este nombre de método existe en la clase actual
        if self.class_stack:
            self.methods_by_class[self.class_stack[-1]].add(n.name)   # <- NUEVO
        self.stack.append(fn)
        self.generic_visit(n)
        self.stack.pop()

    def visit_AsyncFunctionDef(self, n: ast.AsyncFunctionDef): self.visit_FunctionDef(n)

    def _resolve_call(self, node: ast.AST) -> Tuple[str,str]:
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            base=node.value.id; fn=node.attr
            if base in self.imap: return (self.imap[base].split(".")[0], fn)
            return (self.mod, fn)
        if isinstance(node, ast.Name):
            name=node.id
            if name in self.imap: return (self.imap[name].split(".")[0], name)
            return (self.mod, name)
        return (self.mod, "<call>")

    def _label_from_args(self, args: List[ast.AST]) -> Optional[str]:
        sql_label = None
        def scan_string(s: str):
            nonlocal sql_label
            m = SQL_RE.search(s)
            if m: sql_label = m.group(1).upper()
            m2 = DB_NAME_RE.search(s)
            if m2: self.databases.add(m2.group(1))

        for a in args:
            if isinstance(a, ast.Constant) and isinstance(a.value, str):
                scan_string(a.value)
            elif isinstance(a, ast.JoinedStr):  # f"SELECT ..." → concatenar literales
                lit = "".join(p.value for p in a.values
                              if isinstance(p, ast.Constant) and isinstance(p.value, str))
                scan_string(lit)
            elif isinstance(a, ast.Name):
                if a.id in self.csql: sql_label = self.csql[a.id]
                if a.id in self.cdb:  self.databases.add(self.cdb[a.id])
        return sql_label

    def _event_kwargs(self, caller: str, kwargs: List[ast.keyword]):
        for kw in kwargs:
            if not kw.arg or not kw.arg.startswith("on_"): 
                continue
            tgt_mod, tgt_fn = None, None
            if isinstance(kw.value, ast.Attribute) and isinstance(kw.value.value, ast.Name):
                base=kw.value.value.id; name=kw.value.attr
                tgt_mod = self.imap.get(base, self.mod).split(".")[0]; tgt_fn = name
            elif isinstance(kw.value, ast.Name):
                name=kw.value.id; tgt_mod = self.imap.get(name, self.mod).split(".")[0]; tgt_fn = name
            else:
                continue
            self.edges.add((caller, tgt_mod, tgt_fn, kw.arg))

    def visit_Call(self, node: ast.Call):
        caller = self.cur()
        if not caller:
            return

        # Qué se está llamando (mod estimado + símbolo)
        cm, cf = self._resolve_call(node.func)

        # ---- Ajuste de CONTEXTO DE CLASE en el destino ----
        # Caso A: self.metodo(...) / cls.metodo(...)
        if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
            base = node.func.value.id
            if base in {"self", "cls"} and self.class_stack:
                cm = f"{self.mod}.{self.class_stack[-1]}"
            # Caso B: ClassName.metodo(...) dentro del mismo módulo
            elif base in self.methods_by_class and base in (self.class_stack or [base]):
                # si el "base" coincide con una clase actual/visible, cualifica a mod.Clase
                cm = f"{self.mod}.{base}"
        # Caso C: metodo(...) (nombre "desnudo" dentro de una clase actual)
        elif isinstance(node.func, ast.Name) and self.class_stack:
            cur_cls = self.class_stack[-1]
            if node.func.id in self.methods_by_class.get(cur_cls, set()):
                cm = f"{self.mod}.{cur_cls}"

        # ---- Detección DB/SQL (tal como ya la tienes) ----
        # sqlite3.connect("file.db") o sqlite3.connect(DB_PATH)
        if (isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name)
            and cf == "connect" and self.imap.get(node.func.value.id, "").startswith("sqlite3")):
            for a in list(node.args) + [kw.value for kw in node.keywords]:
                if isinstance(a, ast.Constant) and isinstance(a.value, str):
                    m = DB_NAME_RE.search(a.value)
                    if m:
                        self.databases.add(m.group(1))
                elif isinstance(a, ast.Name):
                    if a.id in self.cdb:
                        self.databases.add(self.cdb[a.id])

        # etiqueta SQL (constante, f-string o nombre)
        sql_label = self._label_from_args(list(node.args) + [kw.value for kw in node.keywords])

        # Si llama a execute/executemany/executescript sin etiqueta, usa "SQL"
        if cf in {"execute", "executemany", "executescript"} and not sql_label:
            sql_label = "SQL"

        # Si hay SQL pero no DB detectada, usa una genérica
        if sql_label and not self.databases:
            self.databases.add("DB")

        # Aristas función→DB
        if sql_label and self.databases:
            for db in sorted(self.databases):
                self.db_edges.append((caller, db, sql_label))

        # Eventos (on_*)
        self._event_kwargs(caller, node.keywords)

        # ---- Arista función→función con el módulo/clase correctamente cualificado ----
        self.edges.add((caller, cm, cf, cf))

        # Continuar recorriendo hijos
        self.generic_visit(node)


        # sqlite3.connect("file.db") o sqlite3.connect(DB_PATH)
        if (isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name)
            and cf == "connect" and self.imap.get(node.func.value.id, "").startswith("sqlite3")):
            for a in list(node.args) + [kw.value for kw in node.keywords]:
                if isinstance(a, ast.Constant) and isinstance(a.value, str):
                    m = DB_NAME_RE.search(a.value)
                    if m: self.databases.add(m.group(1))
                elif isinstance(a, ast.Name):
                    if a.id in self.cdb: self.databases.add(self.cdb[a.id])

        # etiqueta SQL (constante, f-string o nombre de var)
        sql_label = self._label_from_args(list(node.args) + [kw.value for kw in node.keywords])

        # Si llama a execute/executemany/executescript y aún no hay etiqueta, usa "SQL"
        if cf in {"execute", "executemany", "executescript"} and not sql_label:
            sql_label = "SQL"

        # Si hay SQL pero ninguna DB identificada aún, usa una genérica
        if sql_label and not self.databases:
            self.databases.add("DB")

        # Crear aristas función→DB si corresponde
        if sql_label and self.databases:
            for db in sorted(self.databases):
                self.db_edges.append((caller, db, sql_label))

        # Eventos (on_*)
        self._event_kwargs(caller, node.keywords)

        # Arista función→función normal
        self.edges.add((caller, cm, cf, cf))
        self.generic_visit(node)

# ---------------- IO helpers ----------------
def _should_ignore(p: pathlib.Path)->bool:
    return any(seg in IGNORE_DIRS for seg in p.parts)

def _iter_files(paths: Iterable[str], files: Iterable[str], no_rec: bool):
    seen=set()
    def add(p: pathlib.Path):
        if p.suffix==".py" and not _should_ignore(p) and p not in seen:
            seen.add(p); return True
        return False
    for f in files:
        p=(ROOT/f).resolve()
        if p.is_file() and add(p): yield p
    for d in paths:
        b=(ROOT/d).resolve()
        if not b.exists(): continue
        it=b.glob("*.py") if no_rec else b.rglob("*.py")
        for p in it:
            if add(p): yield p
    if not paths and not files:
        # por defecto: nada (el batch script pasa --files)
        return

def _parse_file(p: pathlib.Path):
    src=p.read_text(encoding="utf-8",errors="ignore")
    t=ast.parse(src); mod=p.with_suffix("").name
    ir=ImportResolver(); ir.visit(t)
    cc=ConstCollector(); cc.visit(t)
    v=V(mod, src, ir.name_to_module, cc.sql_of, cc.db_of); v.visit(t)
    return v

# ---------------- Utilidades de layout ----------------
def topological_order_kahn(nodes: List[str], edges: List[Tuple[str,str]])->List[str]:
    indeg = {n:0 for n in nodes}
    adj=defaultdict(list)
    for u,v in edges:
        if u in indeg and v in indeg and u!=v:
            adj[u].append(v); indeg[v]+=1
    q=deque([n for n,d in indeg.items() if d==0])
    out=[]
    while q:
        u=q.popleft(); out.append(u)
        for v in adj.get(u,[]):
            indeg[v]-=1
            if indeg[v]==0: q.append(v)
    if len(out)<len(nodes):  # hay ciclos: añade lo que falte por grado
        rest=[n for n in nodes if n not in out]
        rest.sort(key=lambda n: (-sum(1 for u,v in edges if u==n), n))
        out+=rest
    return out

# ---------------- Export draw.io ----------------
def export_drawio(by_mod: Dict[str,List[str]],
                  edges_ff: List[Tuple[str,str]],
                  db_nodes: Set[str],
                  edges_fd: List[Tuple[str,str,Optional[str]]],
                  args) -> str:
    pal=style_palette(args.theme)
    lane_w, lane_h = 1000, 600
    node_w, node_h = 180, 54
    gap_x, gap_y = 220, 120
    cols = max(1, args.cols or 3)

    out=[]
    out.append(f'<mxfile host="app.diagrams.net" modified="{time.strftime("%Y-%m-%d %H:%M:%S")}" agent="gd_v32">')
    out.append('<diagram id="Flow" name="Flow"><mxGraphModel><root>')
    out.append('<mxCell id="0"/><mxCell id="1" parent="0"/>')

    def nid():
        nid.c+=1; return str(nid.c)
    nid.c=100

    # Mapas para edges y estilos
    lane_id: Dict[str,str]={}
    fn_pos: Dict[str, Tuple[str,int,int,str]] = {}  # fn -> (lane_id, x, y, cell_id)
    db_pos: Dict[str,str] = {}                      # nombre DB -> id nodo DB

    # lanes por módulo
    x0,y0=40,40
    lane_gap=120
    x=x0
    for mod in sorted(by_mod.keys()):
        lid=nid(); lane_id[mod]=lid
        out.append(
            f'<mxCell id="{lid}" value="{html.escape(mod)}" style="swimlane;rounded=1;'
            f'fillColor={pal["lane_fill"]};fontColor={pal["text"]};" vertex="1" parent="1">'
            f'<mxGeometry x="{x}" y="{y0}" width="{lane_w}" height="{lane_h}" as="geometry"/></mxCell>'
        )
        # funciones en una cuadrícula (topo order para algo de “naturalidad”)
        funcs = by_mod[mod]
        order = topological_order_kahn(funcs, [(u,v) for u,v in edges_ff if u in funcs and v in funcs])
        if not order: order = funcs[:]
        C = cols if cols>0 else max(1, int(math.sqrt(len(order))) )
        for i,fn in enumerate(order):
            r=i//C; c=i% C
            xx = 40 + c*(node_w+ (gap_x-140))
            yy = 40 + r*(node_h+ (gap_y-66))
            cell=nid()
            # ¿toca DB?
            touches_db = any(u==fn for (u,_,_) in edges_fd)
            fill = pal["db_fill"] if touches_db else pal["func_fill"]
            stroke = pal["db_stroke"] if touches_db else pal["func_stroke"]
            out.append(
                f'<mxCell id="{cell}" value="{html.escape(fn.split(".")[-1])}()" '
                f'style="rounded=1;whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};fontColor={pal["text"]};" '
                f'vertex="1" parent="{lid}"><mxGeometry x="{xx}" y="{yy}" width="{node_w}" height="{node_h}" as="geometry"/></mxCell>'
            )
            fn_pos[fn]=(lid, xx, yy, cell)
        x += lane_w + lane_gap

    # lane DATASOURCES (si procede)
    if args.include_db and (db_nodes or edges_fd):
        lid=nid(); lane_id["DATASOURCES"]=lid
        xd = x
        out.append(
            f'<mxCell id="{lid}" value="DATASOURCES" style="swimlane;rounded=1;fillColor={pal["lane_fill"]};fontColor={pal["text"]};" '
            f'vertex="1" parent="1"><mxGeometry x="{xd}" y="{y0}" width="{lane_w//2}" height="{lane_h}" as="geometry"/></mxCell>'
        )
        for i,db in enumerate(sorted(db_nodes or {"DB"})):
            xx = 40; yy = 40 + i*120
            ndb=nid()
            out.append(
                f'<mxCell id="{ndb}" value="DB: {html.escape(db)}" '
                f'style="ellipse;whiteSpace=wrap;fillColor={pal["db_fill"]};strokeColor={pal["db_stroke"]};fontColor={pal["text"]};" '
                f'vertex="1" parent="{lid}"><mxGeometry x="{xx}" y="{yy}" width="200" height="70" as="geometry"/></mxCell>'
            )
            db_pos[db]=ndb

    # edges f->f (mismo estilo base)
    edge_style = drawio_edge_style(args.edge_style, args.arrow, pal["edge"], False, args.line_jumps=="on")
    for u,v in edges_ff:
        if u not in fn_pos or v not in fn_pos: continue
        sid=fn_pos[u][3]; tid=fn_pos[v][3]
        out.append(
            f'<mxCell id="{nid()}" style="{edge_style}" edge="1" parent="1" source="{sid}" target="{tid}">'
            f'<mxGeometry relative="1" as="geometry"/></mxCell>'
        )

    # edges f->DB
    if args.include_db and edges_fd:
        edge_style_db = drawio_edge_style(args.edge_style, args.arrow, pal["edge_db"], True, args.line_jumps=="on")
        for u,db,label in edges_fd:
            sid = fn_pos.get(u, (None,None,None,None))[3]
            tid = db_pos.get(db) or db_pos.get("DB")
            if not (sid and tid): continue
            lbl = html.escape(label or "") if args.label_edges else ""
            out.append(
                f'<mxCell id="{nid()}" value="{lbl}" style="{edge_style_db}" edge="1" parent="1" source="{sid}" target="{tid}">'
                f'<mxGeometry relative="1" as="geometry"/></mxCell>'
            )

    # leyenda
    if args.legend == "on":
        leg_id=nid()
        out.append(
            f'<mxCell id="{leg_id}" value="Legend&#xa;• Node (red): touches DB&#xa;• Dashed edge: inter-module&#xa;• Style: {args.theme}/{args.edge_style}/{args.arrow}&#xa;• Generated: {time.strftime("%Y-%m-%d %H:%M:%S")}" '
            f'style="rounded=1;whiteSpace=wrap;html=1;fillColor={pal["legend"]};strokeColor={pal["func_stroke"]};fontColor={pal["text"]};" vertex="1" parent="1">'
            f'<mxGeometry x="{x0+40}" y="{y0+lane_h-80}" width="340" height="110" as="geometry"/></mxCell>'
        )

    out.append('</root></mxGraphModel></diagram></mxfile>')
    return "\n".join(out)

# ---------------- Export Mermaid (sencillo) ----------------
def export_mermaid(by_mod: Dict[str,List[str]],
                   edges_ff: List[Tuple[str,str]],
                   db_nodes: Set[str],
                   edges_fd: List[Tuple[str,str,Optional[str]]],
                   args) -> str:
    lines=[]
    lines.append("%% generated by generate_drawio.py v3.2")
    lines.append("flowchart LR")
    # subgraphs por módulo
    for mod in sorted(by_mod):
        lines.append(f"  subgraph {mod}")
        for fn in by_mod[mod]:
            node = fn.replace(".","_")
            lines.append(f"    {node}[{fn.split('.')[-1]}()]")
        lines.append("  end")
    # dbs
    for db in sorted(db_nodes or {"DB"}):
        lines.append(f"  db_{db.replace('.','_').replace('/','_')}(({db})):::db")
    # edges f->f
    for u,v in edges_ff:
        lines.append(f"  {u.replace('.','_')} --> {v.replace('.','_')}")
    # edges f->db
    for u,db,label in edges_fd:
        lbl = f'|{label}|' if (args.label_edges and label) else ""
        lines.append(f"  {u.replace('.','_')} -- {lbl} --> db_{db.replace('.','_').replace('/','_')}")
    lines.append("classDef db fill:#ffdede,stroke:#d43c3c;")
    return "\n".join(lines)

# ---------------- Main ----------------
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--files", nargs="*", default=[], help="Archivos .py (relativos a la raíz del repo)")
    ap.add_argument("--paths", nargs="*", default=[], help="Directorios a escanear")
    ap.add_argument("--no_recurse", action="store_true", help="No recursivo al usar --paths")
    # estilos / opciones
    ap.add_argument("--include_db", action="store_true", help="Dibujar lane DATASOURCES y edges función→DB")
    ap.add_argument("--label_edges", action="store_true", help="Etiquetar aristas con SQL")
    ap.add_argument("--hide_private", action="store_true", help="Ocultar funciones que empiezan con '_'")
    ap.add_argument("--layout", default="sugi-lite")
    ap.add_argument("--rank-origin", default="in")
    ap.add_argument("--theme", default="light")
    ap.add_argument("--arrow", default="block")
    ap.add_argument("--edge-style", default="orthogonal")
    ap.add_argument("--line-jumps", default="off", choices=["on","off"])
    ap.add_argument("--size-mode", default="degree")
    ap.add_argument("--legend", default="on", choices=["on","off"])
    ap.add_argument("--cols", type=int, default=3)
    ap.add_argument("--export", nargs="*", default=["drawio"], choices=["drawio","mermaid"])
    ap.add_argument("--outfile", default=str(DOCS/"flow.drawio"))
    args=ap.parse_args()

    # Parsear todos los archivos
    files=list(_iter_files(args.paths, args.files, args.no_recurse)) or []
    if not files:
        print("[WARN] No se recibieron archivos. Usa --files o --paths.")
        return

    by_mod: Dict[str,List[str]] = defaultdict(list)
    edges_ff_set: Set[Tuple[str,str]] = set()
    db_nodes: Set[str] = set()
    edges_fd: List[Tuple[str,str,Optional[str]]] = []

    for p in files:
        v=_parse_file(p)
        # filtro private si corresponde
        funcs = sorted(f for f in v.funcs if not (args.hide_private and f.split(".")[-1].startswith("_")))
        by_mod[v.mod].extend(funcs)
        # f->f: convierte a calificados
        for (u, tgt_mod, tgt_fn, _lab) in v.edges:
            u2=u
            v2 = f"{tgt_mod}.{tgt_fn}" if "." not in tgt_fn else tgt_fn
            edges_ff_set.add((u2, v2))
        # DBs
        db_nodes |= set(v.databases)
        edges_fd.extend(v.db_edges)

    # dedup y orden por módulo
    for mod in list(by_mod):
        seen=set(); uniq=[]
        for f in by_mod[mod]:
            if f not in seen: seen.add(f); uniq.append(f)
        by_mod[mod]=uniq

    xml = export_drawio(by_mod, sorted(edges_ff_set), db_nodes, edges_fd, args)

    out = pathlib.Path(args.outfile)
    out.parent.mkdir(parents=True, exist_ok=True)
    if any(e.lower()=="drawio" for e in args.export):
        out.write_text(xml, encoding="utf-8")
        print(f"OK draw.io → {out}")

    if any(e.lower()=="mermaid" for e in args.export):
        mmd = export_mermaid(by_mod, sorted(edges_ff_set), db_nodes, edges_fd, args)
        mmd_path = out.with_suffix(".mmd") if out.suffix == ".drawio" else (DOCS/"flow.mmd")
        mmd_path.write_text(mmd, encoding="utf-8")
        print(f"OK mermaid → {mmd_path}")

if __name__=="__main__":
    main()
