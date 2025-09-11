#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
draw.io v2.1: swimlanes + imports + DB + etiquetas + callbacks Kivy + constantes SQL
Salida: docs/flow.drawio
"""
import ast, html, argparse, pathlib, re
from collections import defaultdict, Counter
from typing import Dict, Iterable, List, Optional, Set, Tuple

ROOT = pathlib.Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"; DOCS.mkdir(exist_ok=True)
IGNORE_DIRS = {".venv","venv","__pycache__","build","dist",".buildozer","jni","external",".git",".idea",".vscode"}

SQL_RE = re.compile(r'(?is)\b(SELECT|INSERT|UPDATE|DELETE)\b')
DB_NAME_RE = re.compile(r'(?i)([A-Za-z0-9_\-]+\.db)')

# ---- Constantes ----
class ConstCollector(ast.NodeVisitor):
    def __init__(self):
        self.sql_of: Dict[str,str] = {}
        self.db_of: Dict[str,str]  = {}
    def visit_Assign(self, node: ast.Assign):
        if not (isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)):
            return
        s = node.value.value
        m = SQL_RE.search(s); m2 = DB_NAME_RE.search(s)
        sql = m.group(1).upper() if m else None
        db  = m2.group(1) if m2 else None
        if not sql and not db: return
        for t in node.targets:
            if isinstance(t, ast.Name):
                if sql: self.sql_of[t.id] = sql
                if db:  self.db_of[t.id]  = db

# ---- Imports ----
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

# ---- Call graph ----
class V(ast.NodeVisitor):
    def __init__(self, mod: str, src: str, imap: Dict[str,str], csql: Dict[str,str], cdb: Dict[str,str]):
        self.mod = mod
        self.src = src
        self.imap = imap
        self.csql = csql
        self.cdb  = cdb
        self.stack: List[str] = []
        self.funcs: Set[str] = set()
        self.edges: Set[Tuple[str,str,str,Optional[str]]] = set()
        self.databases: Set[str] = set()
        self.db_edges: List[Tuple[str,str,Optional[str]]] = []

    def cur(self): return self.stack[-1] if self.stack else None
    def visit_FunctionDef(self, n: ast.FunctionDef):
        fn=f"{self.mod}.{n.name}"; self.funcs.add(fn); self.stack.append(fn); self.generic_visit(n); self.stack.pop()
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
        sql_label=None
        for a in args:
            if isinstance(a, ast.Constant) and isinstance(a.value, str):
                m=SQL_RE.search(a.value); 
                if m: sql_label = m.group(1).upper()
                m2=DB_NAME_RE.search(a.value)
                if m2: self.databases.add(m2.group(1))
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
        caller=self.cur()
        if not caller: return
        cm, cf = self._resolve_call(node.func)

        # sqlite3.connect("file.db")
        if (isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name)
            and cf=="connect" and self.imap.get(node.func.value.id, "").startswith("sqlite3")):
            for a in list(node.args) + [kw.value for kw in node.keywords]:
                if isinstance(a, ast.Constant) and isinstance(a.value, str):
                    m=DB_NAME_RE.search(a.value)
                    if m: self.databases.add(m.group(1))

        sql_label = self._label_from_args(list(node.args) + [kw.value for kw in node.keywords])
        if sql_label and self.databases:
            for db in sorted(self.databases):
                self.db_edges.append((caller, db, sql_label))

        # eventos (bind/constructor con on_*)
        if cf=="bind": self._event_kwargs(caller, node.keywords)
        else:          self._event_kwargs(caller, node.keywords)

        self.edges.add((caller, cm, cf, cf))
        self.generic_visit(node)

# ---- IO ----
def _should_ignore(p: pathlib.Path)->bool: return any(seg in IGNORE_DIRS for seg in p.parts)
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
        for p in ROOT.rglob("*.py"):
            if add(p): yield p

def _parse_file(p: pathlib.Path):
    src=p.read_text(encoding="utf-8",errors="ignore")
    t=ast.parse(src); mod=p.with_suffix("").name
    ir=ImportResolver(); ir.visit(t)
    cc=ConstCollector(); cc.visit(t)
    v=V(mod, src, ir.name_to_module, cc.sql_of, cc.db_of); v.visit(t)
    return v

# ---- draw.io ----
def main():
    ap=argparse.ArgumentParser(description="draw.io swimlanes + DB + etiquetas + eventos + constantes SQL")
    ap.add_argument("--paths",nargs="*",default=[])
    ap.add_argument("--files",nargs="*",default=[])
    ap.add_argument("--no_recurse",action="store_true")
    ap.add_argument("--modules",nargs="*",default=[])
    ap.add_argument("--exclude_mods",nargs="*",default=["generate_mermaid","generate_drawio","analyze_sql"])
    ap.add_argument("--hide_private",action="store_true")
    ap.add_argument("--inter_module_only",action="store_true")
    ap.add_argument("--include_db",action="store_true")
    ap.add_argument("--label_edges",action="store_true")
    ap.add_argument("--cols",type=int,default=3)
    ap.add_argument("--outfile",default="docs/flow.drawio")
    args=ap.parse_args()

    visitors=[]
    for p in _iter_files(args.paths,args.files,args.no_recurse):
        try: visitors.append(_parse_file(p))
        except Exception as ex: print(f"[WARN] {p}: {ex}")

    funcs=set().union(*(v.funcs for v in visitors))
    if args.modules:      funcs={fn for fn in funcs if fn.split(".")[0] in set(args.modules)}
    if args.exclude_mods: funcs={fn for fn in funcs if fn.split(".")[0] not in set(args.exclude_mods)}
    if args.hide_private: funcs={fn for fn in funcs if not fn.split(".")[-1].startswith("_")}

    edges=set(); db_nodes=set(); db_edges=[]
    for v in visitors:
        for (caller, cm, cf, label) in v.edges:
            if caller in funcs:
                if args.inter_module_only and (caller.split(".")[0]==cm):
                    continue
                edges.add((caller, cm, cf, label))
        if args.include_db:
            db_nodes |= v.databases
            for item in v.db_edges:
                if item[0] in funcs: db_edges.append(item)

    degree=Counter()
    for (caller, cm, cf, _) in edges:
        degree[caller]+=1; degree[f"{cm}.{cf}"]+=1

    by_mod=defaultdict(list)
    for fn in funcs: by_mod[fn.split(".")[0]].append(fn)
    for mod in by_mod: by_mod[mod].sort(key=lambda fn:(-degree[fn], fn))

    lane_w,lane_pad = 980,90
    node_w,node_h   = 200,64
    gap_x,gap_y,lanes_gap = 46,26,90
    cols=max(1,args.cols)

    next_id=2
    parts=[
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<mxfile host="app.diagrams.net">','<diagram name="Flow">','<mxGraphModel><root>',
        '<mxCell id="0"/>','<mxCell id="1" parent="0"/>'
    ]
    y_cursor=20; id_map={}

    # lanes/nodos
    for mod in sorted(by_mod):
        nodes=by_mod[mod]; rows=max(1,(len(nodes)+cols-1)//cols); lane_h=lane_pad+rows*(node_h+gap_y)
        lane_id=str(next_id); next_id+=1
        parts.append(f'<mxCell id="{lane_id}" value="{html.escape(mod)}" style="swimlane;horizontal=0;fontStyle=1;startSize=28;rounded=1;" vertex="1" parent="1">')
        parts.append(f'<mxGeometry x="20" y="{y_cursor}" width="{lane_w}" height="{lane_h}" as="geometry"/>')
        parts.append('</mxCell>')
        x0,y0=40,y_cursor+44; x,y,c=x0,y0,0
        for fn in nodes:
            nid=str(next_id); next_id+=1; id_map[fn]=nid
            label=html.escape(fn.split(".")[-1]+"()")
            parts.append(f'<mxCell id="{nid}" value="{label}" style="rounded=1;whiteSpace=wrap;html=1;fontSize=13;" vertex="1" parent="{lane_id}">')
            parts.append(f'<mxGeometry x="{x}" y="{y}" width="{node_w}" height="{node_h}" as="geometry"/>')
            parts.append('</mxCell>')
            c+=1
            if c>=cols: c=0; x=x0; y+=node_h+gap_y
            else: x+=node_w+gap_x
        y_cursor+=lane_h+lanes_gap

    # bloque DB opcional
    db_id_map={}
    if args.include_db and db_nodes:
        db_lane_id=str(next_id); next_id+=1
        db_lane_w,db_lane_h = 540, 120 + 86*len(db_nodes)
        parts.append(f'<mxCell id="{db_lane_id}" value="DATASOURCES" style="swimlane;horizontal=0;fontStyle=1;startSize=28;rounded=1;" vertex="1" parent="1">')
        parts.append(f'<mxGeometry x="{lane_w + 60}" y="20" width="{db_lane_w}" height="{db_lane_h}" as="geometry"/>')
        parts.append('</mxCell>')
        x_db,y_db=40,60
        for db in sorted(db_nodes):
            did=str(next_id); next_id+=1; db_id_map[db]=did
            parts.append(f'<mxCell id="{did}" value="{html.escape(f"DB: {db}")}" style="shape=ellipse;whiteSpace=wrap;html=1;fontStyle=1;" vertex="1" parent="{db_lane_id}">')
            parts.append(f'<mxGeometry x="{x_db}" y="{y_db}" width="220" height="80" as="geometry"/>')
            parts.append('</mxCell>')
            y_db+=86

    # aristas función→función (sólido intra, punteado inter)
    for (caller, cm, cf, label) in sorted(edges):
        src=id_map.get(caller); dst=id_map.get(f"{cm}.{cf}")
        if not src or not dst: continue
        same = (caller.split(".")[0]==cm)
        style='endArrow=block;edgeStyle=orthogonalEdgeStyle;rounded=1;'
        if not same: style+='dashed=1;'
        eid=str(next_id); next_id+=1
        parts.append(f'<mxCell id="{eid}" style="{style}" edge="1" parent="1" source="{src}" target="{dst}">')
        parts.append('<mxGeometry relative="1" as="geometry"/>')
        parts.append('</mxCell>')
        # (opcional: etiqueta de arista con hijo; omitimos para no saturar)

    # aristas función→DB (punteadas)
    for (caller, db, op) in db_edges:
        src=id_map.get(caller); dst=db_id_map.get(db)
        if not src or not dst: continue
        style='endArrow=block;edgeStyle=orthogonalEdgeStyle;rounded=1;dashed=1;'
        eid=str(next_id); next_id+=1
        parts.append(f'<mxCell id="{eid}" style="{style}" edge="1" parent="1" source="{src}" target="{dst}">')
        parts.append('<mxGeometry relative="1" as="geometry"/>')
        parts.append('</mxCell>')

    parts += ['</root></mxGraphModel></diagram></mxfile>']
    out=(ROOT/args.outfile).resolve(); out.write_text("\n".join(parts),encoding="utf-8")
    print(f"OK ➜ {out}")

if __name__=="__main__": main()
