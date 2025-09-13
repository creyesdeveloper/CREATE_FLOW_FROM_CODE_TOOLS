#!/usr/bin/env bash
set -euxo pipefail   # <- activa trazas (-x) y errores estrictos

: "${INCLUDE_DB:=1}"
: "${LABEL_EDGES:=1}"
: "${HIDE_PRIVATE:=0}"
: "${COLS:=0}"
: "${LAYOUT:=sugi-lite}"
: "${RANK_ORIGIN:=in}"
: "${THEME:=midnight}"
: "${ARROW:=block}"
: "${EDGE_STYLE:=orthogonal}"
: "${LINE_JUMPS:=on}"
: "${SIZE_MODE:=degree}"
: "${LEGEND:=on}"
: "${GENERATE_MERMAID:=1}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

MERMAID="$ROOT/tools_main/generate_mermaid.py"
DRAWIO="$ROOT/tools_main/generate_drawio.py"
DOCS="$ROOT/docs"
mkdir -p "$DOCS"

TMP_DRAWIO="$DOCS/flow.drawio"   # <- nombre por defecto del script Python
TMP_MMD="$DOCS/flow.mmd"

drawio_flags=(
  --layout "$LAYOUT" --rank-origin "$RANK_ORIGIN"
  --theme "$THEME" --arrow "$ARROW" --edge-style "$EDGE_STYLE" --line-jumps "$LINE_JUMPS"
  --size-mode "$SIZE_MODE" --legend "$LEGEND" --cols "$COLS"
  --export drawio mermaid
)
mermaid_flags=()
(( INCLUDE_DB ))   && { drawio_flags+=( --include_db );   mermaid_flags+=( --include_db ); }
(( LABEL_EDGES ))  && { drawio_flags+=( --label_edges );  mermaid_flags+=( --label_edges ); }
(( HIDE_PRIVATE )) && { drawio_flags+=( --hide_private ); mermaid_flags+=( --hide_private ); }

FILES=()
if (( $# > 0 )); then
  FILES=("$@")
else
  while IFS= read -r f; do
    base="$(basename "$f")"
    [[ "$base" == generate_* ]] && continue
    [[ "$base" == analyze_sql.py ]] && continue
    [[ "$base" == _* ]] && continue
    FILES+=("$base")
  done < <(find "$ROOT" -maxdepth 1 -type f -name '*.py' | sort)
fi

echo "== Generando flujos para ${#FILES[@]} archivo(s) =="

for f in "${FILES[@]}"; do
  base="${f##*/}"; base="${base%.py}"
  echo "→ $f"

  # Limpia temporales para evitar confusiones
  rm -f "$TMP_DRAWIO" "$TMP_MMD"

  # 1) Mermaid por archivo (opcional)
  if (( GENERATE_MERMAID )); then
    python3 "$MERMAID" --files "$f" "${mermaid_flags[@]}" --outfile "$DOCS/flow_${base}.md"
    echo "   OK mermaid  ➜ $DOCS/flow_${base}.md"
  fi

  # 2) Draw.io: forzamos a que el script escriba su default y luego renombramos
  python3 "$DRAWIO" --files "$f" --no_recurse "${drawio_flags[@]}" --outfile "$TMP_DRAWIO" || true

  # Fallbacks: algunos builds ignoran --outfile y/o sólo crean drawio
  if [[ -f "$TMP_DRAWIO" ]]; then
    mv -f "$TMP_DRAWIO" "$DOCS/flow_${base}.drawio"
    echo "   OK draw.io  ➜ $DOCS/flow_${base}.drawio"
  elif [[ -f "$DOCS/flow.drawio" ]]; then
    mv -f "$DOCS/flow.drawio" "$DOCS/flow_${base}.drawio"
    echo "   OK draw.io  ➜ $DOCS/flow_${base}.drawio"
  else
    echo "   ⚠️  No se generó draw.io para $f (revisa la traza arriba)."
    exit 1
  fi

  # Si también quieres separar el .mmd del drawio.py, renómbralo si aparece
  if [[ -f "$TMP_MMD" ]]; then
    mv -f "$TMP_MMD" "$DOCS/flow_${base}.mmd"
  fi
done

echo "OK ✅  Archivos en: $DOCS"
