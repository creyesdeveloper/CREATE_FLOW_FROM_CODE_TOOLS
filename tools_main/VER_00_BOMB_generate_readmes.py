#!/usr/bin/env python3
"""
Generador de READMEs y docs por archivo.

Fase 1 (skeleton):
- CLI con argparse
- Recorre rutas/archivos (con/sin recursión)
- Extrae metadata vía AST: imports, funciones, clases, docstrings
- Renderiza README raíz y docs/<archivo>.md con plantillas Jinja2 si está disponible;
  si no, usa plantillas internas simples (fallback)
- Enlaza a diagramas drawio/mermaid y a sql_insights.md cuando existan

Uso rápido:
  python tools_main/generate_readmes.py \
    --paths . \
    --docs-out docs \
    --outfile-root README.md

  python tools_main/generate_readmes.py \
    --files tools_main/analyze_sql.py historial.py \
    --no_recurse \
    --docs-out docs \
    --outfile-root README.md

Requisitos opcionales:
  pip install jinja2
"""
from __future__ import annotations

import argparse
import ast
import dataclasses
import os
from pathlib import Path
from typing import Iterable, List, Optional, Tuple
from datetime import datetime

# -------------------------
# Modelos de datos
# -------------------------

@dataclasses.dataclass
class FunctionInfo:
    name: str
    lineno: int
    doc: Optional[str] = None

@dataclasses.dataclass
class ClassInfo:
    name: str
    lineno: int
    doc: Optional[str] = None
    methods: List[FunctionInfo] = dataclasses.field(default_factory=list)

@dataclasses.dataclass
class FileInfo:
    path: Path
    rel_path: str
    module: str
    doc: Optional[str]
    imports: List[str]
    functions: List[FunctionInfo]
    classes: List[ClassInfo]


# -------------------------
# Descubrimiento de archivos
# -------------------------

def gather_files(paths: Iterable[str], files: Iterable[str], recurse: bool) -> List[Path]:
    base = Path.cwd()
    found: List[Path] = []

    # Archivos explícitos
    for f in files:
        p = (base / f).resolve()
        if p.is_file() and p.suffix == ".py":
            found.append(p)

    # Rutas/directorios
    for p_str in paths:
        p = (base / p_str).resolve()
        if p.is_file() and p.suffix == ".py":
            found.append(p)
        elif p.is_dir():
            glob_pat = "**/*.py" if recurse else "*.py"
            found.extend(sorted(p.glob(glob_pat)))

    # Normalizar + únicos
    uniq = []
    seen = set()
    for p in found:
        if p.suffix != ".py":
            continue
        rp = str(p)
        if rp not in seen:
            seen.add(rp)
            uniq.append(p)
    return uniq


# -------------------------
# Parser AST
# -------------------------

def parse_python_file(path: Path, project_root: Path) -> FileInfo:
    rel_path = str(path.relative_to(project_root))
    module = path.stem
    text = path.read_text(encoding="utf-8", errors="ignore")
    try:
        tree = ast.parse(text)
    except SyntaxError as e:
        # Archivo inválido: devolvemos mínimos
        return FileInfo(
            path=path,
            rel_path=rel_path,
            module=module,
            doc=None,
            imports=[],
            functions=[],
            classes=[],
        )

    mod_doc = ast.get_docstring(tree)

    imports: List[str] = []
    functions: List[FunctionInfo] = []
    classes: List[ClassInfo] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                imports.append(n.name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            names = ", ".join(n.name for n in node.names)
            imports.append(f"from {mod} import {names}")
        elif isinstance(node, ast.FunctionDef):
            # Solo de primer nivel
            if isinstance(getattr(node, 'parent', None), ast.Module):
                functions.append(FunctionInfo(
                    name=node.name,
                    lineno=node.lineno,
                    doc=ast.get_docstring(node),
                ))
        elif isinstance(node, ast.ClassDef):
            if isinstance(getattr(node, 'parent', None), ast.Module):
                cls = ClassInfo(
                    name=node.name,
                    lineno=node.lineno,
                    doc=ast.get_docstring(node),
                )
                # métodos
                for b in node.body:
                    if isinstance(b, ast.FunctionDef):
                        cls.methods.append(FunctionInfo(
                            name=b.name,
                            lineno=b.lineno,
                            doc=ast.get_docstring(b),
                        ))
                classes.append(cls)

    # Añadir referencia al padre para distinguir nivel (pequeño truco)
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            setattr(child, 'parent', parent)

    return FileInfo(
        path=path,
        rel_path=rel_path,
        module=module,
        doc=mod_doc,
        imports=sorted(set(imports)),
        functions=sorted(functions, key=lambda f: f.lineno),
        classes=sorted(classes, key=lambda c: c.lineno),
    )


# -------------------------
# Plantillas (Jinja2 si disponible; fallback string)
# -------------------------

try:
    from jinja2 import Environment, FileSystemLoader, StrictUndefined
except Exception:  # pragma: no cover
    Environment = None  # type: ignore

DEFAULT_ROOT_TMPL = """# {{ project_title }}\n\n{{ project_desc }}\n\n- Generado: {{ now }}\n- Archivos analizados: {{ files|length }}\n\n## Índice de módulos\n{% for f in files %}- [{{ f.module }}]({{ docs_out }}/{{ f.module }}.md) — {{ f.rel_path }}\n{% endfor %}\n"""

DEFAULT_FILE_TMPL = """# {{ f.module }}\n\nRuta: `{{ f.rel_path }}`\n\n{% if f.doc %}> {{ f.doc | replace('\n', '\n> ') }}\n{% endif %}\n\n## Imports\n{% if f.imports %}{% for i in f.imports %}- `{{ i }}`\n{% endfor %}{% else %}_No se detectaron imports._\n{% endif %}\n\n## Funciones\n{% if f.functions %}{% for fn in f.functions %}- `{{ fn.name }}` (línea {{ fn.lineno }}){% if fn.doc %}: {{ fn.doc.split('\n')[0] }}{% endif %}\n{% endfor %}{% else %}_No se detectaron funciones de nivel módulo._\n{% endif %}\n\n## Clases\n{% if f.classes %}{% for c in f.classes %}- **{{ c.name }}** (línea {{ c.lineno }}){% if c.doc %}: {{ c.doc.split('\n')[0] }}{% endif %}\n  {% if c.methods %}  - Métodos:\n    {% for m in c.methods %}  - `{{ m.name }}` ({{ m.lineno }}){% if m.doc %}: {{ m.doc.split('\n')[0] }}{% endif %}\n    {% endfor %}{% endif %}\n{% endfor %}{% else %}_No se detectaron clases._\n{% endif %}\n\n## Diagramas\n{% if drawio %}- draw.io: `{{ drawio }}`{% else %}_No se encontró .drawio_\n{% endif %}\n{% if mermaid %}- Mermaid: `{{ mermaid }}`{% else %}_No se encontró .md (Mermaid)_\n{% endif %}\n\n## SQL relacionado\n{% if sql_anchor %}- Ver `{{ sql_file }}` → sección **{{ anchor_label }}**{% else %}_No se encontró referencia en sql_insights.md_\n{% endif %}\n"""


def load_env(template_root: Optional[Path]):
    if Environment and template_root and template_root.exists():
        return Environment(
            loader=FileSystemLoader(str(template_root)),
            autoescape=False,
        )
    return None


def render_root(env, context, template_name: Optional[str]) -> str:
    if env and template_name:
        return env.get_template(template_name).render(**context)
    # Fallback
    from string import Template
    # Usamos Jinja-like con reemplazos mínimos vía Template donde aplica
    return DEFAULT_ROOT_TMPL.replace("{{ project_title }}", context["project_title"]) \
        .replace("{{ project_desc }}", context["project_desc"]) \
        .replace("{{ now }}", context["now"]) \
        .replace("{{ docs_out }}", context["docs_out"]) \
        .replace("{{ files|length }}", str(len(context["files"]))) \
        .replace("{% for f in files %}", "").replace("{% endfor %}", "") \
        + "".join([f"- [{f.module}]({context['docs_out']}/{f.module}.md) — {f.rel_path}\n" for f in context["files"]])


def render_file(env, context, template_name: Optional[str]) -> str:
    if env and template_name:
        return env.get_template(template_name).render(**context)
    # Fallback: render muy simple por formato
    f = context["f"]
    lines = [f"# {f.module}\n", f"Ruta: `{f.rel_path}`\n\n"]
    if f.doc:
        lines.append("> " + f.doc.replace("\n", "\n> ") + "\n\n")
    # Imports
    lines.append("## Imports\n")
    if f.imports:
        for i in f.imports:
            lines.append(f"- `{i}`\n")
    else:
        lines.append("_No se detectaron imports._\n")
    lines.append("\n## Funciones\n")
    if f.functions:
        for fn in f.functions:
            head = f"- `{fn.name}` (línea {fn.lineno})"
            if fn.doc:
                head += f": {fn.doc.split('\n')[0]}"
            lines.append(head + "\n")
    else:
        lines.append("_No se detectaron funciones de nivel módulo._\n")
    lines.append("\n## Clases\n")
    if f.classes:
        for c in f.classes:
            head = f"- **{c.name}** (línea {c.lineno})"
            if c.doc:
                head += f": {c.doc.split('\n')[0]}"
            lines.append(head + "\n")
            if c.methods:
                lines.append("  - Métodos:\n")
                for m in c.methods:
                    mh = f"  - `{m.name}` ({m.lineno})"
                    if m.doc:
                        mh += f": {m.doc.split('\n')[0]}"
                    lines.append(mh + "\n")
    else:
        lines.append("_No se detectaron clases._\n")

    # Diagramas
    lines.append("\n## Diagramas\n")
    drawio = context.get("drawio")
    mermaid = context.get("mermaid")
    lines.append(f"- draw.io: `{drawio}`\n" if drawio else "_No se encontró .drawio_\n")
    lines.append(f"- Mermaid: `{mermaid}`\n" if mermaid else "_No se encontró .md (Mermaid)_\n")

    # SQL
    lines.append("\n## SQL relacionado\n")
    anchor = context.get("sql_anchor")
    if anchor:
        lines.append(f"- Ver `{context['sql_file']}` → sección **{context['anchor_label']}**\n")
    else:
        lines.append("_No se encontró referencia en sql_insights.md_\n")

    return "".join(lines)


# -------------------------
# Utilidades
# -------------------------

def guess_diagram_paths(docs_out: Path, module: str) -> Tuple[Optional[str], Optional[str]]:
    drawio = docs_out / f"flow_{module}.drawio"
    mermaid = docs_out / f"flow_{module}.md"
    return (
        str(drawio) if drawio.exists() else None,
        str(mermaid) if mermaid.exists() else None,
    )


def find_sql_anchor(sql_file: Path, module: str) -> Tuple[Optional[str], Optional[str]]:
    """Devuelve (anchor, label) si encuentra sección para el archivo en sql_insights.md"""
    if not sql_file.exists():
        return None, None
    try:
        text = sql_file.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None, None
    # Heurística: buscar encabezados como "## nombre.py" o "### nombre.py"
    for prefix in ("### ", "## "):
        tag = f"{prefix}{module}.py"
        idx = text.find(tag)
        if idx != -1:
            # Construimos un anchor compatible con GitHub (simplificado)
            anchor = tag.lower().replace(" ", "-").replace(".", "")
            label = f"{module}.py"
            return anchor, label
    return None, None


# -------------------------
# Render principal
# -------------------------

def render_project(
    files: List[FileInfo],
    project_root: Path,
    outfile_root: Path,
    docs_out: Path,
    template_root: Optional[Path],
    root_template: Optional[str],
    file_template: Optional[str],
) -> None:
    env = load_env(template_root)
    docs_out.mkdir(parents=True, exist_ok=True)

    # README raíz
    context_root = {
        "project_title": project_root.name.replace("_", " "),
        "project_desc": (
            "Documentación generada automáticamente a partir de código Python: "
            "diagramas, imports, funciones, clases y SQL relacionado."
        ),
        "now": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "docs_out": str(docs_out),
        "files": files,
    }
    root_md = render_root(env, context_root, root_template)
    outfile_root.write_text(root_md, encoding="utf-8")

    # Docs por archivo
    sql_file = docs_out / "sql_insights.md"
    for f in files:
        drawio, mermaid = guess_diagram_paths(docs_out, f.module)
        anchor, label = find_sql_anchor(sql_file, f.module)
        context_file = {
            "f": f,
            "drawio": drawio,
            "mermaid": mermaid,
            "sql_file": str(sql_file) if sql_file.exists() else None,
            "sql_anchor": anchor,
            "anchor_label": label,
        }
        text = render_file(env, context_file, file_template)
        (docs_out / f"{f.module}.md").write_text(text, encoding="utf-8")


# -------------------------
# CLI
# -------------------------

def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Genera README.md raíz y docs/<archivo>.md a partir de código Python",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--paths", nargs="*", default=["."], help="Directorios a analizar")
    p.add_argument("--files", nargs="*", default=[], help="Archivos .py específicos")
    p.add_argument("--no_recurse", action="store_true", help="No recorrer subdirectorios")
    p.add_argument("--outfile-root", default="README.md", help="Ruta del README raíz")
    p.add_argument("--docs-out", default="docs", help="Directorio de salida para docs")
    p.add_argument("--template-root", default=None, help="Directorio con plantillas Jinja2")
    p.add_argument("--root-template", default=None, help="Nombre de plantilla para README raíz (Jinja2)")
    p.add_argument("--file-template", default=None, help="Nombre de plantilla para docs por archivo (Jinja2)")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_argparser().parse_args(argv)

    project_root = Path.cwd()
    docs_out = (project_root / args.docs_out).resolve()
    outfile_root = (project_root / args.outfile_root).resolve()

    files = gather_files(args.paths, args.files, recurse=not args.no_recurse)
    if not files:
        print("No se encontraron archivos .py a analizar.")
        return 1

    parsed: List[FileInfo] = [parse_python_file(p, project_root) for p in files]

    template_root = Path(args.template_root) if args.template_root else None

    render_project(
        files=parsed,
        project_root=project_root,
        outfile_root=outfile_root,
        docs_out=docs_out,
        template_root=template_root,
        root_template=args.root_template,
        file_template=args.file_template,
    )

    print(f"✔ README generado en {outfile_root}")
    print(f"✔ Docs por archivo en {docs_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
