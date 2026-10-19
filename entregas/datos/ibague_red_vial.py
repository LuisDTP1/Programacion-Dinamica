"""
Red vial simplificada de IBAGUÉ (Tolima) para el problema de ruteo.

Cada NODO es un barrio o punto de referencia de una de las 13 comunas de
la ciudad. Cada ARISTA es un tramo de una vía real (Carrera 5, Avenida
Ambalá, Avenida Guabinal, Avenida Ferrocarril, vía a Bogotá, etc.).

IMPORTANTE: las coordenadas son APROXIMADAS (tomadas a nivel de barrio),
suficientes para el ejercicio académico. La longitud de cada tramo se
calcula con la fórmula de Haversine multiplicada por un factor de
sinuosidad (las calles no son rectas). Para trabajar con TODAS las calles
reales de la ciudad, ejecute el programa con la opción --osm.

Para ajustar un punto, basta con cambiar su (lat, lon) en NODOS.
"""

# Velocidades promedio por tipo de vía (km/h), considerando tráfico urbano
VELOCIDADES_KMH = {
    "nacional": 50,   # vía a Bogotá, vía a Armenia
    "avenida": 32,    # Carrera 5, Av. Ambalá, Av. Guabinal, Av. Ferrocarril
    "calle": 22,      # calles y carreras de barrio
}

FACTOR_SINUOSIDAD = 1.30

# id: (nombre, comuna, lat, lon, puede_ser_cliente)
NODOS = {
    0:  ("Centro de Distribución Mirolindo", "9 Picaleña-Mirolindo", 4.4262, -75.1585, False),
    1:  ("Centro - Plaza de Bolívar",        "1 Centro",              4.4446, -75.2423, True),
    2:  ("Belén",                            "1 Centro",              4.4418, -75.2372, True),
    3:  ("La Pola",                          "1 Centro",              4.4478, -75.2462, True),
    4:  ("Calambeo",                         "2 Calambeo",            4.4535, -75.2385, True),
    5:  ("Ancón",                            "2 Calambeo",            4.4592, -75.2448, True),
    6:  ("San Simón",                        "3 San Simón",           4.4485, -75.2265, True),
    7:  ("Cádiz",                            "3 San Simón",           4.4422, -75.2252, True),
    8:  ("Piedra Pintada",                   "4 Piedrapintada",       4.4462, -75.2120, True),
    9:  ("Carrera 5 con Calle 37",           "4 Piedrapintada",       4.4405, -75.2170, False),
    10: ("Jordán 7.a etapa",                 "5 Jordán",              4.4455, -75.1985, True),
    11: ("Jordán 9.a etapa",                 "5 Jordán",              4.4392, -75.1925, True),
    12: ("Carrera 5 con Calle 60",           "5 Jordán",              4.4400, -75.2035, False),
    13: ("Vergel",                           "6 Vergel",              4.4528, -75.1885, True),
    14: ("Ambalá",                           "6 Vergel",              4.4605, -75.2045, True),
    15: ("El Salado",                        "7 Salado",              4.4725, -75.1935, True),
    16: ("Ciudadela Simón Bolívar",          "8 Simón Bolívar",       4.4590, -75.1770, True),
    17: ("Jardín Santander",                 "8 Simón Bolívar",       4.4485, -75.1810, True),
    18: ("Mirolindo",                        "9 Picaleña-Mirolindo",  4.4305, -75.1660, True),
    19: ("Picaleña",                         "9 Picaleña-Mirolindo",  4.4175, -75.1690, True),
    20: ("Hacienda Santa Cruz",              "9 Picaleña-Mirolindo",  4.4120, -75.1560, True),
    21: ("Aeropuerto Perales",               "9 Picaleña-Mirolindo",  4.4197, -75.1319, True),
    22: ("Estadio Manuel Murillo Toro",      "10 Estadio",            4.4335, -75.2205, True),
    23: ("Santa Helena (U. del Tolima)",     "10 Estadio",            4.4290, -75.2125, True),
    24: ("Terminal de Transportes",          "10 Estadio",            4.4378, -75.2290, True),
    25: ("Las Ferias",                       "11 Ferias",             4.4270, -75.2290, True),
    26: ("Av. Ferrocarril con Calle 21",     "11 Ferias",             4.4345, -75.2345, False),
    27: ("Ricaurte",                         "12 Ricaurte",           4.4335, -75.2448, True),
    28: ("Kennedy",                          "12 Ricaurte",           4.4280, -75.2395, True),
    29: ("Boquerón",                         "13 Boquerón",           4.4205, -75.2490, True),
}

DEPOSITO = 0

# (u, v, nombre de la vía, tipo) -- vías de doble sentido
VIAS = [
    # Eje oriente-occidente: Carrera 5
    (1, 2, "Carrera 5", "avenida"),
    (2, 7, "Carrera 5", "avenida"),
    (7, 9, "Carrera 5", "avenida"),
    (9, 12, "Carrera 5", "avenida"),
    (12, 11, "Carrera 5", "avenida"),
    (11, 18, "Carrera 5", "avenida"),
    (18, 0, "Carrera 5", "avenida"),
    # Salida a Bogotá (Ruta 40) y sector Picaleña
    (0, 21, "Vía a Bogotá", "nacional"),
    (0, 19, "Calle 145 - Picaleña", "calle"),
    (19, 20, "Vía Picaleña", "calle"),
    (0, 20, "Vía Bogotá - Santa Cruz", "nacional"),
    (18, 19, "Avenida Mirolindo", "avenida"),
    # Avenida Ambalá (norte)
    (6, 8, "Avenida Ambalá", "avenida"),
    (9, 8, "Calle 37", "calle"),
    (8, 14, "Avenida Ambalá", "avenida"),
    (14, 15, "Avenida Ambalá", "avenida"),
    (8, 10, "Calle 42 - Jordán", "calle"),
    # Avenida Guabinal y sector Jordán - Vergel - Salado
    (12, 10, "Calle 60", "avenida"),
    (10, 13, "Avenida Guabinal", "avenida"),
    (13, 16, "Avenida Guabinal", "avenida"),
    (15, 16, "Vía El Salado", "calle"),
    (17, 10, "Calle 64 - Jardín", "calle"),
    (17, 13, "Carrera 12 - Jardín", "calle"),
    (17, 11, "Calle 69", "calle"),
    (16, 18, "Calle 103 - Mirolindo", "avenida"),
    # Centro y norte occidental
    (1, 3, "Calle 10", "calle"),
    (1, 4, "Carrera 1 - Calambeo", "calle"),
    (4, 5, "Vía Ancón", "calle"),
    (3, 5, "Carrera 2 - Ancón", "calle"),
    (4, 6, "Calle 19", "calle"),
    (6, 7, "Carrera 4D", "calle"),
    # Sur: Avenida Ferrocarril, Ricaurte, Boquerón
    (1, 26, "Avenida Ferrocarril", "avenida"),
    (2, 24, "Calle 19", "calle"),
    (24, 26, "Avenida Ferrocarril", "avenida"),
    (26, 27, "Calle 21 - Ricaurte", "calle"),
    (3, 27, "Avenida Combeima", "calle"),
    (27, 28, "Carrera 8 Sur", "calle"),
    (27, 29, "Vía a Armenia", "nacional"),
    (28, 29, "Carrera 8 Sur - Boquerón", "calle"),
    (26, 25, "Avenida Ferrocarril", "avenida"),
    (25, 28, "Calle 25 Sur", "calle"),
    (25, 22, "Avenida Ferrocarril", "avenida"),
    (24, 22, "Carrera 4 Estadio", "calle"),
    (22, 7, "Carrera 4 Estadio", "calle"),
    (22, 23, "Avenida Ferrocarril", "avenida"),
    (23, 9, "Calle 37 - Santa Helena", "calle"),
    (23, 19, "Avenida Ferrocarril - Picaleña", "avenida"),
]
