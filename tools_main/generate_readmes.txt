Novedades claves

Filtros de include/exclude:

--include: patrones glob a incluir (relativos a la raíz del proyecto).

--exclude: patrones glob adicionales a excluir.

Exclusiones por defecto (aunque no pases flags):

.git/**, **/.venv/**, venv/**, env/**

**/__pycache__/**, **/.mypy_cache/**, **/.pytest_cache/**

**/node_modules/**, **/.idea/**, **/.vscode/**

**/build/**, **/dist/**, **/site-packages/**

docs/** (evita reindexar lo generado)

gather_files(...) ahora respeta includes/excludes y evita entrar a carpetas peligrosas.


Cómo usarlo ahora (solo lo que tú quieras)

Solo tools_main/ y 3 archivos específicos, sin recursión:

python tools_main/generate_readmes.py \
  --paths tools_main \
  --files carrito.py historial.py tomar_pedido.py \
  --no_recurse \
  --docs-out docs --outfile-root README.md

  Solo la carpeta raíz pero incluyendo únicamente *.py de la raíz y tools_main/*.py:

python tools_main/generate_readmes.py \
  --paths . \
  --include "*.py" "tools_main/*.py" \
  --exclude "docs/**" ".venv/**" \
  --no_recurse \
  --docs-out docs


Explorar recursivo src/ pero excluyendo src/experimentos/**:

python tools_main/generate_readmes.py \
  --paths src \
  --include "src/**/*.py" \
  --exclude "src/experimentos/**" \
  --docs-out docs




python tools_main/generate_readmes.py \ --paths . \ --include "*.py" "tools_main/*.py" \ --exclude "docs/**" ".venv/**" \ --no_recurse \ --docs-out docs
