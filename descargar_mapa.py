import math
import os
import sys
import time
import urllib.parse
import xml.etree.ElementTree as ET
from xml.sax.saxutils import quoteattr

import requests

BASE = os.path.dirname(os.path.abspath(__file__))
SALIDA = os.path.join(BASE, "ibague.osm")
CENTRO = (4.4389, -75.2322)                      # Plaza de Bolívar
RADIO_M = 4500
SOLO_API = False
for arg in sys.argv[1:]:                         # argumentos opcionales: radio y/o "api"
    if arg.isdigit():
        RADIO_M = int(arg)
    elif arg.lower() == "api":
        SOLO_API = True

HEADERS = {"User-Agent": "tarea-rutas-ibague/1.0 (proyecto universitario)"}

# Servidores públicos de Overpass: si uno está saturado se prueba el siguiente
SERVIDORES = [
    "https://z.overpass-api.de/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]

# Solo vías por donde pasan vehículos (sin andenes, ciclorrutas ni parqueaderos)
TIPOS_VIA = ("motorway|trunk|primary|secondary|tertiary|unclassified|residential|living_street|"
             "motorway_link|trunk_link|primary_link|secondary_link|tertiary_link")
VIAS = set(TIPOS_VIA.split("|"))

CONSULTA = f"""[out:xml][timeout:120];
way["highway"~"^({TIPOS_VIA})$"](around:{RADIO_M},{CENTRO[0]},{CENTRO[1]});
(._;>;);
out body qt;
"""

API_OSM = "https://api.openstreetmap.org/api/0.6/map"
LADO_CUADRITO_M = 1000


# ------------------------------------------------------------ fuente 1: Overpass
def descargar_overpass(servidor):
    """Descarga el mapa de un servidor Overpass; lanza una excepción si algo sale mal."""
    r = requests.post(servidor, data={"data": CONSULTA}, stream=True,
                      timeout=(10, 90), headers=HEADERS)
    if r.status_code != 200:
        raise RuntimeError(f"el servidor respondió HTTP {r.status_code}")

    temporal = SALIDA + ".tmp"
    total = 0
    with open(temporal, "wb") as f:
        for trozo in r.iter_content(chunk_size=1 << 16):
            f.write(trozo)
            total += len(trozo)
            print(f"\r  recibidos {total / 1e6:.1f} MB", end="", flush=True)
    print()

    # Overpass a veces responde 200 aunque la consulta haya fallado: se revisa el contenido
    with open(temporal, "rb") as f:
        datos = f.read()
    if b"</osm>" not in datos[-500:]:
        raise RuntimeError("la respuesta llegó incompleta")
    if b"runtime error" in datos[-2000:]:
        raise RuntimeError("el servidor canceló la consulta (está saturado)")
    if b"<way" not in datos:
        raise RuntimeError("la respuesta no trae calles")
    os.replace(temporal, SALIDA)


def desde_overpass():
    for servidor in SERVIDORES:
        print(f"Probando {servidor}")
        try:
            descargar_overpass(servidor)
            return True
        except Exception as e:  # saturado, sin internet, tiempo agotado, etc.
            print(f"  Falló: {e}")
    return False


# ------------------------------------------------- fuente 2: API principal de OSM
def _cuadritos():
    """Divide la zona en cuadritos de ~1 km: (oeste, sur, este, norte)."""
    dlat = RADIO_M / 111320.0
    dlon = RADIO_M / (111320.0 * math.cos(math.radians(CENTRO[0])))
    oeste, sur = CENTRO[1] - dlon, CENTRO[0] - dlat
    este, norte = CENTRO[1] + dlon, CENTRO[0] + dlat
    n = max(1, math.ceil(2 * RADIO_M / LADO_CUADRITO_M))
    for i in range(n):
        for j in range(n):
            yield (oeste + (este - oeste) * j / n, sur + (norte - sur) * i / n,
                   oeste + (este - oeste) * (j + 1) / n, sur + (norte - sur) * (i + 1) / n)


def _pedir_cuadrito(caja, nivel=0):
    """Pide un cuadrito a la API. Si trae demasiados puntos (error 400) lo parte en 4."""
    o, s, e, n = caja
    for intento in range(4):
        try:
            r = requests.get(API_OSM, params={"bbox": f"{o:.6f},{s:.6f},{e:.6f},{n:.6f}"},
                             headers=HEADERS, timeout=(10, 120))
        except requests.RequestException:
            time.sleep(5 * (intento + 1))
            continue
        if r.status_code == 200:
            return [ET.fromstring(r.content)]
        if r.status_code == 400 and nivel < 3:     # demasiados puntos: dividir en 4
            mo, ms = (o + e) / 2, (s + n) / 2
            raices = []
            for sub in ((o, s, mo, ms), (mo, s, e, ms), (o, ms, mo, n), (mo, ms, e, n)):
                raices += _pedir_cuadrito(sub, nivel + 1)
            return raices
        if r.status_code in (429, 502, 503, 504, 509):
            time.sleep(10 * (intento + 1))
            continue
        raise RuntimeError(f"HTTP {r.status_code}")
    raise RuntimeError("la API de OpenStreetMap no respondió")


def _procesar(raiz, nodos, vias):
    """De un cuadrito se queda solo con las calles de vehículos y los puntos que usan."""
    nuevas = {}
    for el in raiz.findall("way"):
        etiquetas = {t.get("k"): t.get("v") for t in el.findall("tag")}
        if etiquetas.get("highway") in VIAS:
            nuevas[el.get("id")] = ([nd.get("ref") for nd in el.findall("nd")], etiquetas)
    usados = {ref for refs, _ in nuevas.values() for ref in refs}
    for el in raiz.findall("node"):
        if el.get("id") in usados:
            nodos[el.get("id")] = (el.get("lat"), el.get("lon"))
    vias.update(nuevas)


def _guardar(nodos, vias):
    """Escribe ibague.osm con las calles y sus puntos (mismo formato que Overpass)."""
    buenas = {wid: v for wid, v in vias.items() if all(r in nodos for r in v[0])}
    usados = {r for refs, _ in buenas.values() for r in refs}
    temporal = SALIDA + ".tmp"
    with open(temporal, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<osm version="0.6" generator="descargar_mapa.py">\n')
        for nid in usados:
            lat, lon = nodos[nid]
            f.write(f'  <node id="{nid}" lat="{lat}" lon="{lon}"/>\n')
        for wid, (refs, etiquetas) in buenas.items():
            f.write(f'  <way id="{wid}">\n')
            for ref in refs:
                f.write(f'    <nd ref="{ref}"/>\n')
            for k, v in etiquetas.items():
                f.write(f"    <tag k={quoteattr(k)} v={quoteattr(v)}/>\n")
            f.write("  </way>\n")
        f.write("</osm>\n")
    os.replace(temporal, SALIDA)
    return len(buenas)


def desde_api_osm():
    cuadritos = list(_cuadritos())
    print(f"Pidiendo {len(cuadritos)} cuadritos de ~{LADO_CUADRITO_M} m a api.openstreetmap.org ...")
    nodos, vias = {}, {}
    try:
        for i, caja in enumerate(cuadritos, start=1):
            for raiz in _pedir_cuadrito(caja):
                _procesar(raiz, nodos, vias)
            print(f"\r  cuadrito {i}/{len(cuadritos)} · {len(vias)} calles", end="", flush=True)
            time.sleep(1)                            # no saturar el servicio
        print()
    except Exception as e:
        print(f"\n  Falló: {e}")
        return False
    if not vias:
        print("  La respuesta no trajo calles.")
        return False
    print(f"  Guardadas {_guardar(nodos, vias)} calles.")
    return True


# ------------------------------------------------------------------------- main
def main():
    print(f"Descargando calles de Ibagué (radio {RADIO_M} m)...")
    if not SOLO_API and desde_overpass():
        print(f"Listo: se guardó {SALIDA}\nAhora corre:  python app.py")
        return
    print("\nProbando con la API principal de OpenStreetMap (por cuadritos) ...")
    if desde_api_osm():
        print(f"Listo: se guardó {SALIDA}\nAhora corre:  python app.py")
        return

    # Plan B: abrir la consulta en el navegador y guardar el resultado como ibague.osm
    url = SERVIDORES[0] + "?data=" + urllib.parse.quote(CONSULTA)
    print("\nNo se pudo descargar desde Python. Plan B: abre este enlace en el navegador,")
    print("guarda el resultado con el nombre ibague.osm en esta carpeta y corre python app.py:\n")
    print(url)


if __name__ == "__main__":
    main()