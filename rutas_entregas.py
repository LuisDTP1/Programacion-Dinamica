"""
Ruteo de entregas en Ibagué con grafos — punto de entrada.

Ejecute este archivo desde la carpeta del proyecto:

    python rutas_entregas.py
    python rutas_entregas.py --clientes 24 --semilla 7 --salida 07:30
    python rutas_entregas.py --help

El código está en la carpeta entregas/ y los resultados (mapa, CSV) se
guardan en la carpeta salidas/.
"""

from entregas.principal import main

if __name__ == "__main__":
    main()
