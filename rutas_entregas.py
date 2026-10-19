"""
==========================================================================
 RUTEO DE ENTREGAS CON GRAFOS
 Diseño de Algoritmos - Ingeniería en Sistemas (6.º semestre)
==========================================================================

Problema
--------
Una empresa tiene un CENTRO DE DISTRIBUCIÓN (depósito) y varios CLIENTES
conectados por una red de calles. Cada camión de carga sale del depósito
con exactamente 100 paquetes (dimensiones y pesos aleatorios), debe
entregarlos a sus clientes y volver al depósito recorriendo la menor
distancia posible.

Modelado
--------
* La ciudad es un GRAFO NO DIRIGIDO PONDERADO G = (V, E):
    - V: intersecciones (depósito, clientes y cruces intermedios).
    - E: calles; el peso es la distancia en km.
* Un camión no puede ir "en línea recta": solo puede moverse por aristas.
  Por eso primero calculamos el CAMINO MÍNIMO real entre cada par de
  puntos de interés con DIJKSTRA (O((V+E) log V) por fuente).
* Con esas distancias armamos un grafo completo reducido (solo depósito +
  clientes del camión) y resolvemos un TSP (Travelling Salesman Problem):
    - Si hay pocas paradas (<= 10): HELD-KARP, programación dinámica
      exacta, O(n^2 * 2^n).
    - Si hay más: heurística VECINO MÁS CERCANO O(n^2) + mejora 2-OPT.
* Asignación de clientes a camiones: ALGORITMO DE BARRIDO (sweep), que
  ordena los clientes por ángulo polar alrededor del depósito y los
  reparte en zonas contiguas.
* Carga: cada camión valida capacidad de peso y volumen, y los paquetes
  se cargan en orden LIFO (lo último que se entrega entra primero).

Uso
---
    python rutas_entregas.py                     # valores por defecto
    python rutas_entregas.py --camiones 4 --nodos 60 --semilla 7
    python rutas_entregas.py --grafico           # guarda rutas.png (matplotlib)
"""

from __future__ import annotations

import argparse
import heapq
import math
import random
from dataclasses import dataclass, field
from itertools import combinations

# --------------------------------------------------------------------------
# 1. ESTRUCTURAS DE DATOS
# --------------------------------------------------------------------------

PAQUETES_POR_CAMION = 100


@dataclass
class Paquete:
    id: int
    largo_cm: float
    ancho_cm: float
    alto_cm: float
    peso_kg: float
    destino: int  # nodo del grafo

    @property
    def volumen_m3(self) -> float:
        return (self.largo_cm * self.ancho_cm * self.alto_cm) / 1_000_000


@dataclass
class Camion:
    id: int
    capacidad_kg: float = 3_500.0   # camión de carga liviano típico (NHR/NPR)
    capacidad_m3: float = 18.0
    clientes: list[int] = field(default_factory=list)
    paquetes: list[Paquete] = field(default_factory=list)
    ruta: list[int] = field(default_factory=list)          # orden de paradas
    ruta_completa: list[int] = field(default_factory=list) # con nodos intermedios
    distancia_km: float = 0.0

    @property
    def peso_total(self) -> float:
        return sum(p.peso_kg for p in self.paquetes)

    @property
    def volumen_total(self) -> float:
        return sum(p.volumen_m3 for p in self.paquetes)

    def cabe(self, p: Paquete) -> bool:
        return (self.peso_total + p.peso_kg <= self.capacidad_kg and
                self.volumen_total + p.volumen_m3 <= self.capacidad_m3)


class Grafo:
    """Grafo no dirigido ponderado con lista de adyacencia."""

    def __init__(self) -> None:
        self.adyacencia: dict[int, list[tuple[int, float]]] = {}
        self.coordenadas: dict[int, tuple[float, float]] = {}

    def agregar_nodo(self, nodo: int, x: float, y: float) -> None:
        self.adyacencia.setdefault(nodo, [])
        self.coordenadas[nodo] = (x, y)

    def agregar_arista(self, u: int, v: int, peso: float) -> None:
        self.adyacencia[u].append((v, peso))
        self.adyacencia[v].append((u, peso))

    def existe_arista(self, u: int, v: int) -> bool:
        return any(w == v for w, _ in self.adyacencia[u])

    @property
    def num_aristas(self) -> int:
        return sum(len(a) for a in self.adyacencia.values()) // 2

    # ---------------------- DIJKSTRA ------------------------------------
    def dijkstra(self, origen: int) -> tuple[dict[int, float], dict[int, int]]:
        """Distancias mínimas desde `origen` a todos los nodos.
        Devuelve (dist, previo) para poder reconstruir caminos.
        Complejidad: O((V + E) log V) usando un min-heap."""
        dist = {n: math.inf for n in self.adyacencia}
        previo: dict[int, int] = {}
        dist[origen] = 0.0
        heap = [(0.0, origen)]
        while heap:
            d, u = heapq.heappop(heap)
            if d > dist[u]:
                continue  # entrada obsoleta del heap
            for v, w in self.adyacencia[u]:
                nd = d + w
                if nd < dist[v]:
                    dist[v] = nd
                    previo[v] = u
                    heapq.heappush(heap, (nd, v))
        return dist, previo

    @staticmethod
    def reconstruir_camino(previo: dict[int, int], origen: int, destino: int) -> list[int]:
        camino = [destino]
        while camino[-1] != origen:
            camino.append(previo[camino[-1]])
        return camino[::-1]


# --------------------------------------------------------------------------
# 2. GENERACIÓN ALEATORIA DEL ESCENARIO
# --------------------------------------------------------------------------

def distancia_euclidiana(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def generar_ciudad(num_nodos: int, rng: random.Random) -> Grafo:
    """Crea una red vial conexa: primero un árbol de expansión mínima
    (Prim) sobre puntos aleatorios para garantizar conectividad, y luego
    calles extra entre vecinos cercanos para que haya rutas alternativas."""
    g = Grafo()
    g.agregar_nodo(0, 50.0, 50.0)  # depósito en el centro (km)
    for n in range(1, num_nodos):
        g.agregar_nodo(n, rng.uniform(0, 100), rng.uniform(0, 100))

    coords = g.coordenadas
    factor_calle = 1.25  # las calles no son rectas: +25 % sobre la distancia aérea

    # Prim para asegurar que el grafo sea conexo
    en_arbol = {0}
    heap = [(distancia_euclidiana(coords[0], coords[v]), 0, v) for v in range(1, num_nodos)]
    heapq.heapify(heap)
    while len(en_arbol) < num_nodos:
        d, u, v = heapq.heappop(heap)
        if v in en_arbol:
            continue
        en_arbol.add(v)
        g.agregar_arista(u, v, round(d * factor_calle, 2))
        for w in range(num_nodos):
            if w not in en_arbol:
                heapq.heappush(heap, (distancia_euclidiana(coords[v], coords[w]), v, w))

    # Calles adicionales: cada nodo se conecta con algunos de sus vecinos cercanos
    for u in range(num_nodos):
        vecinos = sorted((v for v in range(num_nodos) if v != u),
                         key=lambda v: distancia_euclidiana(coords[u], coords[v]))
        for v in vecinos[:3]:
            if not g.existe_arista(u, v) and rng.random() < 0.6:
                d = distancia_euclidiana(coords[u], coords[v]) * factor_calle
                g.agregar_arista(u, v, round(d, 2))
    return g


def generar_paquete(pid: int, destino: int, rng: random.Random) -> Paquete:
    return Paquete(
        id=pid,
        largo_cm=round(rng.uniform(10, 60), 1),
        ancho_cm=round(rng.uniform(10, 50), 1),
        alto_cm=round(rng.uniform(5, 40), 1),
        peso_kg=round(rng.uniform(0.5, 30), 2),
        destino=destino,
    )


# --------------------------------------------------------------------------
# 3. ASIGNACIÓN DE CLIENTES (ALGORITMO DE BARRIDO)
# --------------------------------------------------------------------------

def asignar_zonas(grafo: Grafo, clientes: list[int], num_camiones: int) -> list[list[int]]:
    """Ordena los clientes por ángulo polar respecto al depósito y los
    reparte en `num_camiones` sectores contiguos. O(n log n)."""
    cx, cy = grafo.coordenadas[0]
    ordenados = sorted(clientes, key=lambda c: math.atan2(grafo.coordenadas[c][1] - cy,
                                                          grafo.coordenadas[c][0] - cx))
    tam = math.ceil(len(ordenados) / num_camiones)
    return [ordenados[i:i + tam] for i in range(0, len(ordenados), tam)]


def cargar_camion(camion: Camion, rng: random.Random, siguiente_id: int) -> int:
    """Crea 100 paquetes para los clientes del camión, respetando capacidad.
    Si un paquete aleatorio no cabe, se vuelve a generar (máx. 50 intentos)."""
    for _ in range(PAQUETES_POR_CAMION):
        for _intento in range(50):
            p = generar_paquete(siguiente_id, rng.choice(camion.clientes), rng)
            if camion.cabe(p):
                camion.paquetes.append(p)
                siguiente_id += 1
                break
        else:
            raise RuntimeError(f"El camión {camion.id} no tiene capacidad para 100 paquetes.")
    return siguiente_id


# --------------------------------------------------------------------------
# 4. TSP SOBRE LA MATRIZ DE CAMINOS MÍNIMOS
# --------------------------------------------------------------------------

def costo_ruta(ruta: list[int], D: dict[int, dict[int, float]]) -> float:
    return sum(D[ruta[i]][ruta[i + 1]] for i in range(len(ruta) - 1))


def held_karp(paradas: list[int], D: dict[int, dict[int, float]]) -> list[int]:
    """TSP exacto por programación dinámica. dp[(S, j)] = costo mínimo de
    salir del depósito, visitar el conjunto S y terminar en j.
    Complejidad O(n^2 * 2^n): solo viable para pocas paradas."""
    n = len(paradas)
    dp: dict[tuple[int, int], tuple[float, int]] = {}
    for j in range(n):
        dp[(1 << j, j)] = (D[0][paradas[j]], -1)
    for tam in range(2, n + 1):
        for subset in combinations(range(n), tam):
            S = sum(1 << b for b in subset)
            for j in subset:
                S_sin_j = S & ~(1 << j)
                dp[(S, j)] = min(
                    (dp[(S_sin_j, k)][0] + D[paradas[k]][paradas[j]], k)
                    for k in subset if k != j
                )
    completo = (1 << n) - 1
    _, ultimo = min((dp[(completo, j)][0] + D[paradas[j]][0], j) for j in range(n))
    # reconstrucción hacia atrás
    orden, S, j = [], completo, ultimo
    while j != -1:
        orden.append(paradas[j])
        S, j = S & ~(1 << j), dp[(S, j)][1]
    return [0] + orden[::-1] + [0]


def vecino_mas_cercano(paradas: list[int], D: dict[int, dict[int, float]]) -> list[int]:
    """Heurística voraz O(n^2): siempre ir al cliente no visitado más cercano."""
    pendientes, ruta = set(paradas), [0]
    while pendientes:
        siguiente = min(pendientes, key=lambda c: D[ruta[-1]][c])
        ruta.append(siguiente)
        pendientes.remove(siguiente)
    return ruta + [0]


def dos_opt(ruta: list[int], D: dict[int, dict[int, float]]) -> list[int]:
    """Búsqueda local 2-opt: invierte segmentos mientras se reduzca la
    distancia (elimina cruces en la ruta)."""
    mejora = True
    while mejora:
        mejora = False
        for i in range(1, len(ruta) - 2):
            for k in range(i + 1, len(ruta) - 1):
                a, b, c, d = ruta[i - 1], ruta[i], ruta[k], ruta[k + 1]
                delta = (D[a][c] + D[b][d]) - (D[a][b] + D[c][d])
                if delta < -1e-9:
                    ruta[i:k + 1] = reversed(ruta[i:k + 1])
                    mejora = True
    return ruta


def planificar_ruta(camion: Camion, grafo: Grafo) -> str:
    """Calcula la ruta del camión y devuelve el nombre del método usado."""
    paradas = sorted({p.destino for p in camion.paquetes})
    puntos = [0] + paradas

    # Dijkstra desde cada punto de interés -> matriz de distancias reales
    D: dict[int, dict[int, float]] = {}
    previos: dict[int, dict[int, int]] = {}
    for u in puntos:
        dist, prev = grafo.dijkstra(u)
        D[u] = {v: dist[v] for v in puntos}
        previos[u] = prev

    if len(paradas) <= 10:
        ruta, metodo = held_karp(paradas, D), "Held-Karp (óptimo exacto)"
    else:
        ruta = vecino_mas_cercano(paradas, D)
        ruta, metodo = dos_opt(ruta, D), "Vecino más cercano + 2-opt"

    camion.ruta = ruta
    camion.distancia_km = costo_ruta(ruta, D)
    # Expandir cada tramo al camino real por las calles
    completa = [0]
    for a, b in zip(ruta, ruta[1:]):
        completa += Grafo.reconstruir_camino(previos[a], a, b)[1:]
    camion.ruta_completa = completa
    return metodo


def ordenar_carga_lifo(camion: Camion) -> None:
    """Los paquetes del último cliente van al fondo del camión."""
    orden_entrega = {nodo: i for i, nodo in enumerate(camion.ruta)}
    camion.paquetes.sort(key=lambda p: orden_entrega[p.destino], reverse=True)


# --------------------------------------------------------------------------
# 5. REPORTES Y VISUALIZACIÓN
# --------------------------------------------------------------------------

def imprimir_reporte(camiones: list[Camion], metodos: list[str], grafo: Grafo) -> None:
    linea = "=" * 74
    print(linea)
    print(f" RED VIAL: {len(grafo.adyacencia)} nodos, {grafo.num_aristas} calles | "
          f"Depósito = nodo 0")
    print(linea)
    total = 0.0
    for c, metodo in zip(camiones, metodos):
        paradas = c.ruta[1:-1]
        print(f"\nCAMIÓN {c.id}")
        print(f"  Paquetes : {len(c.paquetes)}")
        print(f"  Peso     : {c.peso_total:8.1f} / {c.capacidad_kg:.0f} kg "
              f"({100 * c.peso_total / c.capacidad_kg:5.1f} %)")
        print(f"  Volumen  : {c.volumen_total:8.2f} / {c.capacidad_m3:.0f} m³ "
              f"({100 * c.volumen_total / c.capacidad_m3:5.1f} %)")
        print(f"  Método   : {metodo}")
        print(f"  Paradas  : {len(paradas)} clientes")
        print(f"  Ruta     : {' -> '.join(map(str, c.ruta))}")
        print(f"  Recorrido por calles ({len(c.ruta_completa) - 1} tramos): "
              f"{' -> '.join(map(str, c.ruta_completa))}")
        print(f"  Distancia: {c.distancia_km:.2f} km")
        print("  Entregas :")
        for nodo in paradas:
            pq = [p for p in c.paquetes if p.destino == nodo]
            print(f"     cliente {nodo:>3}: {len(pq):>3} paquetes, "
                  f"{sum(p.peso_kg for p in pq):7.1f} kg")
        total += c.distancia_km
    print(f"\n{linea}\n DISTANCIA TOTAL DE LA FLOTA: {total:.2f} km\n{linea}")


def mostrar_muestra_paquetes(camion: Camion, n: int = 5) -> None:
    print(f"\nMuestra de paquetes del camión {camion.id} (orden de carga LIFO):")
    print(f"  {'ID':>5} {'L':>6} {'A':>6} {'H':>6} {'Peso':>7} {'Vol m³':>8} {'Destino':>8}")
    for p in camion.paquetes[:n]:
        print(f"  {p.id:>5} {p.largo_cm:>6} {p.ancho_cm:>6} {p.alto_cm:>6} "
              f"{p.peso_kg:>7} {p.volumen_m3:>8.4f} {p.destino:>8}")


def dibujar(grafo: Grafo, camiones: list[Camion], archivo: str = "rutas.png") -> None:
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("\n(matplotlib no está instalado: pip install matplotlib)")
        return
    fig, ax = plt.subplots(figsize=(10, 10))
    xy = grafo.coordenadas
    for u, vecinos in grafo.adyacencia.items():
        for v, _ in vecinos:
            if u < v:
                ax.plot([xy[u][0], xy[v][0]], [xy[u][1], xy[v][1]], color="#dddddd", lw=1, zorder=1)
    colores = plt.cm.tab10.colors
    for c in camiones:
        col = colores[(c.id - 1) % 10]
        xs = [xy[n][0] for n in c.ruta_completa]
        ys = [xy[n][1] for n in c.ruta_completa]
        ax.plot(xs, ys, color=col, lw=2.2, label=f"Camión {c.id} ({c.distancia_km:.1f} km)", zorder=2)
        ax.scatter([xy[n][0] for n in c.ruta[1:-1]], [xy[n][1] for n in c.ruta[1:-1]],
                   color=col, s=70, edgecolor="black", zorder=3)
    ax.scatter(*xy[0], marker="s", s=250, color="black", zorder=4, label="Depósito")
    for n, (x, y) in xy.items():
        ax.annotate(str(n), (x, y), fontsize=7, xytext=(3, 3), textcoords="offset points")
    ax.set_title("Rutas óptimas de entrega")
    ax.set_xlabel("km"); ax.set_ylabel("km"); ax.legend(loc="lower left", framealpha=0.9)
    fig.tight_layout(); fig.savefig(archivo, dpi=130)
    print(f"\nGráfico guardado en {archivo}")


# --------------------------------------------------------------------------
# 6. PROGRAMA PRINCIPAL
# --------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="Ruteo de entregas con grafos")
    ap.add_argument("--camiones", type=int, default=3, help="número de camiones")
    ap.add_argument("--nodos", type=int, default=40, help="intersecciones de la ciudad")
    ap.add_argument("--clientes", type=int, default=24, help="clientes a atender")
    ap.add_argument("--semilla", type=int, default=None, help="semilla aleatoria (reproducible)")
    ap.add_argument("--grafico", action="store_true", help="guardar rutas.png")
    args = ap.parse_args()

    if args.clientes >= args.nodos:
        ap.error("--clientes debe ser menor que --nodos")
    if args.camiones > args.clientes:
        ap.error("debe haber al menos un cliente por camión")

    rng = random.Random(args.semilla)
    grafo = generar_ciudad(args.nodos, rng)
    clientes = rng.sample(range(1, args.nodos), args.clientes)
    zonas = asignar_zonas(grafo, clientes, args.camiones)

    camiones, metodos, sig_id = [], [], 1
    for i, zona in enumerate(zonas, start=1):
        c = Camion(id=i, clientes=zona)
        sig_id = cargar_camion(c, rng, sig_id)
        metodos.append(planificar_ruta(c, grafo))
        ordenar_carga_lifo(c)
        camiones.append(c)

    imprimir_reporte(camiones, metodos, grafo)
    mostrar_muestra_paquetes(camiones[0])
    if args.grafico:
        dibujar(grafo, camiones)


if __name__ == "__main__":
    main()
