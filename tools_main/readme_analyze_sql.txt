
Creado por : Carlos Reyes Bustamamante + ChatGPT


Requiere framework sqlparse (pip install sqlparse)


Como funciona?

    1.Recorre tu repo buscando .py

    2.Detecta cadenas que parecen SQL (SELECT/INSERT/UPDATE/DELETE)

    3.Identifica tablas, columnas básicas y condiciones

    4.Genera docs/sql_insights.md con:

    5.Ruta del archivo y línea

    6.SQL formateado

    7.Explicación en lenguaje humano (español)

Que se hace post ejecución de este script?

    1.Se revisa el contenido generado manualmente y se corrigen inconsistencias

    2.Aprobado el contenido, se integra a documentación general.

USO DE ESTE SCRIPT

# 1) Escanear solo la raíz del repo (recursivo)
python3 tools/analyze_sql.py

# 2) Escanear únicamente archivos propios
python3 tools/analyze_sql.py --files carrito.py historial.py

# 3) Escanear una ruta SIN BAJAR a subdirectorios
python3 tools/analyze_sql.py --paths . --no_recurse

# 4) Cambiar el archivo de salida
python3 tools/analyze_sql.py --files carrito.py --outfile docs/sql_insights.md
