import ast
import heapq
import itertools
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
PASO_M = 15.0     # separación entre los puntos de calle usados para ubicar entregas


def _metros(a, b):
    # Distancia aproximada en metros entre dos puntos (lat, lon) cercanos
    dy = (b[0] - a[0]) * 111320.0
    dx = (b[1] - a[1]) * 111320.0 * math.cos(math.radians(a[0]))
    return math.hypot(dx, dy)


class Indice:
    #Ubica puntos sobre las calles.

    # cercano(): la esquina (nodo) más cercana.
    # snap():    el punto más cercano SOBRE la calle, aunque quede a mitad de cuadra o de una
               # vía larga donde las esquinas están lejos (así una finca se ubica junto a su vía).

    def __init__(self, G):
        self.ids = np.array(list(G.nodes))
        self.lat = np.array([G.nodes[n]["y"] for n in self.ids])
        self.lon = np.array([G.nodes[n]["x"] for n in self.ids])

        # Cada calle se reparte en puntos cada ~15 m. En las calles de doble vía (dos aristas
        # en sentidos opuestos) se usa una sola y se guardan los datos de ambos sentidos.
        aristas = list(G.edges(keys=True, data=True))
        por_clave = {}
        for i, (u, v, k, d) in enumerate(aristas):
            por_clave.setdefault((u, v, round(float(d.get("length", 0.0)), 1)), []).append(i)
        inversa = {}
        for i, (u, v, k, d) in enumerate(aristas):
            if i in inversa or u == v:
                continue
            for j in por_clave.get((v, u, round(float(d.get("length", 0.0)), 1)), []):
                if j != i and j not in inversa:
                    inversa[i], inversa[j] = j, i
                    break

        self.aristas = []
        p_lat, p_lon, p_e, p_pos = [], [], [], []
        for i, (u, v, k, d) in enumerate(aristas):
            j = inversa.get(i)
            if j is not None and j < i:
                continue                                  # ya la cubre su pareja
            largo = float(d.get("length", 0.0))
            a = (G.nodes[u]["y"], G.nodes[u]["x"])
            b = (G.nodes[v]["y"], G.nodes[v]["x"])
            geom = d.get("geometry")
            if geom is not None and hasattr(geom, "coords"):
                coords = [(y, x) for x, y in geom.coords]
                if _metros(coords[0], a) > _metros(coords[-1], a):
                    coords.reverse()                      # orientar de u hacia v
            else:
                coords = [a, b]
            largo_geo = sum(_metros(c1, c2) for c1, c2 in zip(coords, coords[1:]))
            if largo <= 0 or largo_geo <= 0:
                continue
            escala = largo / largo_geo                    # ajusta la geometría al largo real
            cum = [0.0]
            for c1, c2 in zip(coords, coords[1:]):
                cum.append(cum[-1] + _metros(c1, c2) * escala)
            e = len(self.aristas)
            self.aristas.append({"u": u, "v": v, "L": largo, "coords": coords, "cum": cum,
                                 "fwd": d, "rev": aristas[j][3] if j is not None else None})
            for t in range(len(coords) - 1):
                pasos = max(1, math.ceil(_metros(coords[t], coords[t + 1]) / PASO_M))
                for q in range(pasos):
                    f = q / pasos
                    p_lat.append(coords[t][0] + (coords[t + 1][0] - coords[t][0]) * f)
                    p_lon.append(coords[t][1] + (coords[t + 1][1] - coords[t][1]) * f)
                    p_e.append(e)
                    p_pos.append(cum[t] + (cum[t + 1] - cum[t]) * f)
            p_lat.append(coords[-1][0])
            p_lon.append(coords[-1][1])
            p_e.append(e)
            p_pos.append(cum[-1])

        self.p_lat, self.p_lon = np.array(p_lat), np.array(p_lon)
        self.p_e, self.p_pos = np.array(p_e), np.array(p_pos)

    def cercano(self, lat, lon):
        # Devuelve (id_nodo, distancia_en_metros) de la esquina más cercana
        dy = (self.lat - lat) * 111320.0
        dx = (self.lon - lon) * 111320.0 * math.cos(math.radians(lat))
        d2 = dx * dx + dy * dy
        i = int(np.argmin(d2))
        return int(self.ids[i]), float(math.sqrt(d2[i]))

    def snap(self, lat, lon):
        # Punto de calle más cercano: {"lat","lon","dist_m","e" (calle),"pos" (m desde su inicio)}
        dy = (self.p_lat - lat) * 111320.0
        dx = (self.p_lon - lon) * 111320.0 * math.cos(math.radians(lat))
        d2 = dx * dx + dy * dy
        i = int(np.argmin(d2))
        return {"lat": float(self.p_lat[i]), "lon": float(self.p_lon[i]),
                "dist_m": float(math.sqrt(d2[i])),
                "e": int(self.p_e[i]), "pos": float(self.p_pos[i])}


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


# ------------------------------------------- puntos sobre la calle (nodos virtuales)
def _punto_en(coords, cum, d):
    # [lat, lon] a distancia d (m) desde el inicio de la calle
    for i in range(len(cum) - 1):
        if d <= cum[i + 1] or i == len(cum) - 2:
            seg = cum[i + 1] - cum[i]
            t = 0.0 if seg <= 0 else min(1.0, max(0.0, (d - cum[i]) / seg))
            return [coords[i][0] + (coords[i + 1][0] - coords[i][0]) * t,
                    coords[i][1] + (coords[i + 1][1] - coords[i][1]) * t]


def _tramo(coords, cum, a, b):
    # Puntos [lat, lon] del pedazo de calle entre las distancias a y b (a <= b)
    pts = [_punto_en(coords, cum, a)]
    pts += [list(c) for c, d in zip(coords, cum) if a < d < b]
    pts.append(_punto_en(coords, cum, b))
    return pts


def insertar_virtuales(adj, indice, veh, puntos):
    # Agrega al grafo los puntos donde salen/llegan los vehículos, partiendo la calle en ese lugar.

    # puntos: lista de (id_virtual, snap). Si varios puntos caen en la misma calle se encadenan
    # en orden (esquina -> punto 1 -> punto 2 -> esquina), para que ir de uno a otro no obligue a
    # dar la vuelta por las esquinas. Respeta el sentido de la calle y las reglas del vehículo.
    
    reglas = _reglas(veh)
    por_calle = {}
    for nid, sn in puntos:
        por_calle.setdefault(sn["e"], []).append((sn["pos"], nid))
    for e, lista in por_calle.items():
        a = indice.aristas[e]
        cadena = [(0.0, a["u"])] + sorted(lista) + [(a["L"], a["v"])]
        for datos, sentido in ((a["fwd"], 1), (a["rev"], -1)):
            if datos is None:
                continue
            costo_total = _costo_arista(datos, veh, reglas)
            if costo_total is None:
                continue                      # este vehículo no puede usar esa calle
            mult = costo_total / a["L"]
            for (p0, n0), (p1, n1) in zip(cadena, cadena[1:]):
                largo = p1 - p0
                pts = _tramo(a["coords"], a["cum"], p0, p1)
                if sentido == 1:
                    desde, hasta = n0, n1
                else:
                    desde, hasta, pts = n1, n0, pts[::-1]
                adj.setdefault(desde, []).append((hasta, largo * mult, largo, {"_puntos": pts}))


# ------------------------------------------------------------------ Dijkstra
def dijkstra(adj, origen, objetivos=None, limite_m=None):
    costo = {origen: 0.0}
    metros = {origen: 0.0}
    previo = {}
    pendientes = set(objetivos) if objetivos else None
    desempate = itertools.count()     # evita comparar nodos (números) con puntos virtuales (tuplas)
    cola = [(0.0, next(desempate), origen)]
    vistos = set()
    while cola:
        d, _, u = heapq.heappop(cola)
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
                heapq.heappush(cola, (nd, next(desempate), v))
    return costo, metros, previo


def zona_alcanzable(G, indice, veh, max_puntos=2500):
    sd = indice.snap(veh["lat"], veh["lon"])
    if sd["dist_m"] > MAX_AJUSTE_M:
        return []
    limite = float(veh.get("alcance_km") or 0) * 1000
    adj = construir_adyacencia(G, veh)
    dep = ("salida", "alcance")
    insertar_virtuales(adj, indice, veh, [(dep, sd)])
    _, metros, _ = dijkstra(adj, dep, None, limite if limite else None)
    nodos = [n for n in metros if not isinstance(n, tuple)]      # solo esquinas reales
    paso = max(1, math.ceil(len(nodos) / max_puntos))
    return [[sd["lat"], sd["lon"]]] + [[G.nodes[n]["y"], G.nodes[n]["x"]] for n in nodos[::paso]]


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
        if "_puntos" in datos:                     # pedazo de calle junto a un punto virtual
            pts.extend(datos["_puntos"])
            continue
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
    # Mochila 0/1 controlando peso exacto y volumen acumulado
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


# ------------------------------------------------------ Held-Karp (TSP Exacto) y Vecino más cercano
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
    # Algoritmo rápido para cuando hay más de 12 paradas
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
def _planificar_vehiculo(G, indice, v, pendientes, nodo, snaps, excluidos):
    res = {"id": v["id"], "tipo": v["tipo"], "peso_max": v["peso_max"],
           "alcance_km": v.get("alcance_km"), "peso_cargado": 0, "paradas": [], "ruta": [],
           "ruta_ida": [], "ruta_regreso": [], "salida": None,
           "distancia_km": 0.0, "tiempo_min": 0, "mensaje": ""}
    excl = excluidos[v["id"]] = {"lejos": set(), "inalcanzable": set()}

    adj = construir_adyacencia(G, v)
    sd = indice.snap(v["lat"], v["lon"])        # punto de la calle donde sale el vehículo
    d_dep = sd["dist_m"]
    dep = ("salida", v["id"])

    cands = [p for p in pendientes.values() if p["peso"] <= v["peso_max"] and caben(p, v)]
    if not cands:
        res["mensaje"] = ("Ningún pedido pendiente cabe en este vehículo por peso o medidas "
                          "(los que faltan son más grandes, o los otros vehículos ya los tomaron).")
        return res
    if d_dep > MAX_AJUSTE_M:
        excl["inalcanzable"] = {p["id"] for p in cands}
        res["mensaje"] = "Su punto de salida está fuera del mapa (a más de 250 m de una calle)."
        return res

    # La salida y los pedidos se ubican sobre la calle (no en la esquina más cercana)
    insertar_virtuales(adj, indice, v, [(dep, sd)] + [(nodo[p["id"]], snaps[p["id"]]) for p in cands])

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

    # El último tramo de `orden` es el regreso a la bodega: se guarda aparte para que el
    # mapa no tenga que adivinar dónde termina la ida y dónde empieza la vuelta.
    ruta_ida, ruta_regreso, metros = [], [], 0.0
    ultimo_tramo = len(orden) - 2
    for tramo, (a, b) in enumerate(zip(orden, orden[1:])):
        na, nb = nodos[a], nodos[b]
        if na == nb:
            continue
        _, m, previo = busq[na]
        ns, ars = camino(previo, na, nb)
        puntos = puntos_camino(G, ns, ars)
        if tramo == ultimo_tramo:
            ruta_regreso.extend(puntos)
        else:
            ruta_ida.extend(puntos)
        metros += m[nb]
    ruta = ruta_ida + ruta_regreso

    for pos, idx in enumerate(orden[1:-1], start=1):
        p = elegidos[idx - 1]
        calle = snaps[p["id"]]            # punto exacto de la calle donde termina esa entrega
        res["paradas"].append({"orden": pos, "id": p["id"], "cliente": p["cliente"],
                               "peso": p["peso"], "lat": p["lat"], "lon": p["lon"],
                               "calle_lat": calle["lat"], "calle_lon": calle["lon"]})
        del pendientes[p["id"]]

    km = metros / 1000.0
    res["peso_cargado"] = round(sum(p["peso"] for p in elegidos), 1)
    res["ruta"] = ruta
    res["ruta_ida"] = ruta_ida
    res["ruta_regreso"] = ruta_regreso
    res["salida"] = [sd["lat"], sd["lon"]]
    res["distancia_km"] = round(km, 2)
    
    # Cálculo de tiempo realista: conducción + 5 minutos por entrega
    tiempo_conduccion = (km / VELOCIDAD_KMH.get(v["tipo"], 30)) * 60
    tiempo_entregas = len(elegidos) * 5
    res["tiempo_min"] = round(tiempo_conduccion + tiempo_entregas)
    return res


def _motivo(p, vehiculos, excluidos):
    aptos = [v for v in vehiculos if p["peso"] <= v["peso_max"] and caben(p, v)]
    if not aptos:
        return "excede", "Excede el peso o las medidas de todos los vehículos."
    lejos = [v for v in aptos if p["id"] in excluidos[v["id"]]["lejos"]]
    sin_calle = [v for v in aptos if p["id"] in excluidos[v["id"]]["inalcanzable"]]
    if len(lejos) + len(sin_calle) == len(aptos):
        if lejos:
            return "lejos", "Está más lejos de lo que alcanzan los vehículos que pueden llevarlo."
        return "sin_calle", "No hay calles permitidas para llegar hasta ahí con los vehículos que pueden llevarlo."
    return "llenos", "Los vehículos que pueden llevarlo ya iban llenos."


def planificar(G, indice, vehiculos, pedidos):
    nodo, snaps, fuera_mapa = {}, {}, []
    for p in pedidos:
        sn = indice.snap(p["lat"], p["lon"])
        if sn["dist_m"] > MAX_AJUSTE_M:
            fuera_mapa.append(p)
        else:
            nodo[p["id"]] = ("pedido", p["id"])
            snaps[p["id"]] = sn

    pendientes = {p["id"]: p for p in pedidos if p["id"] in nodo}
    excluidos, resultados = {}, {}
    for v in sorted(vehiculos, key=lambda x: x["peso_max"]):
        resultados[v["id"]] = _planificar_vehiculo(G, indice, v, pendientes, nodo, snaps, excluidos)

    # "codigo" le dice a la página qué se puede hacer: crear un vehículo solo ayuda si el
    # motivo es "excede" (muy grande o pesado) o "llenos" (faltó capacidad)
    sin_asignar = [{"id": p["id"], "cliente": p["cliente"], "codigo": "fuera_mapa",
                    "motivo": "Está fuera de la zona del mapa descargado (a más de 250 m de una calle)."}
                   for p in fuera_mapa]
    for p in pendientes.values():
        codigo, motivo = _motivo(p, vehiculos, excluidos)
        sin_asignar.append({"id": p["id"], "cliente": p["cliente"], "codigo": codigo, "motivo": motivo})

    return {"vehiculos": [resultados[v["id"]] for v in vehiculos],
            "sin_asignar": sin_asignar}