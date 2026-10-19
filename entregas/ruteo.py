"""
Asignación de clientes a camiones y cálculo de la ruta más eficiente.

1. matriz_costos: corre DIJKSTRA desde el depósito y desde cada cliente
   para obtener el costo mínimo real (por las calles) entre cada par de
   puntos, tanto en km como en minutos.
2. TSP sobre esa matriz:
     - HELD-KARP (programación dinámica, exacto)  O(n^2 · 2^n)  si n <= 10
     - VECINO MÁS CERCANO + 2-OPT (heurística)     O(n^2) + O(n^3)/pasada
   Ambos funcionan aunque la matriz sea asimétrica (calles de un sentido).
3. barrido: reparte clientes en zonas por ángulo alrededor del depósito.
"""

from __future__ import annotations

import math
from itertools import combinations

from .grafo import Grafo

LIMITE_EXACTO = 10


def barrido(grafo: Grafo, deposito: int, clientes: list[int], k: int) -> list[list[int]]:
    """Algoritmo de barrido (sweep): ordena los clientes por ángulo polar
    alrededor del depósito y corta en k zonas contiguas. El barrido arranca
    después del MAYOR hueco angular, para no partir un mismo sector de la
    ciudad en dos (el depósito de Mirolindo está en el extremo oriental).
    O(n log n)."""
    lat0, lon0 = grafo.pos[deposito]
    angulo = lambda c: math.atan2(grafo.pos[c][0] - lat0, grafo.pos[c][1] - lon0)
    orden = sorted(clientes, key=angulo)
    angs = [angulo(c) for c in orden]
    huecos = [(angs[(i + 1) % len(angs)] - angs[i]) % (2 * math.pi) for i in range(len(angs))]
    inicio = (huecos.index(max(huecos)) + 1) % len(orden)
    orden = orden[inicio:] + orden[:inicio]
    tam = math.ceil(len(orden) / k)
    return [orden[i:i + tam] for i in range(0, len(orden), tam)]


def matriz_costos(grafo: Grafo, puntos: list[int], criterio: str):
    """Dijkstra desde cada punto. Devuelve:
        C[u][v]       costo según el criterio (para optimizar)
        tramos[u][v]  lista de (u, v, arco) del camino mínimo real
    """
    C, tramos = {}, {}
    for u in puntos:
        costo, previo = grafo.dijkstra(u, criterio)
        C[u], tramos[u] = {}, {}
        for v in puntos:
            if v not in costo:
                raise RuntimeError(f"No hay camino de {grafo.nombre.get(u, u)} a {grafo.nombre.get(v, v)}")
            C[u][v] = costo[v]
            tramos[u][v] = Grafo.reconstruir(previo, u, v) if u != v else []
    return C, tramos


def costo_ruta(ruta: list[int], C) -> float:
    return sum(C[a][b] for a, b in zip(ruta, ruta[1:]))


def held_karp(dep: int, paradas: list[int], C) -> list[int]:
    """dp[(S, j)] = costo mínimo de salir del depósito, visitar exactamente
    el conjunto S (máscara de bits) y terminar en j."""
    n = len(paradas)
    if n == 0:
        return [dep, dep]
    dp = {(1 << j, j): (C[dep][paradas[j]], -1) for j in range(n)}
    for tam in range(2, n + 1):
        for sub in combinations(range(n), tam):
            S = sum(1 << b for b in sub)
            for j in sub:
                S_ant = S & ~(1 << j)
                dp[(S, j)] = min((dp[(S_ant, k)][0] + C[paradas[k]][paradas[j]], k)
                                 for k in sub if k != j)
    total = (1 << n) - 1
    _, j = min((dp[(total, j)][0] + C[paradas[j]][dep], j) for j in range(n))
    orden, S = [], total
    while j != -1:
        orden.append(paradas[j])
        S, j = S & ~(1 << j), dp[(S, j)][1]
    return [dep] + orden[::-1] + [dep]


def vecino_mas_cercano(dep: int, paradas: list[int], C) -> list[int]:
    ruta, pendientes = [dep], set(paradas)
    while pendientes:
        sig = min(pendientes, key=lambda c: C[ruta[-1]][c])
        ruta.append(sig)
        pendientes.remove(sig)
    return ruta + [dep]


def dos_opt(ruta: list[int], C) -> list[int]:
    """Invierte segmentos mientras el costo total baje. Se recalcula el
    costo completo para que sea correcto también con costos asimétricos."""
    mejor = costo_ruta(ruta, C)
    hubo_mejora = True
    while hubo_mejora:
        hubo_mejora = False
        for i in range(1, len(ruta) - 2):
            for k in range(i + 1, len(ruta) - 1):
                nueva = ruta[:i] + ruta[i:k + 1][::-1] + ruta[k + 1:]
                c = costo_ruta(nueva, C)
                if c < mejor - 1e-9:
                    ruta, mejor, hubo_mejora = nueva, c, True
    return ruta


def ruta_optima(grafo: Grafo, deposito: int, paradas: list[int], criterio: str,
                factor_velocidad: float = 1.0):
    """Devuelve (ruta, tramos_reales, km, minutos, metodo, tramos_por_parada).
    tramos_por_parada = [(a, b, km, minutos), ...] de cada parada a la siguiente.
    factor_velocidad > 1 indica un vehículo más rápido que el promedio (moto).
    Como multiplica TODAS las velocidades por la misma constante, no cambia
    cuál camino es el mínimo: solo escala los minutos."""
    C, tramos = matriz_costos(grafo, [deposito] + paradas, criterio)
    if len(paradas) <= LIMITE_EXACTO:
        ruta, metodo = held_karp(deposito, paradas, C), "Held-Karp (óptimo exacto)"
    else:
        ruta = dos_opt(vecino_mas_cercano(deposito, paradas, C), C)
        metodo = "Vecino más cercano + 2-opt"
    por_parada = []
    for a, b in zip(ruta, ruta[1:]):
        t = tramos[a][b]
        por_parada.append((a, b, sum(x.km for _, _, x in t),
                           sum(x.minutos for _, _, x in t) / factor_velocidad))
    recorrido = [t for a, b in zip(ruta, ruta[1:]) for t in tramos[a][b]]
    km = sum(p[2] for p in por_parada)
    minutos = sum(p[3] for p in por_parada)
    return ruta, recorrido, km, minutos, metodo, por_parada


def tiempos_entre_puntos(grafo: Grafo, puntos: list[int], criterio: str):
    """Dijkstra desde cada punto hacia todos los demás (todos contra todos).
    Para cada par (a, b) devuelve km y minutos del camino mínimo, las vías
    usadas y los nodos del camino. Los minutos son a la velocidad de la vía
    (la de un camión); para una moto se dividen por su factor de velocidad.
    Complejidad: P · O((V + E) log V) con P puntos."""
    res = {}
    for a in puntos:
        _, previo = grafo.dijkstra(a, criterio)
        for b in puntos:
            if a == b:
                continue
            t = Grafo.reconstruir(previo, a, b)
            vias = []
            for _, _, x in t:
                if not vias or vias[-1] != x.via:
                    vias.append(x.via)
            res[(a, b)] = {"km": sum(x.km for _, _, x in t),
                           "min": sum(x.minutos for _, _, x in t),
                           "vias": vias, "nodos": [a] + [v for _, v, _ in t]}
    return res
