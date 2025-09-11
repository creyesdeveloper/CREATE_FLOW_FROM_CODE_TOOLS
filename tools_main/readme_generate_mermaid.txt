Diagrama de flujo automático del app (Mermaid)

He optado por Mermaid pues lo considero ideal ya que:

    1.Se visualiza dentro de Markdown (docs/flow.md)

    2.VS Code lo previsualiza de inmediato

    3.Si luego necesitas draw.io, puedes abrir el .md y recrearlo en draw.io o usar su plugin mermaid.

Qué hace este script?

    1.Recorre tus .py

    2.Construye un grafo simple de llamadas (función→función) y puntos de entrada

    3.Emite docs/flow.md con un flowchart Mermaid

NOTA, Filosofía KISS: Este sctipt, no intenta comprender toda la lógica; te da un esqueleto editable.

Como se usa?

    1.En la terminal:
        python3 tools/generate_mermaid.py

    2.Luego Abre docs/flow.md en VS Code: verás el diagrama (Mermaid preview)
