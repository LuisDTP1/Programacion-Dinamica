"""
Grafo ponderado con lista de adyacencia y algoritmo de DIJKSTRA.

Cada arco guarda dos magnitudes:
    km   -> longitud del tramo
    kmh  -> velocidad promedio del tramo
de modo que el mismo grafo sirve para minimizar DISTANCIA (peso = km) o
TIEMPO (peso = km / kmh * 60 minutos). Dijkstra funciona igual en ambos
casos porque los pesos son siempre no negativos.
"""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Arco:
    destino: int
    km: float
    kmh: float
    via: str

    @property
    def minutos(self) -> float:
        return self.km / self.kmh * 60

    def peso(self, criterio: str) -> float:
        return self.km if criterio == "distancia" else self.minutos


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia sobre la superficie terrestre entre dos coordenadas."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


class Grafo:
    def __init__(self) -> None:
        self.ady: dict[int, list[Arco]] = {}
        self.pos: dict[int, tuple[float, float]] = {}   # nodo -> (lat, lon)
        self.nombre: dict[int, str] = {}
        self.comuna: dict[int, str] = {}

    # ------------------------------------------------------------------
    def agregar_nodo(self, n: int, lat: float, lon: float,
                     nombre: str | None = None, comuna: str | None = None) -> None:
        self.ady.setdefault(n, [])
        self.pos[n] = (lat, lon)
        if nombre:
            self.nombre[n] = nombre
        if comuna:
            self.comuna[n] = comuna

    def agregar_arco(self, u: int, v: int, km: float, kmh: float, via: str,
                     doble_sentido: bool = True) -> None:
        self.ady[u].append(Arco(v, km, kmh, via))
        if doble_sentido:
            self.ady[v].append(Arco(u, km, kmh, via))

    @property
    def num_nodos(self) -> int:
        return len(self.ady)

    @property
    def num_arcos(self) -> int:
        return sum(len(a) for a in self.ady.values())

    # ------------------------------------------------------------------
    def dijkstra(self, origen: int, criterio: str = "tiempo"):
        """Caminos mínimos desde `origen`.

        Devuelve:
            costo[v]  -> costo mínimo (km o minutos) de origen a v
            previo[v] -> (u, arco) usado para llegar a v en el camino mínimo

        Complejidad: O((V + E) log V) con un montículo binario (heapq).
        """
        costo = {origen: 0.0}
        previo: dict[int, tuple[int, Arco]] = {}
        heap = [(0.0, origen)]
        visitados = set()
        while heap:
            c, u = heapq.heappop(heap)
            if u in visitados:
                continue            # entrada vieja del heap
            visitados.add(u)
            for arco in self.ady[u]:
                nc = c + arco.peso(criterio)
                if nc < costo.get(arco.destino, math.inf):
                    costo[arco.destino] = nc
                    previo[arco.destino] = (u, arco)
                    heapq.heappush(heap, (nc, arco.destino))
        return costo, previo

    @staticmethod
    def reconstruir(previo: dict, origen: int, destino: int) -> list[tuple[int, int, Arco]]:
        """Lista de tramos (u, v, arco) del camino mínimo origen -> destino."""
        tramos = []
        v = destino
        while v != origen:
            u, arco = previo[v]
            tramos.append((u, v, arco))
            v = u
        return tramos[::-1]

    # ------------------------------------------------------------------
    def alcanzables(self, origen: int) -> set[int]:
        """BFS: nodos a los que se puede llegar desde `origen`."""
        vistos, pila = {origen}, [origen]
        while pila:
            u = pila.pop()
            for a in self.ady[u]:
                if a.destino not in vistos:
                    vistos.add(a.destino)
                    pila.append(a.destino)
        return vistos

    def invertido(self) -> "Grafo":
        g = Grafo()
        for n, (lat, lon) in self.pos.items():
            g.agregar_nodo(n, lat, lon)
        for u, arcos in self.ady.items():
            for a in arcos:
                g.ady[a.destino].append(Arco(u, a.km, a.kmh, a.via))
        return g

    def nodo_mas_cercano(self, lat: float, lon: float, candidatos=None) -> int:
        candidatos = candidatos if candidatos is not None else self.pos.keys()
        return min(candidatos, key=lambda n: haversine_km(lat, lon, *self.pos[n]))


# ----------------------------------------------------------------------
# Construcción de la red de Ibagué
# ----------------------------------------------------------------------

def red_ibague_base() -> tuple[Grafo, int, list[int]]:
    """Grafo simplificado de barrios y vías principales de Ibagué.
    Devuelve (grafo, nodo_deposito, nodos_que_pueden_ser_clientes)."""
    from .datos.ibague_red_vial import (DEPOSITO, FACTOR_SINUOSIDAD, NODOS,
                                 VELOCIDADES_KMH, VIAS)
    g = Grafo()
    for n, (nombre, comuna, lat, lon, _) in NODOS.items():
        g.agregar_nodo(n, lat, lon, nombre, comuna)
    for u, v, via, tipo in VIAS:
        km = haversine_km(*g.pos[u], *g.pos[v]) * FACTOR_SINUOSIDAD
        g.agregar_arco(u, v, round(km, 3), VELOCIDADES_KMH[tipo], via)
    clientes = [n for n, datos in NODOS.items() if datos[4]]
    return g, DEPOSITO, clientes


# Velocidades por tipo de vía de OpenStreetMap (km/h)
_VEL_OSM = {
    "motorway": 60, "trunk": 50, "primary": 35, "secondary": 30,
    "tertiary": 25, "residential": 20, "unclassified": 20, "living_street": 10,
}


def _primero(valor):
    return valor[0] if isinstance(valor, list) else valor


def red_ibague_osm(cache=None) -> tuple[Grafo, int, list[int]]:
    """Descarga (una sola vez) todas las calles transitables de Ibagué desde
    OpenStreetMap con osmnx y las convierte a nuestro Grafo DIRIGIDO
    (respeta calles de un solo sentido). Los barrios de ibague_red_vial
    se ubican en la intersección real más cercana."""
    import os
    try:
        import osmnx as ox
    except ImportError as e:
        raise SystemExit("Para --osm instale osmnx:  pip install osmnx") from e
    from .config import CACHE_OSM
    from .datos.ibague_red_vial import DEPOSITO, NODOS
    cache = str(cache or CACHE_OSM)

    if os.path.exists(cache):
        G = ox.load_graphml(cache)
    else:
        print("Descargando calles de Ibagué desde OpenStreetMap (solo la primera vez)...")
        oeste, sur, este, norte = -75.265, 4.400, -75.120, 4.485
        try:
            G = ox.graph_from_bbox(bbox=(oeste, sur, este, norte), network_type="drive")  # osmnx 2.x
        except TypeError:
            G = ox.graph_from_bbox(norte, sur, este, oeste, network_type="drive")        # osmnx 1.x
        ox.save_graphml(G, cache)

    g = Grafo()
    for n, d in G.nodes(data=True):
        g.agregar_nodo(int(n), float(d["y"]), float(d["x"]))
    for u, v, d in G.edges(data=True):
        km = float(d.get("length", 0)) / 1000
        tipo = str(_primero(d.get("highway", "residential"))).replace("_link", "")
        kmh = _VEL_OSM.get(tipo, 20)
        via = _primero(d.get("name")) or f"vía {tipo} sin nombre"
        g.agregar_arco(int(u), int(v), km, kmh, str(via), doble_sentido=False)

    # Solo se usan nodos del componente fuertemente conexo del depósito,
    # para garantizar que se pueda ir Y volver.
    lat0, lon0 = NODOS[DEPOSITO][2], NODOS[DEPOSITO][3]
    semilla = g.nodo_mas_cercano(lat0, lon0)
    validos = g.alcanzables(semilla) & g.invertido().alcanzables(semilla)

    deposito = g.nodo_mas_cercano(lat0, lon0, validos)
    g.nombre[deposito], g.comuna[deposito] = NODOS[DEPOSITO][0], NODOS[DEPOSITO][1]
    clientes = []
    for nombre, comuna, lat, lon, es_cliente in NODOS.values():
        if not es_cliente:
            continue
        n = g.nodo_mas_cercano(lat, lon, validos)
        if n not in g.nombre:
            g.nombre[n], g.comuna[n] = nombre, comuna
            clientes.append(n)
    return g, deposito, clientes
