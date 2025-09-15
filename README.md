# 🧭 CREATE_FLOW_FROM_CODE_TOOLS

Genera **diagramas de flujo** (Draw.io + Mermaid) a partir de código **Python**, y además **analiza SQL** embebido en los scripts para documentarlo automáticamente.

- Lenguaje: **Python 3.13** (con `.venv`)
- Editor recomendado: **VSCode**
- SO de desarrollo: macOS (funciona también en Linux/Windows)
- Directorio de salidas: `docs/`

---

## 📑 Índice

- [🧭 CREATE\_FLOW\_FROM\_CODE\_TOOLS](#-create_flow_from_code_tools)
  - [📑 Índice](#-índice)
  - [🚀 Objetivo](#-objetivo)
  - [🧩 Componentes principales](#-componentes-principales)
  - [⚙️ Requisitos](#️-requisitos)
  - [🏁 Puesta en marcha](#-puesta-en-marcha)
- [1) Clonar](#1-clonar)
- [2) Crear y activar venv](#2-crear-y-activar-venv)
- [3) Actualizar pip y dependencias](#3-actualizar-pip-y-dependencias)
- [4) (una vez) dar permisos al .sh](#4-una-vez-dar-permisos-al-sh)
  - [🛠️ Uso de las herramientas](#️-uso-de-las-herramientas)
  - [analyze\_sql.py](#analyze_sqlpy)
  - [📂 Estructura del proyecto](#-estructura-del-proyecto)
  - [📄 Salidas en docs/](#-salidas-en-docs)
  - [🧰 Tips VSCode](#-tips-vscode)
  - [Troubleshootin🧯 Troubleshooting](#troubleshootin-troubleshooting)

---

## 🚀 Objetivo

- **Automatizar documentación técnica**:
  - Generar diagramas de flujo del código fuente: **.drawio** (para Draw.io) y **.md** (Mermaid).
  - Extraer y documentar **consultas SQL** detectadas en los scripts Python, agrupadas por archivo, con **índice navegable**.

---

## 🧩 Componentes principales

- `tools_main/generate_drawio.py`: analiza AST de Python y genera **.drawio** y/o **Mermaid**.
- `tools_main/generate_mermaid.py`: genera documentación **Mermaid** por archivo.
- `tools_main/gen_all_flows.sh`: **script de orquestación** para correr lo anterior con flags consistentes.
- `tools_main/analyze_sql.py`: recolecta **SQL** embebido en `.py` y crea `docs/sql_insights.md` con índice y secciones por archivo.

---

## ⚙️ Requisitos

- **Python 3.13**
- **Entorno virtual** (recomendado): `.venv`
- VSCode con extensiones:
  - *Python* (Microsoft)
  - *Pylance* (Microsoft)
  - (opcional) *Draw.io Integration*, *Mermaid Markdown*

---

## 🏁 Puesta en marcha

```bash
# 1) Clonar

    git clone https://github.com/creyesdeveloper/CREATE_FLOW_FROM_CODE_TOOLS.git
    cd CREATE_FLOW_FROM_CODE_TOOLS

# 2) Crear y activar venv

    python3.13 -m venv .venv
    source .venv/bin/activate          # macOS/Linux
    # .venv\Scripts\activate           # Windows (PowerShell: .venv\Scripts\Activate.ps1)

# 3) Actualizar pip y dependencias

    pip install -U pip setuptools wheel
    # Si se usa requirements:
    # pip install -r requirements.txt

# 4) (una vez) dar permisos al .sh

    chmod +x tools_main/gen_all_flows.sh

## 🛠️ Uso de las herramientas

generate_drawio.py / generate_mermaid.py (vía script .sh)

Desde la raíz del repo con el .venv activo:

    # Generar diagramas para UN archivo
    ./tools_main/gen_all_flows.sh carrito.py

    # Generar diagramas para varios
    ./tools_main/gen_all_flows.sh carrito.py historial.py tomar_pedido.py

    # Generar para todos los .py en la raíz
    ./tools_main/gen_all_flows.sh

Variables de entorno (opcional) — defaults actuales:

    INCLUDE_DB=1 LABEL_EDGES=1 HIDE_PRIVATE=0 COLS=0 \
    LAYOUT=sugi-lite RANK_ORIGIN=in THEME=midnight \
    ARROW=block EDGE_STYLE=orthogonal LINE_JUMPS=on \
    SIZE_MODE=degree LEGEND=on GENERATE_MERMAID=1 \
    ./tools_main/gen_all_flows.sh carrito.py

Salida esperada por cada archivo X.py:

    docs/flow_X.drawio

    docs/flow_X.md (Mermaid)

El .sh maneja fallbacks de --outfile y limpia temporales para evitar confusiones

## analyze_sql.py

    # Un archivo
    python3 tools_main/analyze_sql.py --files carrito.py

    # Varios archivos
    python3 tools_main/analyze_sql.py --files carrito.py historial.py tomar_pedido.py

    # Comodín del shell (todos los .py de la carpeta actual)
    python3 tools_main/analyze_sql.py --files *.py

    # Directorio(s) (recursivo por defecto)
    python3 tools_main/analyze_sql.py --paths .

    # Sin recursión
    python3 tools_main/analyze_sql.py --paths tools_main --no_recurse

    # Cambiar el archivo de salida
    python3 tools_main/analyze_sql.py --files carrito.py --outfile docs/sql_insights.md

Salida: docs/sql_insights.md


    - Índice clicable

    - Secciones por Archivo: "nombre.py"

    - Entradas ordenadas por línea, sin duplicados (línea, SQL)

    - Detalles: tipo (SELECT/INSERT/UPDATE/DELETE), tablas, campos, WHERE, ORDER BY, LIMIT

## 📂 Estructura del proyecto

    CREATE_FLOW_FROM_CODE_TOOLS/
    ├─ tools_main/
    │  ├─ generate_drawio.py
    │  ├─ generate_mermaid.py
    │  ├─ analyze_sql.py
    │  └─ gen_all_flows.sh
    ├─ docs/
    │  ├─ flow_*.drawio
    │  ├─ flow_*.md
    │  └─ sql_insights.md
    ├─ carrito.py
    ├─ historial.py
    ├─ tomar_pedido.py
    └─ .venv/ (no versionado)

## 📄 Salidas en docs/

    Diagramas: flow_<archivo>.drawio y flow_<archivo>.md (Mermaid)

    SQL: sql_insights.md con índice y secciones por archivo

## 🧰 Tips VSCode

        - Seleccionar intérprete: Cmd+Shift+P → Python: Select Interpreter → ./.venv/bin/python

        - Reiniciar servidor de análisis: Cmd+Shift+P → Python: Restart Language Server

        - Preview Markdown:

            Lateral: ⇧⌘V

            Mismo editor: ⌘K luego V


## Troubleshootin🧯 Troubleshooting

- No se activó el venv: confirma which python apunta a .../.venv/bin/python.

- “command not found” con el .sh: asegúrate de estar en la raíz y haber corrido chmod +x.

- No aparece flow_<archivo>.drawio: revisa la traza del .sh; puede quedar temporal en docs/flow.drawio (el script lo mueve).

- El shell intenta “ejecutar” nombres de archivo: pon todos los nombres en una sola línea:

    python3 tools_main/analyze_sql.py --files carrito.py historial.py tomar_pedido.py

##👨‍💻 Autor

Carlos Reyes Bustamante — asistido por ChatGPT


