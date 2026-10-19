"""Rutas de carpetas del proyecto."""

from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent      # carpeta Programacion-Dinamica
SALIDAS = RAIZ / "salidas"                         # mapa, CSV y reportes generados
CACHE_OSM = Path(__file__).resolve().parent / "datos" / "ibague_calles.graphml"
