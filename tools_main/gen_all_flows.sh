#!/usr/bin/env bash
set -euo pipefail

# === Config rápida por variables de entorno (puedes cambiarlas al vuelo) ===
: "${INCLUDE_DB:=1}"        # 1 = dibuja nodos de DB y aristas SQL
: "${LABEL_EDGES:=1}"       # 1 = etiqueta aristas con nombre/SQL (Mermaid)
: "${HIDE_PRIVATE:=0}"      # 1 = oculta funciones que empiezan con "_"
: "${COLS:=3}"              # columnas por swimlane en draw.io

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

MERMAID="$ROOT/tools/generate_mermaid.py"
DRAWIO="$ROOT/tools/generate_drawio.py"
DOCS="$ROOT/docs"
mkdir -p "$DOCS"

# === Lista de archivos a procesar ===
# Si pasas archivos por argumento, usa esos. Si no, autodetecta los .py del proyecto (nivel raíz).
FILES=()
if (( $# > 0 )); then
  FILES=("$@")
else
  # Prioriza los módulos típicos de tu app; si no existen, cae a todos los .py del raíz.
  CANDIDATES=( login.py carrito.py historial.py pdf_pedido.py resumen_cliente.py tomar_pedido.py )
  for f in "${CANDIDATES[@]}"; do [[ -f "$f" ]] && FILES+=("$f"); done

  if (( ${#FILES[@]} == 0 )); then
    # Autodetección segura: raíz solamente, excluye herramientas/generadores y ocultos.
    while IFS= read -r f; do
      base="$(basename "$f")"
      [[ "$base" == generate_* ]] && continue
      [[ "$base" == analyze_sql.py ]] && continue
      [[ "$base" == _* ]] && continue
      FILES+=("$base")
    done < <(find "$ROOT" -maxdepth 1 -type f -name '*.py' | sort)
  fi
fi

# === Flags comunes construidos desde las variables ===
mermaid_flags=()
drawio_flags=( "--cols" "$COLS" )

(( INCLUDE_DB ))   && { mermaid_flags+=( "--include_db" ); drawio_flags+=( "--include_db" ); }
(( LABEL_EDGES ))  && { mermaid_flags+=( "--label_edges" ); drawio_flags+=( "--label_edges" ); }
(( HIDE_PRIVATE )) && { mermaid_flags+=( "--hide_private" ); drawio_flags+=( "--hide_private" ); }

echo "== Generando flujos para ${#FILES[@]} archivo(s) =="
for f in "${FILES[@]}"; do
  base="${f##*/}"; base="${base%.py}"
  echo "→ $f"

  # 1) Mermaid enriquecido por archivo
  python3 "$MERMAID" --files "$f" \
    "${mermaid_flags[@]}" \
    --outfile "$DOCS/flow_${base}.md"

  # 2) Draw.io (swimlanes, imports/DB/eventos) por archivo
  python3 "$DRAWIO" --files "$f" \
    "${drawio_flags[@]}" \
    --outfile "$DOCS/flow_${base}.drawio"
done

echo "OK ✅  Archivos en: $DOCS"
echo "Sugerencia: abre con draw.io el que quieras (p. ej. $DOCS/flow_historial.drawio) y ajusta layout."
