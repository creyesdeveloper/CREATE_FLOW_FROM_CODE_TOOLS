#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Extrae consultas SQL desde archivos Python y genera docs/sql_insights.md
con un formato estilo ficha por cada hallazgo.

Uso:
  # Solo raíz (recursivo por defecto)
  python3 tools/analyze_sql.py

 # Directorio específico sin bajar a subdirectorios
  python3 tools/analyze_sql.py --paths . --no_recurse

  # Solo archivos indicados
  python3 tools/analyze_sql.py --files historial.py carrito.py

  # Solo en estas rutas (sin recorrer subdirectorios)
  python3 tools/analyze_sql.py --paths . --no_recurse

  # Cambiar archivo de salida
  python3 tools/analyze_sql.py --outfile docs/sql_insights.md



"""
from __future__ import annotations
import argparse
import ast
import pathlib
import re
from typing import Iterable, List, Tuple, Dict, Optional

ROOT = pathlib.Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
DOCS.mkdir(exist_ok=True)

IGNORE_DIRS = {
    ".venv","venv","__pycache__","build","dist",".buildozer","jni","external",
    ".git",".idea",".vscode","site-packages"
}

SQL_RE = re.compile(r"(?is)\b(SELECT|INSERT|UPDATE|DELETE)\b")
# capturas simples (heurísticas útiles y robustas para nuestra doc)
RE_SELECT_FIELDS = re.compile(r"(?is)\bSELECT\b(.*?)\bFROM\b")
RE_FROM_TABLES   = re.compile(r"(?is)\bFROM\b\s+([A-Za-z0-9_]+)")
RE_JOIN_TABLES   = re.compile(r"(?is)\bJOIN\b\s+([A-Za-z0-9_]+)")
RE_INSERT_TABLE  = re.compile(r"(?is)\bINSERT\s+INTO\b\s+([A-Za-z0-9_]+)")
RE_UPDATE_TABLE  = re.compile(r"(?is)\bUPDATE\b\s+([A-Za-z0-9_]+)")
RE_DELETE_TABLE  = re.compile(r"(?is)\bDELETE\s+FROM\b\s+([A-Za-z0-9_]+)")
RE_WHERE         = re.compile(r"(?is)\bWHERE\b(.*?)(?:\bGROUP\b|\bORDER\b|\bLIMIT\b|$)")
RE_ORDER_BY      = re.compile(r"(?is)\bORDER\s+BY\b")
RE_LIMIT         = re.compile(r"(?is)\bLIMIT\b")

def _should_ignore(path: pathlib.Path) -> bool:
    return any(seg in IGNORE_DIRS for seg in path.parts)

def iter_py_files(paths: Iterable[str], files: Iterable[str], no_recurse: bool) -> Iterable[pathlib.Path]:
    seen: set[pathlib.Path] = set()

    def add(p: pathlib.Path) -> bool:
        if p.suffix == ".py" and not _should_ignore(p) and p not in seen:
            seen.add(p); return True
        return False

    # explicit files
    for f in files:
        p = (ROOT / f).resolve()
        if p.is_file() and add(p):
            yield p

    # directories
    for d in paths:
        base = (ROOT / d).resolve()
        if not base.exists(): continue
        it = base.glob("*.py") if no_recurse else base.rglob("*.py")
        for p in it:
            if add(p): yield p

    # default: whole repo
    if not paths and not files:
        for p in ROOT.rglob("*.py"):
            if add(p): yield p

def _clean_sql_for_block(sql: str) -> str:
    """Normaliza espacios y sangrías, pero sin reescribir SQL."""
    # Strip bordes, preservar saltos
    s = sql.strip("\n")
    # Normaliza tabs → 4 espacios para mejor render
    s = s.replace("\t", "    ")
    return s

def _prefix_block(text: str, prefix: str) -> str:
    """Prepend prefix to each line."""
    return "\n".join(prefix + line for line in text.splitlines())

def _split_fields(fields_blob: str) -> List[str]:
    raw = [x.strip() for x in fields_blob.split(",")]
    # Filtra vacíos y normaliza espacios múltiples
    return [re.sub(r"\s+", " ", f) for f in raw if f]

def classify_and_summarize(sql: str) -> Dict[str, object]:
    """
    Devuelve:
      {
        "type": "Lectura (SELECT)" | "Escritura (INSERT)" | "Actualización (UPDATE)" | "Eliminación (DELETE)",
        "tables": ["t1","t2",...],
        "fields": ["f1","f2",...],   # solo para SELECT si es razonable detectarlos
        "where": "condición ..." | None,
        "has_order": bool,
        "has_limit": bool,
      }
    """
    kind = None
    m = SQL_RE.search(sql)
    if m:
        kw = m.group(1).upper()
        if kw == "SELECT": kind = "Lectura (SELECT)"
        elif kw == "INSERT": kind = "Escritura (INSERT)"
        elif kw == "UPDATE": kind = "Actualización (UPDATE)"
        elif kw == "DELETE": kind = "Eliminación (DELETE)"

    tables: List[str] = []
    fields: List[str] = []
    where: Optional[str] = None

    if kind and "SELECT" in kind:
        mf = RE_SELECT_FIELDS.search(sql)
        if mf:
            fields = _split_fields(mf.group(1))
        # tablas FROM/JOIN
        t = RE_FROM_TABLES.findall(sql)
        j = RE_JOIN_TABLES.findall(sql)
        tables = [*t, *j]
    elif kind and "INSERT" in kind:
        ti = RE_INSERT_TABLE.findall(sql)
        tables = ti
    elif kind and "UPDATE" in kind:
        tu = RE_UPDATE_TABLE.findall(sql)
        tables = tu
    elif kind and "DELETE" in kind:
        td = RE_DELETE_TABLE.findall(sql)
        tables = td

    mw = RE_WHERE.search(sql)
    if mw:
        where = re.sub(r"\s+", " ", mw.group(1).strip())

    has_order = bool(RE_ORDER_BY.search(sql))
    has_limit = bool(RE_LIMIT.search(sql))

    return {
        "type": kind or "Consulta SQL",
        "tables": tables,
        "fields": fields,
        "where": where,
        "has_order": has_order,
        "has_limit": has_limit,
    }

# ---------- AST-based extraction ----------

class SQLCollector(ast.NodeVisitor):
    """Recoge (sql_text, lineno) encontrados en un módulo."""
    def __init__(self, source: str):
        self.source = source
        self.const_map: Dict[str, str] = {}   # nombre -> sql string
        self.results: List[Tuple[str, int]] = []

    # ---------- helpers para obtener string de nodos ----------
    def _const_str(self, node: ast.AST) -> Optional[str]:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.JoinedStr):
            # f-strings: concatenamos las partes literales y dejamos {expr} como ?
            parts = []
            for v in node.values:
                if isinstance(v, ast.FormattedValue):
                    parts.append("?")
                elif isinstance(v, ast.Constant) and isinstance(v.value, str):
                    parts.append(v.value)
            return "".join(parts)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            a = self._const_str(node.left)
            b = self._const_str(node.right)
            if a is not None and b is not None:
                return a + b
        return None

    def _maybe_record(self, s: Optional[str], lineno: int):
        if not s: return
        if SQL_RE.search(s):
            self.results.append((s, lineno))

    # ---------- visit ----------
    def visit_Assign(self, node: ast.Assign):
        # Captura constantes con SQL: SQL_SELECT = "SELECT ..."
        s = self._const_str(node.value)
        if s and SQL_RE.search(s):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    self.const_map[t.id] = s
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        # Busca cursor.execute("SELECT ...") o execute(SQL_SELECT)
        # Primer argumento relevante
        if node.args:
            s = self._const_str(node.args[0])
            if s is None and isinstance(node.args[0], ast.Name):
                s = self.const_map.get(node.args[0].id)
            self._maybe_record(s, getattr(node, "lineno", 1))
        # También revisa keyword args (por si usan 'query=...')
        for kw in node.keywords or []:
            s = self._const_str(kw.value)
            if s is None and isinstance(kw.value, ast.Name):
                s = self.const_map.get(kw.value.id)
            self._maybe_record(s, getattr(node, "lineno", 1))
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant):
        # Como fallback, cualquier literal string que contenga SQL
        if isinstance(node.value, str) and SQL_RE.search(node.value):
            self.results.append((node.value, getattr(node, "lineno", 1)))
        # no generic_visit para constants

def extract_from_file(path: pathlib.Path) -> List[Tuple[str, int]]:
    src = path.read_text(encoding="utf-8", errors="ignore")
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []
    col = SQLCollector(src)
    col.visit(tree)
    return col.results

# ---------- Rendering ----------

def render_entry(relpath: pathlib.Path, lineno: int, sql: str) -> str:
    sql_block = _clean_sql_for_block(sql)
    info = classify_and_summarize(sql_block)

    # Construir cuerpo de resumen
    lines: List[str] = []
    lines.append("------------------------------------------------------------------------")
    lines.append(f" ## {relpath.as_posix()}")
    lines.append("")
    lines.append(f"**Línea {lineno}**")
    lines.append("")
    lines.append("```sql")
    lines.append(sql_block)
    lines.append("```")
    lines.append("")

    # Tipo
    lines.append(f"- Tipo: **{info['type']}**")

    # Tablas
    if info["tables"]:
        tbls = ", ".join(info["tables"])
        lines.append(f"- Tabla(s): **{tbls}**")

    # Campos (solo si hay y no es '*')
    fields = [f for f in info["fields"] if f != "*"]
    if fields:
        lines.append(f"- Campos: {', '.join(fields)}")

    # Filtro WHERE
    if info["where"]:
        lines.append(f"- Filtro: `{info['where']}`")

    # ORDER BY / LIMIT
    if info["has_order"]:
        lines.append(f"- Ordena resultados con **ORDER BY**.")
    if info["has_limit"]:
        lines.append(f"- Limita cantidad de filas con **LIMIT**.")

    lines.append("")
    lines.append("------------------------------------------------------------------------")
    return "\n".join(lines)

# ---------- Main ----------

def main():
    ap = argparse.ArgumentParser(description="Extrae consultas SQL desde .py y genera docs/sql_insights.md")
    ap.add_argument("--paths", nargs="*", default=[], help="Directorios a escanear")
    ap.add_argument("--files", nargs="*", default=[], help="Archivos .py específicos")
    ap.add_argument("--no_recurse", action="store_true", help="No descender a subdirectorios")
    ap.add_argument("--outfile", default=str(DOCS / "sql_insights.md"))
    args = ap.parse_args()

    found: List[str] = []
    for p in iter_py_files(args.paths, args.files, args.no_recurse):
        rel = p.relative_to(ROOT)
        for sql, ln in extract_from_file(p):
            found.append(render_entry(rel, ln, sql))

    out = pathlib.Path(args.outfile)
    out.parent.mkdir(parents=True, exist_ok=True)
    header = [
        "# Consultas SQL detectadas",
        "",
        f"_Proyecto_: {ROOT.name}",
        ""
    ]
    content = "\n".join(header + (found if found else ["*(no se detectaron consultas)*"]))
    out.write_text(content, encoding="utf-8")
    print(f"OK ➜ {out}")

if __name__ == "__main__":
    main()
