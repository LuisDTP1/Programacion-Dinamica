import ast
import heapq
import math
import re

import numpy as np

INF = float("inf")
MAX_AJUSTE_M = 250        # un punto a más de 250 m de una calle se considera fuera del mapa
VELOCIDAD_KMH = {"camion": 25, "liviano": 30, "moto": 35}  # velocidad urbana promedio

# Reglas por tipo de vehículo sobre el tipo de vía de OpenStreetMap ("highway").
REGLAS = {
    "camion": {"prohibidas": {"living_street", "track", "path", "pedestrian", "footway", "cycleway", "steps", "bridleway"},
               "penal": {"residential": 3.0, "service": 3.0, "unclassified": 1.5}},
    "liviano": {"prohibidas": {"living_street", "track", "path", "pedestrian", "footway", "cycleway", "steps", "bridleway"},
                "penal": {"service": 1.5}},
    "moto": {"prohibidas": {"motorway", "motorway_link", "footway", "cycleway", "steps", "pedestrian", "path", "bridleway"},
             "penal": {}},
}


# ---------------------------------------------------------------- utilidades
class Indice:
    """Encuentra el nodo de calle más cercano a una coordenada."""

    def __init__(self, G):
        self.ids = np.array(list(G.nodes))
        self.lat = np.array([G.nodes[n]["y"] for n in self.ids])
        self.lon = np.array([G.nodes[n]["x"] for n in self.ids])

    def cercano(self, lat, lon):
        """Devuelve (id_nodo, distancia_en_metros)."""
        dy = (self.lat - lat) * 111320.0
        dx = (self.lon - lon) * 111320.0 * math.cos(math.radians(lat))
        d2 = dx * dx + dy * dy
        i = int(np.argmin(d2))
        return int(self.ids[i]), float(math.sqrt(d2[i]))


def _lista_highway(h):
    if isinstance(h, list):
        return h
    if isinstance(h, str) and h.startswith("["):
        try:
            return list(ast.literal_eval(h))
        except (ValueError, SyntaxError):
            pass
    return [h] if h else []


def _numero(valor):
    if valor is None:
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    if isinstance(valor, list):
        valor = valor[0] if valor else None
        return _numero(valor)
    m = re.search(r"\d+(?:[.,]\d+)?", str(valor))
    return float(m.group().replace(",", ".")) if m else None


def _reglas(veh):
    return REGLAS.get(veh["tipo"], REGLAS["liviano"])


def _costo_arista(datos, veh, reglas):
    tipos = _lista_highway(datos.get("highway"))
    if any(t in reglas["prohibidas"] for t in tipos):
        return None
    max_alto = _numero(datos.get("maxheight"))
    if max_alto is not None and veh["alto"] > max_alto:
        return None
    max_ancho = _numero(datos.get("maxwidth"))
    if max_ancho is not None and veh["ancho"] > max_ancho:
        return None
    max_peso_t = _numero(datos.get("maxweight"))
    if max_peso_t is not None and veh["peso_max"] > max_peso_t * 1000:
        return None
    penal = max([reglas["penal"].get(t, 1.0) for t in tipos] or [1.0])
    return float(datos.get("length", 0.0)) * penal


def construir_adyacencia(G, veh):
    reglas = _reglas(veh)
    adj = {}
    for u, v, datos in G.edges(data=True):
        costo = _costo_arista(datos, veh, reglas)
        if costo is None:
            continue
        adj.setdefault(u, []).append((v, costo, float(datos.get("length", 0.0)), datos))
    return adj


# ------------------------------------------------------------------ Dijkstra
def dijkstra(adj, origen, objetivos=None, limite_m=None):
    costo = {origen: 0.0}
    metros = {origen: 0.0}
    previo = {}
    pendientes = set(objetivos) if objetivos else None
    cola = [(0.0, origen)]
    vistos = set()
    while cola:
        d, u = heapq.heappop(cola)
        if u in vistos:
            continue
        vistos.add(u)
        if pendientes is not None:
            pendientes.discard(u)
            if not pendientes:
                break
        for v, c, m, datos in adj.get(u, ()):
            if limite_m is not None and metros[u] + m > limite_m:
                continue
            nd = d + c
            if nd < costo.get(v, INF):
                costo[v] = nd
                metros[v] = metros[u] + m
                previo[v] = (u, datos)
                heapq.heappush(cola, (nd, v))
    return costo, metros, previo


def zona_alcanzable(G, indice, veh, max_puntos=2500):
    dep, d_dep = indice.cercano(veh["lat"], veh["lon"])
    if d_dep > MAX_AJUSTE_M:
        return []
    limite = float(veh.get("alcance_km") or 0) * 1000
    adj = construir_adyacencia(G, veh)
    _, metros, _ = dijkstra(adj, dep, None, limite if limite else None)
    nodos = list(metros)
    paso = max(1, math.ceil(len(nodos) / max_puntos))
    return [[G.nodes[n]["y"], G.nodes[n]["x"]] for n in nodos[::paso]]


def camino(previo, origen, destino):
    nodos, aristas = [destino], []
    while nodos[-1] != origen:
        u, datos = previo[nodos[-1]]
        aristas.append(datos)
        nodos.append(u)
    nodos.reverse()
    aristas.reverse()
    return nodos, aristas


def puntos_camino(G, nodos, aristas):
    pts = []
    for (u, v), datos in zip(zip(nodos, nodos[1:]), aristas):
        a = (G.nodes[u]["y"], G.nodes[u]["x"])
        b = (G.nodes[v]["y"], G.nodes[v]["x"])
        geom = datos.get("geometry")
        if geom is not None and hasattr(geom, "coords"):
            coords = [(y, x) for x, y in geom.coords]
            if (coords[0][0] - a[0]) ** 2 + (coords[0][1] - a[1]) ** 2 > \
               (coords[-1][0] - a[0]) ** 2 + (coords[-1][1] - a[1]) ** 2:
                coords.reverse()
        else:
            coords = [a, b]
        pts.extend([list(c) for c in coords])
    return pts


# ------------------------------------------------------------ Mochila 0/1 (DP) con Volumen
def valor(p):
    return int(p["prioridad"]) * 1000 + math.ceil(p["peso"])


def mochila(pedidos, capacidad_kg, vol_max):
    """Mochila 0/1 controlando peso exacto y volumen acumulado."""
    n = len(pedidos)
    W = int(capacidad_kg)
    pesos = [max(1, math.ceil(p["peso"])) for p in pedidos]
    valores = [valor(p) for p in pedidos]
    volumenes = [p["alto"] * p["ancho"] * p["profundo"] for p in pedidos]

    dp = [[(0, 0.0)] * (W + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        pw, val, p_vol = pesos[i - 1], valores[i - 1], volumenes[i - 1]
        for w in range(W + 1):
            dp[i][w] = dp[i - 1][w]
            if pw <= w:
                val_prev, vol_prev = dp[i - 1][w - pw]
                if vol_prev + p_vol <= vol_max and val_prev + val > dp[i][w][0]:
                    dp[i][w] = (val_prev + val, vol_prev + p_vol)

    elegidos, w = [], W
    for i in range(n, 0, -1):
        if dp[i][w][0] != dp[i - 1][w][0]:
            elegidos.append(i - 1)
            w -= pesos[i - 1]
    return elegidos[::-1]


def caben(pedido, veh):
    a = sorted([pedido["alto"], pedido["ancho"], pedido["profundo"]])
    b = sorted([veh["alto"], veh["ancho"], veh["profundo"]])
    return all(x <= y for x, y in zip(a, b))


# ------------------------------------------------------ Held-Karp (TSP Exacto) & Vecino más cercano
def held_karp(D):
    n = len(D)
    if n == 1:
        return 0.0, [0, 0]
    if n == 2:
        return D[0][1] + D[1][0], [0, 1, 0]

    m = n - 1
    bit = lambda i: 1 << (i - 1)
    dp = {}
    for j in range(1, n):
        dp[(bit(j), j)] = (D[0][j], 0)

    for mask in range(1, 1 << m):
        for j in range(1, n):
            if not mask & bit(j) or mask == bit(j):
                continue
            prev = mask ^ bit(j)
            mejor = (INF, 0)
            for k in range(1, n):
                if prev & bit(k):
                    c = dp[(prev, k)][0] + D[k][j]
                    if c < mejor[0]:
                        mejor = (c, k)
            dp[(mask, j)] = mejor

    full = (1 << m) - 1
    costo, ultimo = min((dp[(full, j)][0] + D[j][0], j) for j in range(1, n))

    orden, mask, j = [], full, ultimo
    while j != 0:
        orden.append(j)
        anterior = dp[(mask, j)][1]
        mask ^= bit(j)
        j = anterior
    return costo, [0] + orden[::-1] + [0]


def vecino_mas_cercano(D):
    """Algoritmo rápido para cuando hay más de 12 paradas."""
    n = len(D)
    visitados = {0}
    orden = []
    actual = 0
    costo = 0.0
    while len(visitados) < n:
        siguiente = None
        min_dist = INF
        for j in range(n):
            if j not in visitados and D[actual][j] < min_dist:
                min_dist = D[actual][j]
                siguiente = j
        if siguiente is None:
            return INF, []
        visitados.add(siguiente)
        orden.append(siguiente)
        costo += min_dist
        actual = siguiente
    costo += D[actual][0]
    return costo, [0] + orden + [0]


# ----------------------------------------------------------------- planificador
def _planificar_vehiculo(G, indice, v, pendientes, nodo, excluidos):
    res = {"id": v["id"], "tipo": v["tipo"], "peso_max": v["peso_max"],
           "alcance_km": v.get("alcance_km"), "peso_cargado": 0, "paradas": [], "ruta": [],
           "distancia_km": 0.0, "tiempo_min": 0, "mensaje": ""}
    excl = excluidos[v["id"]] = {"lejos": set(), "inalcanzable": set()}

    adj = construir_adyacencia(G, v)
    dep, d_dep = indice.cercano(v["lat"], v["lon"])

    cands = [p for p in pendientes.values() if p["peso"] <= v["peso_max"] and caben(p, v)]
    if not cands:
        res["mensaje"] = "Ningún pedido pendiente cabe en este vehículo."
        return res
    if d_dep > MAX_AJUSTE_M:
        excl["inalcanzable"] = {p["id"] for p in cands}
        res["mensaje"] = "Su punto de salida está fuera del mapa (a más de 250 m de una calle)."
        return res

    dist_dep, m_dep, _ = dijkstra(adj, dep, {nodo[p["id"]] for p in cands})
    limite = float(v.get("alcance_km") or 0) * 1000
    dentro = []
    for p in cands:
        n = nodo[p["id"]]
        if n not in dist_dep:
            excl["inalcanzable"].add(p["id"])
        elif limite and m_dep[n] > limite:
            excl["lejos"].add(p["id"])
        else:
            dentro.append(p)
    cands = dentro
    if not cands:
        res["mensaje"] = "Ningún pedido está dentro de su alcance por calles permitidas."
        return res

    # Mochila con control de volumen
    vol_max = v["alto"] * v["ancho"] * v["profundo"]
    elegidos = [cands[i] for i in mochila(cands, v["peso_max"], vol_max)]

    nodos = [dep] + [nodo[p["id"]] for p in elegidos]
    busq = {n: dijkstra(adj, n, set(nodos)) for n in set(nodos)}
    elegidos = [p for p in elegidos
                if nodo[p["id"]] in busq[dep][0] and dep in busq[nodo[p["id"]]][0]]
    if not elegidos:
        res["mensaje"] = "No hay ruta de ida y vuelta viable."
        return res
    nodos = [dep] + [nodo[p["id"]] for p in elegidos]
    k = len(nodos)
    D = [[busq[nodos[i]][0].get(nodos[j], INF) for j in range(k)] for i in range(k)]

    # Selección automática de TSP (Held-Karp si <= 13 nodos, Vecino Cercano si > 13)
    if k <= 13:
        costo, orden = held_karp(D)
    else:
        costo, orden = vecino_mas_cercano(D)

    if costo == INF or not orden:
        res["mensaje"] = "No hay ruta viable entre las paradas."
        return res

    ruta, metros = [], 0.0
    for a, b in zip(orden, orden[1:]):
        na, nb = nodos[a], nodos[b]
        if na == nb:
            continue
        _, m, previo = busq[na]
        ns, ars = camino(previo, na, nb)
        ruta.extend(puntos_camino(G, ns, ars))
        metros += m[nb]

    for pos, idx in enumerate(orden[1:-1], start=1):
        p = elegidos[idx - 1]
        res["paradas"].append({"orden": pos, "id": p["id"], "cliente": p["cliente"],
                               "peso": p["peso"], "lat": p["lat"], "lon": p["lon"]})
        del pendientes[p["id"]]

    km = metros / 1000.0
    res["peso_cargado"] = round(sum(p["peso"] for p in elegidos), 1)
    res["ruta"] = ruta
    res["distancia_km"] = round(km, 2)
    
    # Cálculo de tiempo realista: conducción + 5 minutos por entrega
    tiempo_conduccion = (km / VELOCIDAD_KMH.get(v["tipo"], 30)) * 60
    tiempo_entregas = len(elegidos) * 5
    res["tiempo_min"] = round(tiempo_conduccion + tiempo_entregas)
    return res


def _motivo(p, vehiculos, excluidos):
    aptos = [v for v in vehiculos if p["peso"] <= v["peso_max"] and caben(p, v)]
    if not aptos:
        return "Excede el peso o las medidas de todos los vehículos."
    lejos = [v for v in aptos if p["id"] in excluidos[v["id"]]["lejos"]]
    sin_calle = [v for v in aptos if p["id"] in excluidos[v["id"]]["inalcanzable"]]
    if len(lejos) + len(sin_calle) == len(aptos):
        if lejos:
            return "Está más lejos de lo que alcanzan los vehículos que pueden llevarlo."
        return "No hay calles permitidas para llegar hasta ahí con los vehículos que pueden llevarlo."
    return "Los vehículos que pueden llevarlo ya iban llenos."


def planificar(G, indice, vehiculos, pedidos):
    nodo, fuera_mapa = {}, []
    for p in pedidos:
        n, dist = indice.cercano(p["lat"], p["lon"])
        if dist > MAX_AJUSTE_M:
            fuera_mapa.append(p)
        else:
            nodo[p["id"]] = n

    pendientes = {p["id"]: p for p in pedidos if p["id"] in nodo}
    excluidos, resultados = {}, {}
    for v in sorted(vehiculos, key=lambda x: x["peso_max"]):
        resultados[v["id"]] = _planificar_vehiculo(G, indice, v, pendientes, nodo, excluidos)

    sin_asignar = [{"id": p["id"], "cliente": p["cliente"],
                    "motivo": "Está fuera de la zona del mapa descargado (a más de 250 m de una calle)."}
                   for p in fuera_mapa]
    for p in pendientes.values():
        sin_asignar.append({"id": p["id"], "cliente": p["cliente"],
                            "motivo": _motivo(p, vehiculos, excluidos)})

    return {"vehiculos": [resultados[v["id"]] for v in vehiculos],
            "sin_asignar": sin_asignar}