# RESPALDO_generate_drawio
Ruta: `RESPALDO_generate_drawio.py`

> generate_drawio.py — v3.2 (limpio y estable)
> 
> - Analiza 1+ archivos .py (usado per-file por gen_all_flows.sh).
> - Nodos = funciones (incluye métodos de clase).
> - Edges f->f y f->DB (SQLite) con labels de SQL (SELECT/INSERT/UPDATE/DELETE).
> - Lane por módulo + lane DATASOURCES a la derecha.
> - Resalta en rojo nodos que tocan DB.
> - Layout sugiyama-lite sencillo (por columnas).
> - Exporta draw.io y opcionalmente Mermaid.
> 
> Uso típico (desde la raíz del repo):
>   python3 tools_main/generate_drawio.py --files carrito.py --include_db     --layout sugi-lite --rank-origin in --theme midnight --arrow block     --edge-style orthogonal --line-jumps on --size-mode degree --legend on     --cols 0 --export drawio mermaid --outfile docs/flow.drawio

## Imports
- `argparse`
- `ast`
- `from __future__ import annotations`
- `from collections import defaultdict`
- `from collections import defaultdict, deque`
- `from typing import Dict, Iterable, List, Optional, Set, Tuple`
- `html`
- `math`
- `pathlib`
- `re`
- `time`

## Funciones
_No se detectaron funciones de nivel módulo._

## Clases
_No se detectaron clases._

## Diagramas
_No se encontró .drawio_
_No se encontró .md (Mermaid)_

## SQL relacionado
_No se encontró referencia en sql_insights.md_
