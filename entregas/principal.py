"""
==========================================================================
 RUTEO DE ENTREGAS EN IBAGUÉ (TOLIMA) CON GRAFOS
 Diseño de Algoritmos - Ingeniería de Sistemas (6.º semestre)
==========================================================================

Una empresa despacha desde su Centro de Distribución en Mirolindo con una
flota de 2 CAMIONES y 2 MOTOS:

  * Camión (NPR con furgón): 100 paquetes de todo tipo de elemento.
  * Moto (con baúl): 15 paquetes pequeños (sobres, electrónicos pequeños,
    ropa en bolsa, medicamentos); es un 25 % más rápida en el tráfico.

El programa:
  1. Modela Ibagué como un GRAFO PONDERADO (barrios = nodos, vías = arcos
     con longitud en km y velocidad en km/h).                 -> grafo.py
  2. Reparte los barrios en 4 zonas (algoritmo de BARRIDO); las motos
     toman las 2 zonas más lejanas, donde su velocidad ahorra más tiempo.
  3. Usa DIJKSTRA para calcular DISTANCIA y TIEMPO mínimos entre cada par
     de paradas por las vías de la ciudad.                     -> ruteo.py
  4. Encuentra la RUTA MÁS EFICIENTE de cada vehículo (TSP): Held-Karp
     exacto o vecino más cercano + 2-opt.                      -> ruteo.py
  5. Acomoda los paquetes en el furgón o baúl según su elemento (frágil,
     este lado arriba, peso que soporta) y el orden de entrega. -> carga.py
  6. Abre un MAPA interactivo de Ibagué con las rutas trazadas.
                                                               -> reporte.py

Uso
---
    python rutas_entregas.py
    python rutas_entregas.py --clientes 24 --semilla 7
    python rutas_entregas.py --criterio distancia      # minimiza km
    python rutas_entregas.py --osm                     # calles reales (pip install osmnx)
"""

from __future__ import annotations

import argparse
import csv
import random
import webbrowser
from dataclasses import dataclass, field

from .carga import (MEZCLA_CAMION, MEZCLA_MOTO, Furgon, Paquete, ResultadoCarga,
                   baul_moto, empacar, generar_paquete)
from .grafo import red_ibague_base, red_ibague_osm
from .config import SALIDAS
from .ruteo import barrido, ruta_optima, tiempos_entre_puntos

# Características de cada tipo de vehículo
PERFILES = {
    "Camión": {"paquetes": 100, "espacio": Furgon, "mezcla": MEZCLA_CAMION,
               "factor_velocidad": 1.00, "min_parada": 5, "min_paquete": 0.5},
    "Moto":   {"paquetes": 15, "espacio": baul_moto, "mezcla": MEZCLA_MOTO,
               "factor_velocidad": 1.25, "min_parada": 3, "min_paquete": 0.3},
}
FLOTA = ["Camión 1", "Camión 2", "Moto 1", "Moto 2"]


@dataclass
class Vehiculo:
    nombre: str
    clientes: list[int]
    paquetes: list[Paquete] = field(default_factory=list)
    ruta: list[int] = field(default_factory=list)
    recorrido: list = field(default_factory=list)      # tramos (u, v, arco)
    km: float = 0.0
    min_conduccion: float = 0.0
    metodo: str = ""
    carga: ResultadoCarga | None = None
    tramos_parada: list = field(default_factory=list)   # (a, b, km, min)

    @property
    def tipo(self) -> str:
        return self.nombre.split()[0]

    @property
    def perfil(self) -> dict:
        return PERFILES[self.tipo]

    @property
    def min_descargue(self) -> float:
        return (len(self.ruta) - 2) * self.perfil["min_parada"] + \
            len(self.paquetes) * self.perfil["min_paquete"]

    @property
    def min_total(self) -> float:
        return self.min_conduccion + self.min_descargue

    def itinerario(self, salida_min: float) -> list[dict]:
        """Tiempo de cada tramo (de una parada a la siguiente) y hora estimada
        de llegada, sumando el tiempo de entrega en cada parada."""
        filas, reloj = [], salida_min
        for i, (a, b, km, minutos) in enumerate(self.tramos_parada, start=1):
            llega = reloj + minutos
            n = sum(1 for p in self.paquetes if p.destino == b)
            entrega = self.perfil["min_parada"] + n * self.perfil["min_paquete"] if n else 0
            filas.append({"n": i, "de": a, "a": b, "km": km, "min": minutos,
                          "llega": llega, "entrega": entrega, "sale": llega + entrega})
            reloj = llega + entrega
        return filas


def hhmm(minutos: float) -> str:
    m = int(round(minutos))
    return f"{m // 60} h {m % 60:02d} min"


def reloj(minutos_del_dia: float) -> str:
    """Minutos desde medianoche -> '8:05 a. m.'"""
    m = int(round(minutos_del_dia)) % (24 * 60)
    h, mm = divmod(m, 60)
    return f"{(h - 1) % 12 + 1}:{mm:02d} {'a. m.' if h < 12 else 'p. m.'}"


def vias_resumidas(recorrido) -> list[tuple[str, float]]:
    """Agrupa tramos consecutivos de la misma vía: [(vía, km), ...]."""
    res: list[tuple[str, float]] = []
    for _, _, a in recorrido:
        if res and res[-1][0] == a.via:
            res[-1] = (a.via, res[-1][1] + a.km)
        else:
            res.append((a.via, a.km))
    return res


def notas(p: Paquete) -> str:
    n = []
    if p.fragil:
        n.append("FRÁGIL")
    if p.vertical:
        n.append("Este lado arriba")
    if p.solo_piso:
        n.append("Solo piso")
    return ", ".join(n) or "-"


# --------------------------------------------------------------------------

def asignar_zonas(grafo, deposito, clientes, criterio) -> dict[str, list[int]]:
    """Barrido en 4 zonas; las motos se quedan con las 2 más lejanas."""
    zonas = barrido(grafo, deposito, clientes, len(FLOTA))
    costo, _ = grafo.dijkstra(deposito, criterio)
    zonas.sort(key=lambda z: sum(costo[c] for c in z) / len(z))   # cercanas primero
    camiones = [n for n in FLOTA if n.startswith("Camión")]
    motos = [n for n in FLOTA if n.startswith("Moto")]
    return dict(zip(camiones + motos, zonas))


def planificar(v: Vehiculo, grafo, deposito, criterio, rng, sig_id) -> int:
    perfil = v.perfil
    espacio = perfil["espacio"]()
    v.paquetes = [generar_paquete(sig_id + i, rng.choice(v.clientes), rng, perfil["mezcla"])
                  for i in range(perfil["paquetes"])]
    sig_id += perfil["paquetes"]

    paradas = sorted({p.destino for p in v.paquetes})
    (v.ruta, v.recorrido, v.km, v.min_conduccion, v.metodo, v.tramos_parada) = ruta_optima(
        grafo, deposito, paradas, criterio, perfil["factor_velocidad"])
    orden = {n: i for i, n in enumerate(v.ruta[1:-1], start=1)}

    # Acomodo; si algo no cabe o se pasa de peso, se reemplaza ese paquete
    for _ in range(30):
        v.carga = empacar(v.paquetes, orden, espacio)
        cambiar = list(v.carga.no_caben)
        if not cambiar and v.carga.peso_total > espacio.capacidad_kg:
            cambiar = [max(v.paquetes, key=lambda p: p.peso)]
        if not cambiar:
            return sig_id
        for p in cambiar:
            i = v.paquetes.index(p)
            v.paquetes[i] = generar_paquete(p.id, p.destino, rng, perfil["mezcla"])
    raise RuntimeError(f"No fue posible acomodar la carga de {v.nombre}")


def imprimir(vehiculos: list[Vehiculo], grafo, criterio: str, detalle: bool,
             salida_min: float) -> None:
    L = "=" * 100
    print(L)
    print(f" RED VIAL DE IBAGUÉ: {grafo.num_nodos} nodos, {grafo.num_arcos} arcos | "
          f"flota: 2 camiones y 2 motos | ruta más eficiente por {criterio.upper()}")
    print(L)
    for v in vehiculos:
        f, r = v.carga.furgon, v.carga
        print(f"\n{v.nombre.upper()}  ({v.metodo})")
        print(f"  Paquetes  : {len(v.paquetes)}  en {f.nombre}")
        print(f"  Peso      : {r.peso_total:8.1f} / {f.capacidad_kg:.0f} kg "
              f"({100 * r.peso_total / f.capacidad_kg:4.1f} %)")
        print(f"  Volumen   : {r.volumen_total:8.3f} / {f.volumen_m3:.3f} m³ "
              f"({100 * r.volumen_total / f.volumen_m3:4.1f} %)")
        print(f"  Distancia : {v.km:.2f} km")
        print(f"  Tiempo    : conducción {hhmm(v.min_conduccion)} + entregas "
              f"{hhmm(v.min_descargue)} = {hhmm(v.min_total)}")
        print("  Orden de visita:")
        print(f"     0. SALE de {grafo.nombre[v.ruta[0]]}")
        for i, n in enumerate(v.ruta[1:-1], start=1):
            pq = [p for p in v.paquetes if p.destino == n]
            print(f"    {i:>2}. {grafo.nombre[n]:<32} comuna {grafo.comuna[n]:<22}"
                  f"{len(pq):>3} paq. {sum(p.peso for p in pq):7.1f} kg")
        print(f"     -> REGRESA a {grafo.nombre[v.ruta[-1]]}")
        print(f"  Tiempos por tramo (salida {reloj(salida_min)}):")
        print(f"    {'#':>2}  {'De':<32} {'A':<32} {'km':>6} {'Tiempo':>8}  {'Llega':>11}")
        for t in v.itinerario(salida_min):
            print(f"    {t['n']:>2}. {grafo.nombre[t['de']][:32]:<32} {grafo.nombre[t['a']][:32]:<32} "
                  f"{t['km']:>6.2f} {t['min']:>5.0f} min  {reloj(t['llega']):>11}")
        print("  Vías recorridas: " +
              " -> ".join(f"{via} ({km:.1f} km)" for via, km in vias_resumidas(v.recorrido)))
        if detalle:
            imprimir_paquetes(v, grafo)
    print(f"\n{L}\n TOTAL FLOTA: {sum(len(v.paquetes) for v in vehiculos)} paquetes, "
          f"{sum(v.km for v in vehiculos):.2f} km, "
          f"{hhmm(sum(v.min_total for v in vehiculos))} de trabajo\n{L}")


def imprimir_paquetes(v: Vehiculo, grafo) -> None:
    print(f"\n  Paquetes de {v.nombre} en ORDEN DE CARGUE (medidas en cm):")
    enc = (f"  {'#':>3} {'ID':>5} {'Empaque':<7} {'Elemento':<25} {'Alto':>5} {'Ancho':>5} "
           f"{'Prof.':>5} {'Peso kg':>7} {'Cliente':<28} {'Parada':>6}  Notas")
    print(enc)
    print("  " + "-" * (len(enc) - 2))
    for i, col in enumerate(v.carga.colocados, start=1):
        p = col.paquete
        print(f"  {i:>3} {p.id:>5} {p.empaque:<7} {p.elemento:<25} {p.alto:>5.1f} {p.ancho:>5.1f} "
              f"{p.profundidad:>5.1f} {p.peso:>7.2f} {grafo.nombre[p.destino][:28]:<28} "
              f"{col.orden_entrega:>6}  {notas(p)}")


def exportar_csv(v: Vehiculo, grafo) -> str:
    nombre = SALIDAS / f"paquetes_{v.nombre.lower().replace(' ', '_').replace('ó', 'o')}.csv"
    with open(nombre, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["orden_cargue", "id", "empaque", "elemento", "alto_cm", "ancho_cm",
                    "profundidad_cm", "peso_kg", "volumen_m3", "cliente", "comuna",
                    "parada", "notas"])
        for i, col in enumerate(v.carga.colocados, start=1):
            p = col.paquete
            w.writerow([i, p.id, p.empaque, p.elemento, p.alto, p.ancho, p.profundidad,
                        p.peso, round(p.volumen_m3, 4), grafo.nombre[p.destino],
                        grafo.comuna[p.destino], col.orden_entrega, notas(p)])
    return nombre.name


def exportar_tiempos(matriz, grafo, puntos) -> str:
    """CSV con el tiempo y la distancia entre TODOS los pares de puntos."""
    factor_moto = PERFILES["Moto"]["factor_velocidad"]
    nombre = SALIDAS / "tiempos_entre_puntos.csv"
    with open(nombre, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["desde", "hasta", "km", "min_camion", "min_moto", "vias"])
        for a in puntos:
            for b in puntos:
                if a != b:
                    d = matriz[(a, b)]
                    w.writerow([grafo.nombre[a], grafo.nombre[b], round(d["km"], 2),
                                round(d["min"], 1), round(d["min"] / factor_moto, 1),
                                " -> ".join(d["vias"])])
    return nombre.name


def main() -> None:
    ap = argparse.ArgumentParser(description="Ruteo de entregas en Ibagué con grafos")
    ap.add_argument("--clientes", type=int, default=20, help="barrios a atender")
    ap.add_argument("--criterio", choices=["tiempo", "distancia"], default="tiempo",
                    help="qué minimiza la ruta (siempre se reportan ambos)")
    ap.add_argument("--semilla", type=int, default=None, help="para resultados reproducibles")
    ap.add_argument("--osm", action="store_true", help="usar todas las calles reales (osmnx)")
    ap.add_argument("--resumen", action="store_true", help="no listar los paquetes")
    ap.add_argument("--no-abrir", action="store_true", help="no abrir el mapa en el navegador")
    ap.add_argument("--salida", default="08:00", help="hora de salida del depósito (HH:MM)")
    args = ap.parse_args()
    try:
        hh, mm = map(int, args.salida.split(":"))
        salida_min = hh * 60 + mm
    except ValueError:
        ap.error("--salida debe tener el formato HH:MM, por ejemplo 07:30")

    SALIDAS.mkdir(exist_ok=True)
    rng = random.Random(args.semilla)
    grafo, deposito, candidatos = red_ibague_osm() if args.osm else red_ibague_base()
    if not len(FLOTA) <= args.clientes <= len(candidatos):
        ap.error(f"--clientes debe estar entre {len(FLOTA)} y {len(candidatos)}")

    clientes = rng.sample(candidatos, args.clientes)
    zonas = asignar_zonas(grafo, deposito, clientes, args.criterio)
    vehiculos, sig_id = [], 1
    for nombre in FLOTA:
        v = Vehiculo(nombre, zonas[nombre])
        sig_id = planificar(v, grafo, deposito, args.criterio, rng, sig_id)
        vehiculos.append(v)

    imprimir(vehiculos, grafo, args.criterio, not args.resumen, salida_min)

    # Tiempo y distancia entre todos los puntos (Dijkstra desde cada uno)
    puntos = [deposito] + sorted(clientes, key=lambda n: grafo.nombre[n])
    matriz = tiempos_entre_puntos(grafo, puntos, args.criterio)
    archivos = [exportar_csv(v, grafo) for v in vehiculos] + [exportar_tiempos(matriz, grafo, puntos)]
    print(f"\nArchivos en la carpeta {SALIDAS.name}/: " + ", ".join(archivos))

    from .reporte import generar_html
    mapa = generar_html(vehiculos, grafo, deposito, args.criterio, osm=args.osm,
                        matriz=matriz, puntos=puntos, salida_min=salida_min,
                        archivo=SALIDAS / "mapa_entregas.html")
    print(f"Mapa         : {SALIDAS.name}/{mapa.name}")
    if not args.no_abrir:
        webbrowser.open(mapa.resolve().as_uri())


if __name__ == "__main__":
    main()
