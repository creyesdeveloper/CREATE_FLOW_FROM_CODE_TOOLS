# respaldo_funcionando_de analyze_sql
Ruta: `tools_main/respaldo_funcionando_de analyze_sql.py`

> Extrae consultas SQL desde archivos Python y genera docs/sql_insights.md
> con un formato estilo ficha por cada hallazgo.
> 
> Uso:
>   # Solo raíz (recursivo por defecto)
>   python3 tools/analyze_sql.py
> 
>  # Directorio específico sin bajar a subdirectorios
>   python3 tools/analyze_sql.py --paths . --no_recurse
> 
>   # Solo archivos indicados
>   python3 tools/analyze_sql.py --files historial.py carrito.py
> 
>   # Solo en estas rutas (sin recorrer subdirectorios)
>   python3 tools/analyze_sql.py --paths . --no_recurse
> 
>   # Cambiar archivo de salida
>   python3 tools/analyze_sql.py --outfile docs/sql_insights.md

## Imports
- `argparse`
- `ast`
- `from __future__ import annotations`
- `from typing import Iterable, List, Tuple, Dict, Optional`
- `pathlib`
- `re`

## Funciones
_No se detectaron funciones de nivel módulo._

## Clases
_No se detectaron clases._

## Diagramas
_No se encontró .drawio_
_No se encontró .md (Mermaid)_

## SQL relacionado
_No se encontró referencia en sql_insights.md_
