Opción 1: Todo en una sola línea (más simple y seguro):


Solo la carpeta raíz pero incluyendo únicamente *.py de la raíz y tools_main/*.py:

python3 tools_main/generate_readmes.py --paths . \
  --include "*.py" "tools_main/*.py" \
  --exclude "docs/**" ".venv/**" \
  --no_recurse \
  --docs-out docs


Solo tools_main/ y 3 archivos específicos, sin recursión:

python3 tools_main/generate_readmes.py \
  --paths tools_main \
  --files carrito.py historial.py tomar_pedido.py \
  --no_recurse \
  --docs-out docs --outfile-root README.md

Explorar recursivo src/ pero excluyendo src/experimentos/**:

python tools_main/generate_readmes.py \
  --paths src \
  --include "src/**/*.py" \
  --exclude "src/experimentos/**" \
  --docs-out docs



