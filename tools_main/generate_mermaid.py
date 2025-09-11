#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mermaid v2.1: subgraphs por módulo + imports + DB + etiquetas + callbacks Kivy + constantes SQL.
Salida: docs/flow.md
"""
import ast, argparse, pathlib, re
from collections import defaultdict
from typing import Dict, Iterable, List, Optional, Set, Tuple

ROOT = pathlib.Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"; DOCS.mkdir(exist_ok=True)
IGNORE_DIRS = {".venv","venv","__pycache__","build","dist",".buildozer","jni","external",".git",".idea",".vscode"}

SQL_RE = re.compile(r'(?is)\b(SELECT|INSERT|UPDATE|DELETE)\b')
DB_NAME_RE = re.compile(r'(?i)([A-Za-z0-9_\-]+\.db)')

# ---------- Colección de constantes SQL/DB ----------
class ConstCollector(ast.NodeVisitor):
    def __init__(self):
        self.sql_of: Dict[str, str] = {}     # nombre -> op SQL (SELECT/INSERT/...)
        self.db_of: Dict[str, str]  = {}     # nombre -> db.sqlite

    def visit_Assign(self, node: ast.Assign):
        if not isinstance(node.value, ast.Constant) or not isinstance(node.value.value, str):
            return
        s = node.value.value
        sql = None; db = None
        m = SQL_RE.search(s)
        if m: sql = m.group(1).upper()
        m2 = DB_NAME_RE.search(s)
        if m2: db = m2.group(1)
        if not sql and not db: return
        for t in node.targets:
            if isinstance(t, ast.Name):
                if sql: self.sql_of[t.id] = sql
                if db:  self.db_of[t.id]  = db

# ---------- Imports ----------
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

# ---------- Call graph ----------
class CallGraphVisitor(ast.NodeVisitor):
    def __init__(self, module_name: str, src: str, import_map: Dict[str,str],
                 const_sql: Dict[str,str], const_db: Dict[str,str]):
        self.module = module_name
        self.src = src
        self.import_map = import_map
        self.const_sql = const_sql
        self.const_db  = const_db

        self._stack: List[str] = []
        self.funcs: Set[str] = set()
        # caller -> (callee_module, callee_func, label)
        self.edges: Set[Tuple[str,str,str,Optional[str]]] = set()

        self.databases: Set[str] = set()
        self.db_edges: List[Tuple[str,str,Optional[str]]] = []

    def _current(self): return self._stack[-1] if self._stack else None

    def visit_FunctionDef(self, node: ast.FunctionDef):
        fn = f"{self.module}.{node.name}"
        self.funcs.add(fn)
        self._stack.append(fn)
        self.generic_visit(node)
        self._stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self.visit_FunctionDef(node)

    # ---- helpers ----
    def _resolve_call(self, node: ast.AST) -> Tuple[str,str]:
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            base = node.value.id; func = node.attr
            if base in self.import_map:
                return (self.import_map[base].split(".")[0], func)
            return (self.module, func)
        if isinstance(node, ast.Name):
            name = node.id
            if name in self.import_map:
                return (self.import_map[name].split(".")[0], name)
            return (self.module, name)
        return (self.module, "<call>")

    def _label_from_args(self, args: List[ast.AST]) -> Optional[str]:
        # Busca SQL en strings o en nombres constantes
        sql_label = None
        for a in args:
            v = None; db = None
            if isinstance(a, ast.Constant) and isinstance(a.value, str):
                v = a.value
            elif isinstance(a, ast.Name):
                if a.id in self.const_sql: sql_label = self.const_sql[a.id]
                if a.id in self.const_db:  self.databases.add(self.const_db[a.id])
            if v:
                m = SQL_RE.search(v)
                if m: sql_label = m.group(1).upper()
                m2 = DB_NAME_RE.search(v)
                if m2: self.databases.add(m2.group(1))
        return sql_label

    def _edge(self, caller: str, mod: str, func: str, label: Optional[str]):
        self.edges.add((caller, mod, func, label))

    def _edge_db(self, caller: str, db: str, op: Optional[str]):
        self.db_edges.append((caller, db, op))

    def _try_event_kwargs(self, caller: str, callnode: ast.Call, kwargs: List[ast.keyword]):
        # Button(..., on_release=self.generate_pdf)  / bind(on_release=self.go_back)
        for kw in kwargs:
            if not kw.arg: 
                continue
            if not kw.arg.startswith("on_"):
                continue
            target_mod, target_fn = None, None
            if isinstance(kw.value, ast.Attribute) and isinstance(kw.value.value, ast.Name):
                base = kw.value.value.id
                name = kw.value.attr
                target_mod = self.import_map.get(base, self.module).split(".")[0]
                target_fn  = name
            elif isinstance(kw.value, ast.Name):
                name = kw.value.id
                # from X import name
                target_mod = self.import_map.get(name, self.module).split(".")[0]
                target_fn  = name
            else:
                continue
            self._edge(caller, target_mod, target_fn, kw.arg)  # label: on_release/on_press

    def visit_Call(self, node: ast.Call):
        caller = self._current()
        if not caller:
            return

        callee_mod, callee_func = self._resolve_call(node.func)

        # sqlite3.connect("file.db")
        is_sqlite_connect = (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and callee_func == "connect"
            and self.import_map.get(node.func.value.id, "").startswith("sqlite3")
        )
        if is_sqlite_connect:
            # intenta leer "*.db" de args/kwargs
            for a in list(node.args) + [kw.value for kw in node.keywords]:
                if isinstance(a, ast.Constant) and isinstance(a.value, str):
                    m = DB_NAME_RE.search(a.value)
                    if m:
                        self.databases.add(m.group(1))

        # SQL label desde args (strings o constantes)
        sql_label = self._label_from_args(list(node.args) + [kw.value for kw in node.keywords])
        if sql_label and self.databases:
            for db in sorted(self.databases):
                self._edge_db(caller, db, sql_label)

        # callbacks Kivy en kwargs y en bind()
        if callee_func == "bind":
            self._try_event_kwargs(caller, node, node.keywords)
        else:
            # constructor Button(..., on_release=...)
            self._try_event_kwargs(caller, node, node.keywords)

        # arista normal
        self._edge(caller, callee_mod, callee_func, callee_func)
        self.generic_visit(node)

# ---------- IO / parse ----------
def _should_ignore(p: pathlib.Path) -> bool:
    return any(seg in IGNORE_DIRS for seg in p.parts)

def _iter_py_files(paths: Iterable[str], files: Iterable[str], no_recurse: bool):
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
        it = b.glob("*.py") if no_recurse else b.rglob("*.py")
        for p in it:
            if add(p): yield p
    if not paths and not files:
        for p in ROOT.rglob("*.py"):
            if add(p): yield p

def _parse_module(path: pathlib.Path):
    src = path.read_text(encoding="utf-8", errors="ignore")
    tree = ast.parse(src)
    mod = path.with_suffix("").name
    ir = ImportResolver(); ir.visit(tree)
    cc = ConstCollector(); cc.visit(tree)
    v = CallGraphVisitor(mod, src, ir.name_to_module, cc.sql_of, cc.db_of)
    v.visit(tree)
    entry = f"{mod}.__main__" if ("__name__" in src and "__main__" in src) else None
    return v, entry

# ---------- main ----------
def main():
    ap = argparse.ArgumentParser(description="Genera Mermaid (imports+DB+labels+callbacks+const SQL)")
    ap.add_argument("--paths", nargs="*", default=[])
    ap.add_argument("--files", nargs="*", default=[])
    ap.add_argument("--no_recurse", action="store_true")
    ap.add_argument("--modules", nargs="*", default=[])
    ap.add_argument("--exclude_mods", nargs="*", default=["generate_mermaid","generate_drawio","analyze_sql"])
    ap.add_argument("--hide_private", action="store_true")
    ap.add_argument("--inter_module_only", action="store_true")
    ap.add_argument("--include_db", action="store_true")
    ap.add_argument("--label_edges", action="store_true")
    ap.add_argument("--outfile", default="docs/flow.md")
    args = ap.parse_args()

    visitors: List[CallGraphVisitor] = []
    entries = set()
    for p in _iter_py_files(args.paths, args.files, args.no_recurse):
        try:
            v, entry = _parse_module(p)
            visitors.append(v)
            if entry: entries.add(entry)
        except Exception as ex:
            print(f"[WARN] {p}: {ex}")

    funcs = set().union(*(v.funcs for v in visitors))
    if args.modules:  funcs = {fn for fn in funcs if fn.split(".")[0] in set(args.modules)}
    if args.exclude_mods: funcs = {fn for fn in funcs if fn.split(".")[0] not in set(args.exclude_mods)}
    if args.hide_private: funcs = {fn for fn in funcs if not fn.split(".")[-1].startswith("_")}

    edges: Set[Tuple[str,str,str,Optional[str]]] = set()
    db_nodes: Set[str] = set()
    db_edges: List[Tuple[str,str,Optional[str]]] = []

    for v in visitors:
        for (caller, callee_mod, callee_fn, label) in v.edges:
            if caller in funcs:
                if args.inter_module_only and (caller.split(".")[0] == callee_mod):
                    continue
                edges.add((caller, callee_mod, callee_fn, label))
        if args.include_db:
            db_nodes |= v.databases
            for item in v.db_edges:
                if item[0] in funcs:
                    db_edges.append(item)

    by_mod = defaultdict(set)
    for fn in funcs: by_mod[fn.split(".")[0]].add(fn)

    out = (ROOT / args.outfile).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        f.write("# Diagrama de flujo (Mermaid)\n\n")
        f.write("%%{init: {'flowchart': {'curve':'basis','nodeSpacing':60,'rankSpacing':90}, 'themeVariables': {'fontSize':'18px'}} }%%\n")
        f.write("```mermaid\nflowchart TD\n")
        for mod in sorted(by_mod):
            f.write(f"  subgraph {mod}\n")
            for fn in sorted(by_mod[mod]):
                nid = fn.replace(".","_"); label = fn.split(".")[-1]+"()"
                f.write(f'    {nid}["{label}"]\n')
            f.write("  end\n")
        if args.include_db and db_nodes:
            f.write("  subgraph DATASOURCES\n")
            for db in sorted(db_nodes):
                dbid = "db_" + re.sub(r'[^A-Za-z0-9_]', '_', db)
                f.write(f'    {dbid}(["DB: {db}"])\n')
            f.write("  end\n")
        for en in sorted(entries):
            f.write(f'  {en.replace(".","_")}(["{en}"]):::entry\n')
        for caller, callee_mod, callee_fn, label in sorted(edges):
            sa = caller.replace(".","_"); sb = f"{callee_mod}_{callee_fn}"
            style = "-->" if caller.split(".")[0]==callee_mod else "-.->"
            if args.label_edges and label:
                f.write(f"  {sa} {style} |{label}| {sb}\n")
            else:
                f.write(f"  {sa} {style} {sb}\n")
        if args.include_db:
            for caller, db, op in db_edges:
                sa = caller.replace(".","_"); dbid = "db_" + re.sub(r'[^A-Za-z0-9_]', '_', db)
                lbl = f"|{op}|" if (args.label_edges and op) else ""
                f.write(f"  {sa} -.-> {lbl} {dbid}\n")
        f.write("classDef entry stroke-width:2px,stroke-dasharray:4 2;\n```\n")
    print(f"OK ➜ {out}")

if __name__ == "__main__":
    main()
