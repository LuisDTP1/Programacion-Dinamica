"""
Paquetes según su ELEMENTO y acomodo 3D dentro del furgón.

Cada tipo de elemento define rangos de tamaño y peso y unas reglas de
manipulación:
    fragil        -> no se le puede poner nada encima
    vertical      -> "este lado arriba": solo puede girar sobre el eje z
    carga_max_kg  -> peso máximo que soporta encima
    (peso > 25 kg -> va obligatoriamente en el piso)

Algoritmo de acomodo: heurística de PUNTOS EXTREMOS (Extreme Points,
Crainic-Perboli-Tadei, 2008) con criterio "más al fondo, más abajo, más a
la izquierda". Para cada paquete se prueban todos los puntos candidatos y
todas las orientaciones permitidas, y se elige la posición factible que
deja el paquete lo más al fondo posible. Restricciones verificadas:
    1. No sale del furgón.
    2. No se solapa con otro paquete.
    3. Si no está en el piso, al menos el 70 % de su base está apoyada.
    4. No se apoya sobre paquetes frágiles ni excede la carga que soportan.
    5. Orden de entrega (LIFO): ningún paquete que se entrega DESPUÉS
       queda bloqueando a uno que se entrega ANTES (entre él y la puerta).
Complejidad: O(n^2 · o) por paquete, con n paquetes y o orientaciones.

Ejes del furgón: x = largo (0 = cabina, L = puerta), y = ancho, z = alto.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from itertools import permutations

PESO_SOLO_PISO_KG = 25
APOYO_MINIMO = 0.70
EPS = 1e-6

# nombre: (largo cm, ancho cm, alto cm, peso kg, fragil, vertical, carga_max_kg, color, probabilidad)
TIPOS = {
    "Electrodoméstico":        ((40, 80), (35, 65), (40, 90), (12, 40),  False, True,  30,  "#4e79a7", 0.10),
    "Electrónico":             ((20, 50), (15, 40), (10, 35), (1, 8),    True,  True,  0,   "#e15759", 0.15),
    "Vidrio y cerámica":       ((20, 45), (20, 40), (15, 40), (2, 15),   True,  True,  0,   "#f28e2b", 0.10),
    "Alimentos no perecederos": ((30, 50), (25, 40), (20, 35), (5, 25),  False, False, 80,  "#59a14f", 0.20),
    "Ropa y textiles":         ((25, 60), (20, 45), (10, 30), (1, 8),    False, False, 15,  "#b07aa1", 0.20),
    "Ferretería y repuestos":  ((15, 40), (15, 35), (10, 30), (8, 30),   False, False, 100, "#76b7b2", 0.15),
    "Documentos y sobres":     ((20, 35), (15, 30), (2, 8),   (0.2, 2),  False, False, 5,   "#edc948", 0.10),
    # Elementos pequeños, propios de los envíos en moto
    "Electrónico pequeño":     ((10, 25), (8, 18),  (4, 12),  (0.2, 2),  True,  False, 0,   "#ff9da7", 0.0),
    "Ropa (bolsa pequeña)":    ((20, 35), (15, 28), (4, 12),  (0.3, 2.5), False, False, 8,  "#9c755f", 0.0),
    "Medicamentos":            ((10, 20), (8, 15),  (5, 12),  (0.1, 1.5), False, True, 5,   "#bab0ac", 0.0),
}

# Mezcla de elementos que transporta cada tipo de vehículo (pesos relativos)
MEZCLA_CAMION = {n: t[8] for n, t in TIPOS.items() if t[8] > 0}
MEZCLA_MOTO = {"Documentos y sobres": 0.40, "Electrónico pequeño": 0.25,
               "Ropa (bolsa pequeña)": 0.20, "Medicamentos": 0.15}


# Tipo de empaque posible para cada elemento (se elige uno al azar)
EMPAQUES = {
    "Electrodoméstico":         ["Caja"],
    "Electrónico":              ["Caja"],
    "Vidrio y cerámica":        ["Caja", "Huacal"],
    "Alimentos no perecederos": ["Caja", "Bulto"],
    "Ropa y textiles":          ["Bolsa", "Caja"],
    "Ferretería y repuestos":   ["Caja", "Bulto"],
    "Documentos y sobres":      ["Sobre", "Tubo"],
    "Electrónico pequeño":      ["Caja"],
    "Ropa (bolsa pequeña)":     ["Bolsa"],
    "Medicamentos":             ["Caja", "Bolsa"],
}


@dataclass
class Paquete:
    """Medidas en cm: largo = profundidad (sentido del furgón), ancho, alto."""
    id: int
    elemento: str
    empaque: str      # caja, sobre, bolsa, bulto, tubo, huacal
    largo: float      # cm (profundidad)
    ancho: float
    alto: float
    peso: float       # kg
    destino: int      # nodo del grafo

    @property
    def profundidad(self) -> float:
        return self.largo

    @property
    def regla(self):
        return TIPOS[self.elemento]

    @property
    def fragil(self) -> bool:
        return self.regla[4]

    @property
    def vertical(self) -> bool:
        return self.regla[5]

    @property
    def carga_max(self) -> float:
        return self.regla[6]

    @property
    def color(self) -> str:
        return self.regla[7]

    @property
    def solo_piso(self) -> bool:
        return self.peso > PESO_SOLO_PISO_KG

    @property
    def volumen_m3(self) -> float:
        return self.largo * self.ancho * self.alto / 1e6

    def orientaciones(self) -> list[tuple[float, float, float]]:
        """Dimensiones (dx, dy, dz) posibles según las reglas del elemento."""
        l, a, h = self.largo, self.ancho, self.alto
        if self.vertical:
            opciones = [(l, a, h), (a, l, h)]
        else:
            opciones = list(permutations((l, a, h)))
        return list(dict.fromkeys(opciones))  # sin repetidas, conservando orden


def generar_paquete(pid: int, destino: int, rng: random.Random,
                    mezcla: dict[str, float] | None = None) -> Paquete:
    """Paquete aleatorio. `mezcla` indica qué elementos pueden salir y con
    qué probabilidad relativa (por defecto, la mezcla de un camión)."""
    mezcla = mezcla or MEZCLA_CAMION
    elemento = rng.choices(list(mezcla), weights=list(mezcla.values()))[0]
    (l1, l2), (a1, a2), (h1, h2), (p1, p2), *_ = TIPOS[elemento]
    empaque = rng.choice(EMPAQUES[elemento])
    return Paquete(pid, elemento, empaque,
                   round(rng.uniform(l1, l2), 1), round(rng.uniform(a1, a2), 1),
                   round(rng.uniform(h1, h2), 1), round(rng.uniform(p1, p2), 2), destino)


@dataclass
class Furgon:
    """Espacio de carga de un vehículo (medidas internas en cm).
    Por defecto: camión liviano tipo NPR con furgón."""
    largo: float = 420.0   # cm
    ancho: float = 200.0
    alto: float = 200.0
    capacidad_kg: float = 3500.0
    nombre: str = "Furgón de camión NPR"

    @property
    def volumen_m3(self) -> float:
        return self.largo * self.ancho * self.alto / 1e6


def baul_moto() -> Furgon:
    """Baúl de moto de domicilios (medidas internas aproximadas)."""
    return Furgon(largo=55.0, ancho=45.0, alto=45.0, capacidad_kg=40.0, nombre="Baúl de moto")


@dataclass
class Colocacion:
    paquete: Paquete
    x: float
    y: float
    z: float
    dx: float
    dy: float
    dz: float
    orden_entrega: int
    carga_encima: float = 0.0

    @property
    def x2(self): return self.x + self.dx
    @property
    def y2(self): return self.y + self.dy
    @property
    def z2(self): return self.z + self.dz


@dataclass
class ResultadoCarga:
    furgon: Furgon
    colocados: list[Colocacion] = field(default_factory=list)
    no_caben: list[Paquete] = field(default_factory=list)

    @property
    def peso_total(self) -> float:
        return sum(c.paquete.peso for c in self.colocados)

    @property
    def volumen_total(self) -> float:
        return sum(c.paquete.volumen_m3 for c in self.colocados)

    @property
    def largo_usado(self) -> float:
        return max((c.x2 for c in self.colocados), default=0.0)


def _solapa_1d(a1, a2, b1, b2) -> float:
    return max(0.0, min(a2, b2) - max(a1, b1))


def _es_factible(p: Paquete, orden: int, x, y, z, dx, dy, dz,
                 furgon: Furgon, colocados: list[Colocacion]):
    """Devuelve la lista de (apoyo, area) si la posición es válida, o None."""
    if x + dx > furgon.largo + EPS or y + dy > furgon.ancho + EPS or z + dz > furgon.alto + EPS:
        return None
    if p.solo_piso and z > EPS:
        return None
    apoyos = []
    for c in colocados:
        sx = _solapa_1d(x, x + dx, c.x, c.x2)
        sy = _solapa_1d(y, y + dy, c.y, c.y2)
        sz = _solapa_1d(z, z + dz, c.z, c.z2)
        if sx > EPS and sy > EPS and sz > EPS:
            return None                                    # (2) solapamiento
        if abs(c.z - (z + dz)) < EPS and sx > EPS and sy > EPS:
            return None    # no se mete debajo del voladizo de otro paquete
        if z > EPS and abs(c.z2 - z) < EPS and sx > EPS and sy > EPS:
            apoyos.append((c, sx * sy))
        # (5) LIFO: un paquete que se entrega después no puede quedar
        #     entre este y la puerta (x mayor) en la misma franja y-z
        if c.orden_entrega > orden and c.x >= x + dx - EPS and sy > EPS and sz > EPS:
            return None
    if z > EPS:
        area = dx * dy
        if sum(a for _, a in apoyos) < APOYO_MINIMO * area:
            return None                                    # (3) apoyo
        total = sum(a for _, a in apoyos)
        for c, a in apoyos:                                # (4) frágil / carga
            if c.paquete.fragil:
                return None
            if c.carga_encima + p.peso * a / total > c.paquete.carga_max + EPS:
                return None
    return apoyos


def empacar(paquetes: list[Paquete], orden_entrega: dict[int, int],
            furgon: Furgon | None = None) -> ResultadoCarga:
    """Acomoda los paquetes en el furgón.
    orden_entrega[nodo] = posición de ese cliente en la ruta (1 = primero)."""
    furgon = furgon or Furgon()
    res = ResultadoCarga(furgon)

    # Orden de CARGUE: lo último que se entrega entra primero (al fondo);
    # dentro de cada cliente: pesados de piso, luego no frágiles grandes,
    # y los frágiles al final para que queden arriba.
    por_cargar = sorted(paquetes, key=lambda p: (-orden_entrega[p.destino],
                                                 not p.solo_piso, p.fragil, -p.volumen_m3))
    puntos = {(0.0, 0.0, 0.0)}
    for p in por_cargar:
        orden = orden_entrega[p.destino]
        mejor = None
        for (x, y, z) in puntos:
            for (dx, dy, dz) in p.orientaciones():
                clave = (x, z, y, x + dx, dz)        # fondo, abajo, izquierda
                if mejor is not None and clave >= mejor[0]:
                    continue
                apoyos = _es_factible(p, orden, x, y, z, dx, dy, dz, furgon, res.colocados)
                if apoyos is not None:
                    mejor = (clave, (x, y, z, dx, dy, dz), apoyos)
        if mejor is None:
            res.no_caben.append(p)
            continue
        _, (x, y, z, dx, dy, dz), apoyos = mejor
        total = sum(a for _, a in apoyos)
        for c, a in apoyos:
            c.carga_encima += p.peso * a / total
        res.colocados.append(Colocacion(p, x, y, z, dx, dy, dz, orden))
        puntos.discard((x, y, z))
        # nuevos puntos extremos (y sus proyecciones hacia el piso, la
        # pared izquierda y la cabina, para aprovechar los huecos)
        for q in ((x + dx, y, z), (x, y + dy, z), (x, y, z + dz)):
            for r in (q, *_proyecciones(q, res.colocados)):
                if r[0] < furgon.largo and r[1] < furgon.ancho and r[2] < furgon.alto:
                    puntos.add(r)
    return res


def _proyecciones(q, colocados):
    """Proyecta el punto q hacia z=0, y=0 y x=0 hasta tocar otro paquete."""
    px, py, pz = q
    z_pr = max([c.z2 for c in colocados if c.z2 <= pz + EPS and c.x <= px < c.x2 and c.y <= py < c.y2],
               default=0.0)
    y_pr = max([c.y2 for c in colocados if c.y2 <= py + EPS and c.x <= px < c.x2 and c.z <= pz < c.z2],
               default=0.0)
    x_pr = max([c.x2 for c in colocados if c.x2 <= px + EPS and c.y <= py < c.y2 and c.z <= pz < c.z2],
               default=0.0)
    return (px, py, z_pr), (px, y_pr, pz), (x_pr, py, pz)
