import copy
import json
import os
import time

from flask import Flask, jsonify, request

import algoritmos as alg
from datos import PEDIDOS_INICIALES, VEHICULOS_INICIALES

BASE = os.path.dirname(os.path.abspath(__file__))
ARCHIVO_GRAFO = os.path.join(BASE, "ibague.graphml")
ARCHIVO_OSM = os.path.join(BASE, "ibague.osm")
ARCHIVO_ESTADO = os.path.join(BASE, "estado.json")
CENTRO = (4.4389, -75.2322)
RADIO_M = 4500
MAX_DISTANCIA_A_VIA = 1000
TIPOS = ("camion", "moto", "liviano")

app = Flask(__name__, static_folder="static", static_url_path="/static")

SERVIDORES_OVERPASS = [
    "https://overpass.kumi.systems/api",
    "https://overpass.private.coffee/api",
    "https://overpass-api.de/api",
]
RADIOS_M = [RADIO_M, 5500, 4000]


def cargar_grafo():
    import osmnx as ox

    ox.settings.useful_tags_way = sorted(
        set(ox.settings.useful_tags_way) | {"maxheight", "maxweight", "maxwidth"})
    ox.settings.requests_timeout = 180

    osm_nuevo = os.path.exists(ARCHIVO_OSM) and (
        not os.path.exists(ARCHIVO_GRAFO)
        or os.path.getmtime(ARCHIVO_OSM) > os.path.getmtime(ARCHIVO_GRAFO))
    if osm_nuevo:
        print("Construyendo el mapa desde ibague.osm ...")
        G = ox.graph_from_xml(ARCHIVO_OSM)
        ox.save_graphml(G, ARCHIVO_GRAFO)
        return G

    if os.path.exists(ARCHIVO_GRAFO):
        print("Cargando calles desde ibague.graphml ...")
        return ox.load_graphml(ARCHIVO_GRAFO)

    for radio in RADIOS_M:
        for servidor in SERVIDORES_OVERPASS:
            ox.settings.overpass_url = servidor
            for intento in range(2):
                try:
                    print(f"Descargando calles (radio {radio} m) desde {servidor} ...")
                    G = ox.graph_from_point(CENTRO, dist=radio, network_type="drive")
                    ox.save_graphml(G, ARCHIVO_GRAFO)
                    return G
                except Exception as e:
                    print(f"  Falló ({type(e).__name__}). Reintentando ...")
                    time.sleep(5 * (intento + 1))
    raise SystemExit("No se pudo descargar el mapa. Corre primero: python descargar_mapa.py")


def estado_inicial():
    return {"vehiculos": copy.deepcopy(VEHICULOS_INICIALES),
            "pedidos": copy.deepcopy(PEDIDOS_INICIALES)}


def cargar_estado():
    if os.path.exists(ARCHIVO_ESTADO):
        with open(ARCHIVO_ESTADO, encoding="utf-8") as f:
            return json.load(f)
    return estado_inicial()


def guardar_estado():
    with open(ARCHIVO_ESTADO, "w", encoding="utf-8") as f:
        json.dump(ESTADO, f, ensure_ascii=False, indent=2)


def _num(datos, campo, positivo=True):
    try:
        x = float(datos[campo])
    except (KeyError, TypeError, ValueError):
        raise ValueError(f"El campo «{campo}» debe ser un número.")
    if positivo and x <= 0:
        raise ValueError(f"El campo «{campo}» debe ser mayor que cero.")
    return x


def _punto(datos):
    lat, lon = _num(datos, "lat", False), _num(datos, "lon", False)
    _, metros = INDICE.cercano(lat, lon)
    if metros > MAX_DISTANCIA_A_VIA:
        raise ValueError("Ese punto está fuera de la zona de Ibagué cubierta por el mapa.")
    return lat, lon


def _nuevo_id(lista, prefijo):
    usados = {x["id"] for x in lista}
    n = len(lista) + 1
    while f"{prefijo}{n:02d}" in usados:
        n += 1
    return f"{prefijo}{n:02d}"


@app.get("/")
def inicio():
    return app.send_static_file("index.html")


@app.get("/api/estado")
def api_estado():
    return jsonify(ESTADO)


@app.post("/api/pedidos")
def api_agregar_pedido():
    d = request.get_json(force=True)
    try:
        lat, lon = _punto(d)
        prioridad = int(_num(d, "prioridad"))
        if prioridad not in (1, 2, 3):
            raise ValueError("La prioridad debe ser 1, 2 o 3.")
        pedido = {
            "id": _nuevo_id(ESTADO["pedidos"], "P"),
            "cliente": (d.get("cliente") or "").strip() or "Cliente sin nombre",
            "peso": _num(d, "peso"), "alto": _num(d, "alto"),
            "ancho": _num(d, "ancho"), "profundo": _num(d, "profundo"),
            "prioridad": prioridad, "lat": lat, "lon": lon,
        }
    except ValueError as e:
        return jsonify(error=str(e)), 400
    ESTADO["pedidos"].append(pedido)
    guardar_estado()
    return jsonify(pedido), 201


@app.delete("/api/pedidos/<pid>")
def api_borrar_pedido(pid):
    ESTADO["pedidos"] = [p for p in ESTADO["pedidos"] if p["id"] != pid]
    guardar_estado()
    return jsonify(ok=True)


@app.post("/api/vehiculos")
def api_agregar_vehiculo():
    d = request.get_json(force=True)
    try:
        tipo = d.get("tipo")
        if tipo not in TIPOS:
            raise ValueError("El tipo debe ser camion, moto o liviano.")
        lat, lon = _punto(d)
        vid = (d.get("id") or "").strip() or _nuevo_id(ESTADO["vehiculos"], tipo)
        if any(v["id"] == vid for v in ESTADO["vehiculos"]):
            raise ValueError(f"Ya existe un vehículo con el id «{vid}».")
        vehiculo = {
            "id": vid, "tipo": tipo,
            "peso_max": _num(d, "peso_max"), "alto": _num(d, "alto"),
            "ancho": _num(d, "ancho"), "profundo": _num(d, "profundo"),
            "lat": lat, "lon": lon,
        }
    except ValueError as e:
        return jsonify(error=str(e)), 400
    ESTADO["vehiculos"].append(vehiculo)
    guardar_estado()
    return jsonify(vehiculo), 201


@app.delete("/api/vehiculos/<vid>")
def api_borrar_vehiculo(vid):
    ESTADO["vehiculos"] = [v for v in ESTADO["vehiculos"] if v["id"] != vid]
    guardar_estado()
    return jsonify(ok=True)


@app.post("/api/reiniciar")
def api_reiniciar():
    import importlib
    import datos as dt
    importlib.reload(dt)

    ESTADO.clear()
    ESTADO["vehiculos"] = copy.deepcopy(dt.VEHICULOS_INICIALES)
    ESTADO["pedidos"] = copy.deepcopy(dt.PEDIDOS_INICIALES)
    
    guardar_estado()
    return jsonify(ESTADO)


@app.post("/api/planificar")
def api_planificar():
    if not ESTADO["vehiculos"]:
        return jsonify(error="Agrega al menos un vehículo."), 400
    if not ESTADO["pedidos"]:
        return jsonify(error="Agrega al menos un pedido."), 400
    return jsonify(alg.planificar(G, INDICE, ESTADO["vehiculos"], ESTADO["pedidos"]))


G = cargar_grafo()
INDICE = alg.Indice(G)
ESTADO = cargar_estado()
print(f"Listo: {len(G.nodes)} nodos y {len(G.edges)} calles.")

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)