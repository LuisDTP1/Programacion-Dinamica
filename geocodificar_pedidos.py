import math
import os
import shutil
import sys
import time

import requests

BASE = os.path.dirname(os.path.abspath(__file__))
ARCHIVO_DATOS = os.path.join(BASE, "datos.py")
CENTRO = (4.4389, -75.2322)                      # Plaza de Bolívar
RADIO_M = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 3000
NOMINATIM = "https://nominatim.openstreetmap.org/search"
HEADERS = {"User-Agent": "tarea-rutas-ibague/1.0 (proyecto universitario)"}

# Cada cliente es un lugar real de Ibagué. Peso, medidas y prioridad se conservan de los
# pedidos de ejemplo (prioridad: 3 = urgente, 2 = normal, 1 = puede esperar).
# "consultas": nombres con los que se busca el lugar; se prueba uno tras otro hasta encontrarlo.
LUGARES = [
    {"id": "P01", "cliente": "Hospital Federico Lleras Acosta", "peso": 12, "alto": 0.3, "ancho": 0.3, "profundo": 0.4, "prioridad": 3,
     "consultas": ["Hospital Federico Lleras Acosta, Ibagué", "Hospital Federico Lleras Acosta"]},
    {"id": "P02", "cliente": "Conservatorio del Tolima", "peso": 45, "alto": 0.5, "ancho": 0.5, "profundo": 0.6, "prioridad": 2,
     "consultas": ["Conservatorio del Tolima, Ibagué", "Conservatorio del Tolima"]},
    {"id": "P03", "cliente": "Terminal de Transportes de Ibagué", "peso": 380, "alto": 0.8, "ancho": 0.8, "profundo": 1.0, "prioridad": 1,
     "consultas": ["Terminal de Transportes de Ibagué", "Terminal de Transporte Ibagué"]},
    {"id": "P04", "cliente": "Jardín Botánico San Jorge", "peso": 60, "alto": 0.5, "ancho": 0.5, "profundo": 0.5, "prioridad": 2,
     "consultas": ["Jardín Botánico San Jorge, Ibagué", "Jardín Botánico San Jorge"]},
    {"id": "P05", "cliente": "Universidad del Tolima", "peso": 25, "alto": 0.4, "ancho": 0.4, "profundo": 0.5, "prioridad": 3,
     "consultas": ["Universidad del Tolima, Ibagué", "Universidad del Tolima"]},
    {"id": "P06", "cliente": "Centro Comercial Acqua Power Center", "peso": 900, "alto": 1.2, "ancho": 1.0, "profundo": 1.5, "prioridad": 1,
     "consultas": ["Acqua Power Center, Ibagué", "Centro Comercial Acqua, Ibagué"]},
    {"id": "P07", "cliente": "Gobernación del Tolima", "peso": 8, "alto": 0.2, "ancho": 0.2, "profundo": 0.3, "prioridad": 3,
     "consultas": ["Gobernación del Tolima, Ibagué", "Gobernación del Tolima"]},
    {"id": "P08", "cliente": "Estadio Manuel Murillo Toro", "peso": 1500, "alto": 1.0, "ancho": 1.2, "profundo": 2.0, "prioridad": 1,
     "consultas": ["Estadio Manuel Murillo Toro, Ibagué", "Estadio Murillo Toro Ibagué"]},
    {"id": "P09", "cliente": "Cámara de Comercio de Ibagué", "peso": 30, "alto": 0.5, "ancho": 0.4, "profundo": 0.5, "prioridad": 2,
     "consultas": ["Cámara de Comercio de Ibagué", "Cámara de Comercio Ibagué"]},
    {"id": "P10", "cliente": "Batallón Coronel Jaime Rooke", "peso": 150, "alto": 0.6, "ancho": 0.6, "profundo": 0.8, "prioridad": 2,
     "consultas": ["Batallón Coronel Jaime Rooke, Ibagué", "Batallón Jaime Rooke Ibagué"]},
    {"id": "P11", "cliente": "Clínica Tolima", "peso": 18, "alto": 0.3, "ancho": 0.3, "profundo": 0.4, "prioridad": 3,
     "consultas": ["Clínica Tolima, Ibagué", "Clínica Minuto de Dios, Ibagué", "Clínica Nuestra, Ibagué"]},
    {"id": "P13", "cliente": "Estructura metálica para el Centro Comercial La Estación", "peso": 300, "alto": 4.0, "ancho": 3.0, "profundo": 8.0, "prioridad": 1,
     "consultas": ["Centro Comercial La Estación, Ibagué", "La Estación Ibagué centro comercial"]},
]

# Este pedido ya tiene las coordenadas que elegiste tú; no se busca, se conserva igual
FIJOS = [
    {"id": "P12", "cliente": "Finca los Laureles", "peso": 620, "alto": 1.0, "ancho": 1.0, "profundo": 1.2,
     "prioridad": 2, "lat": 4.41626, "lon": -75.21692},
]


def zona():
    # Rectángulo del mapa descargado: izquierda, arriba, derecha, abajo
    dlat = RADIO_M / 111320.0
    dlon = RADIO_M / (111320.0 * math.cos(math.radians(CENTRO[0])))
    return CENTRO[1] - dlon, CENTRO[0] + dlat, CENTRO[1] + dlon, CENTRO[0] - dlat


def distancia_m(lat, lon):
    dy = (lat - CENTRO[0]) * 111320.0
    dx = (lon - CENTRO[1]) * 111320.0 * math.cos(math.radians(CENTRO[0]))
    return math.hypot(dx, dy)


def buscar(consulta, acotado):
    # Busca un lugar. Con acotado=True solo devuelve resultados dentro de la zona del mapa.
    params = {"q": consulta, "format": "jsonv2", "limit": 1, "countrycodes": "co",
              "viewbox": "{:.5f},{:.5f},{:.5f},{:.5f}".format(*zona())}
    if acotado:
        params["bounded"] = 1
    r = requests.get(NOMINATIM, params=params, headers=HEADERS, timeout=30)
    r.raise_for_status()
    resultados = r.json()
    time.sleep(1.1)                                 # Nominatim pide máximo 1 consulta por segundo
    if not resultados:
        return None
    return {"lat": round(float(resultados[0]["lat"]), 5),
            "lon": round(float(resultados[0]["lon"]), 5),
            "nombre": resultados[0].get("display_name", "")}


def encontrar(lugar):
    # Devuelve (resultado, dentro_del_mapa). Primero busca dentro del mapa y luego fuera.
    for acotado in (True, False):
        for consulta in lugar["consultas"]:
            res = buscar(consulta, acotado)
            if res:
                return res, acotado
    return None, False


def linea(p):
    return (f'    {{"id": "{p["id"]}", "cliente": "{p["cliente"]}", "peso": {p["peso"]}, '
            f'"alto": {p["alto"]}, "ancho": {p["ancho"]}, "profundo": {p["profundo"]}, '
            f'"prioridad": {p["prioridad"]}, "lat": {p["lat"]}, "lon": {p["lon"]}}},\n')


def main():
    print(f"Buscando {len(LUGARES)} lugares en OpenStreetMap (zona de {RADIO_M} m)...\n")
    pedidos, pendientes = [], []
    for lugar in LUGARES:
        try:
            res, dentro = encontrar(lugar)
        except requests.RequestException as e:
            print(f"Sin conexión con Nominatim ({e}). No se cambió nada.")
            return
        if not res:
            print(f"  {lugar['id']} {lugar['cliente']}: NO se encontró")
            pendientes.append(lugar)
            continue
        dist = distancia_m(res["lat"], res["lon"])
        aviso = "" if dentro else "  <-- FUERA del mapa descargado"
        print(f"  {lugar['id']} {lugar['cliente']}: {res['lat']}, {res['lon']} "
              f"({dist / 1000:.1f} km del centro){aviso}")
        print(f"       encontrado como: {res['nombre'][:90]}")
        pedido = {k: v for k, v in lugar.items() if k != "consultas"}
        pedido.update(lat=res["lat"], lon=res["lon"])
        pedidos.append(pedido)

    if not pedidos:
        print("\nNo se encontró ningún lugar. No se cambió nada.")
        return

    pedidos = sorted(pedidos + FIJOS, key=lambda p: p["id"])
    texto = open(ARCHIVO_DATOS, encoding="utf-8").read()
    inicio = texto.find("PEDIDOS_INICIALES = [")
    if inicio == -1:
        print("\nNo encontré PEDIDOS_INICIALES en datos.py. Pega esto a mano:\n")
        print("PEDIDOS_INICIALES = [\n" + "".join(linea(p) for p in pedidos) + "]")
        return
    shutil.copy(ARCHIVO_DATOS, ARCHIVO_DATOS + ".bak")
    with open(ARCHIVO_DATOS, "w", encoding="utf-8") as f:
        f.write(texto[:inicio] + "PEDIDOS_INICIALES = [\n" + "".join(linea(p) for p in pedidos) + "]\n")

    print(f"\nListo: datos.py quedó con {len(pedidos)} pedidos (copia anterior en datos.py.bak).")
    if pendientes:
        print("Sin encontrar (agrégalos a mano en la página, haciendo clic en el mapa): "
              + ", ".join(p["cliente"] for p in pendientes))
    print('Ahora pulsa "Restaurar ejemplo" en la página.')


if __name__ == "__main__":
    main()
