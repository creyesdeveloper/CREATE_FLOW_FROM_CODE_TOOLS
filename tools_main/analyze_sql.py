#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Extrae consultas SQL desde archivos Python y genera docs/sql_insights.md
agrupadas por archivo, con Índice navegable al inicio.

Uso:
  # Solo raíz (recursivo por defecto)
  python3 tools_main/analyze_sql.py

  # Directorio específico sin bajar a subdirectorios
  python3 tools_main/analyze_sql.py --paths . --no_recurse

  # Solo archivos indicados
  python3 tools_main/analyze_sql.py --files historial.py carrito.py

  # Cambiar archivo de salida
  python3 tools_main/analyze_sql.py --outfile docs/sql_insights.md
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
    s = sql.strip("\n")
    s = s.replace("\t", "    ")
    return s

def _split_fields(fields_blob: str) -> List[str]:
    raw = [x.strip() for x in fields_blob.split(",")]
    return [re.sub(r"\s+", " ", f) for f in raw if f]

def classify_and_summarize(sql: str) -> Dict[str, object]:
    """
    Devuelve:
      {
        "type": "Lectura (SELECT)" | "Escritura (INSERT)" | "Actualización (UPDATE)" | "Eliminación (DELETE)",
        "tables": ["t1","t2",...],
        "fields": ["f1","f2",...],
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
        t = RE_FROM_TABLES.findall(sql)
        j = RE_JOIN_TABLES.findall(sql)
        tables = [*t, *j]
    elif kind and "INSERT" in kind:
        tables = RE_INSERT_TABLE.findall(sql)
    elif kind and "UPDATE" in kind:
        tables = RE_UPDATE_TABLE.findall(sql)
    elif kind and "DELETE" in kind:
        tables = RE_DELETE_TABLE.findall(sql)

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

    # helpers para obtener string de nodos
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
        return None

    def _maybe_record(self, s: Optional[str], lineno: int):
        if not s: return
        if SQL_RE.search(s):
            self.results.append((s, lineno))

    # visit
    def visit_Assign(self, node: ast.Assign):
        # constantes con SQL: SQL_SELECT = "SELECT ..."
        s = self._const_str(node.value)
        if s and SQL_RE.search(s):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    self.const_map[t.id] = s
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        # cursor.execute("SELECT ...") o execute(SQL_SELECT)
        if node.args:
            s = self._const_str(node.args[0])
            if s is None and isinstance(node.args[0], ast.Name):
                s = self.const_map.get(node.args[0].id)
            self._maybe_record(s, getattr(node, "lineno", 1))
        # keyword args (ej. query=...)
        for kw in node.keywords or []:
            s = self._const_str(kw.value)
            if s is None and isinstance(kw.value, ast.Name):
                s = self.const_map.get(kw.value.id)
            self._maybe_record(s, getattr(node, "lineno", 1))
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant):
        # fallback: cualquier string literal con SQL
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

# ---------- Rendering agrupado ----------

def _slugify(s: str) -> str:
    """Slug simple para anchors GitHub-like."""
    s = s.lower()
    s = re.sub(r"[^\w\s-]", "", s)   # quita símbolos (.,",etc.)
    s = re.sub(r"\s+", "-", s.strip())
    s = re.sub(r"-+", "-", s)
    return s

def render_entry_block(lineno: int, sql: str) -> str:
    """Bloque de una consulta (misma forma de hoy), sin repetir cabecera de archivo."""
    sql_block = _clean_sql_for_block(sql)
    info = classify_and_summarize(sql_block)

    lines: List[str] = []
    lines.append(f"**Línea {lineno}**")
    lines.append("")
    lines.append("```sql")
    lines.append(sql_block)
    lines.append("```")
    lines.append("")
    lines.append(f"- Tipo: **{info['type']}**")

    if info["tables"]:
        tbls = ", ".join(info["tables"]) # type: ignore
        lines.append(f"- Tabla(s): **{tbls}**")

    fields = [f for f in info["fields"] if f != "*"] # type: ignore
    if fields:
        lines.append(f"- Campos: {', '.join(fields)}")

    if info["where"]:
        lines.append(f"- Filtro: `{info['where']}`")

    if info["has_order"]:
        lines.append(f"- Ordena resultados con **ORDER BY**.")
    if info["has_limit"]:
        lines.append(f"- Limita cantidad de filas con **LIMIT**.")

    return "\n".join(lines)

def render_file_section(relpath: pathlib.Path, entries: List[Tuple[int, str]]) -> str:
    """Sección completa para un archivo con sus consultas."""
    fname = relpath.as_posix()
    anchor = _slugify(fname)  # para el índice
    lines: List[str] = []
    lines.append("------------------------------------------------------------------------")
    lines.append(f'## Archivo: "{fname}"')
    lines.append(f'<a id="{anchor}"></a>')
    lines.append("")
    for i, (ln, sql) in enumerate(entries, 1):
        if i > 1:
            lines.append("")         # respiro
            lines.append("---")      # separador suave entre consultas
            lines.append("")
        lines.append(render_entry_block(ln, sql))
    lines.append("")  # cierre
    return "\n".join(lines)

# ---------- Main ----------

def main():
    ap = argparse.ArgumentParser(description="Extrae consultas SQL desde .py y genera docs/sql_insights.md")
    ap.add_argument("--paths", nargs="*", default=[], help="Directorios a escanear")
    ap.add_argument("--files", nargs="*", default=[], help="Archivos .py específicos")
    ap.add_argument("--no_recurse", action="store_true", help="No descender a subdirectorios")
    ap.add_argument("--outfile", default=str(DOCS / "sql_insights.md"))
    args = ap.parse_args()

    # Mapa: archivo_rel -> set de (lineno, sql) para deduplicar
    per_file: Dict[pathlib.Path, Dict[Tuple[int, str], None]] = {}

    for p in iter_py_files(args.paths, args.files, args.no_recurse):
        rel = p.relative_to(ROOT)
        bucket = per_file.setdefault(rel, {})
        for sql, ln in extract_from_file(p):
            sql_block = _clean_sql_for_block(sql)
            bucket[(ln, sql_block)] = None  # dedup exacto por (línea, sql)

    out = pathlib.Path(args.outfile)
    out.parent.mkdir(parents=True, exist_ok=True)

    header = [
        "# Consultas SQL detectadas",
        "",
        f"_Proyecto_: {ROOT.name}",
        "",
    ]

    if not per_file:
        content = "\n".join(header + ["*(no se detectaron consultas)*"])
        out.write_text(content, encoding="utf-8")
        print(f"OK ➜ {out}")
        return

    # Índice
    files_sorted = sorted(per_file.keys(), key=lambda p: p.as_posix())
    index_lines: List[str] = []
    index_lines.append("## Índice")
    index_lines.append("")
    for i, rel in enumerate(files_sorted, 1):
        anchor = _slugify(rel.as_posix())
        index_lines.append(f"{i}. [Archivo: \"{rel.name}\"](#${anchor})")
    index_lines.append("")
    index_lines.append("---")
    index_lines.append("")

    # Secciones por archivo
    body_sections: List[str] = []
    for rel in files_sorted:
        entries_sorted = sorted(per_file[rel].keys(), key=lambda x: x[0])  # por línea
        body_sections.append(render_file_section(rel, entries_sorted))

    content = "\n".join(header + index_lines + body_sections)
    out.write_text(content, encoding="utf-8")
    print(f"OK ➜ {out}")

if __name__ == "__main__":
    main()
