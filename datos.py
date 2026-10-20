# Bodega de la empresa (los camiones y livianos salen de aquí)
BODEGA = (4.4268, -75.2075)
# Plaza de Bolívar (la moto sale del centro)
CENTRO = (4.4389, -75.2322)

VEHICULOS_INICIALES = [
    {"id": "camion1", "tipo": "camion", "peso_max": 8000, "alto": 3.5,
     "ancho": 2.5, "profundo": 7.0, "lat": BODEGA[0], "lon": BODEGA[1]},
    {"id": "liviano1", "tipo": "liviano", "peso_max": 700, "alto": 1.8,
     "ancho": 1.7, "profundo": 2.2, "lat": BODEGA[0], "lon": BODEGA[1]},
    {"id": "moto1", "tipo": "moto", "peso_max": 80, "alto": 0.5,
     "ancho": 0.5, "profundo": 0.6, "lat": CENTRO[0], "lon": CENTRO[1]},
]

PEDIDOS_INICIALES = [
    {"id": "P01", "cliente": "Hospital Federico Lleras Acosta", "peso": 12, "alto": 0.3, "ancho": 0.3, "profundo": 0.4, "prioridad": 3, "lat": 4.43336, "lon": -75.21897},
    {"id": "P02", "cliente": "Conservatorio del Tolima", "peso": 45, "alto": 0.5, "ancho": 0.5, "profundo": 0.6, "prioridad": 2, "lat": 4.44344, "lon": -75.24399},
    {"id": "P03", "cliente": "Terminal de Transportes de Ibagué", "peso": 380, "alto": 0.8, "ancho": 0.8, "profundo": 1.0, "prioridad": 1, "lat": 4.43681, "lon": -75.23435},
    {"id": "P04", "cliente": "Jardín Botánico San Jorge", "peso": 60, "alto": 0.5, "ancho": 0.5, "profundo": 0.5, "prioridad": 2, "lat": 4.45411, "lon": -75.21862},
    {"id": "P05", "cliente": "Universidad del Tolima", "peso": 25, "alto": 0.4, "ancho": 0.4, "profundo": 0.5, "prioridad": 3, "lat": 4.42773, "lon": -75.2126},
    {"id": "P06", "cliente": "Centro Comercial Acqua Power Center", "peso": 900, "alto": 1.2, "ancho": 1.0, "profundo": 1.5, "prioridad": 1, "lat": 4.44079, "lon": -75.20455},
    {"id": "P07", "cliente": "Gobernación del Tolima", "peso": 8, "alto": 0.2, "ancho": 0.2, "profundo": 0.3, "prioridad": 3, "lat": 4.44401, "lon": -75.24196},
    {"id": "P08", "cliente": "Estadio Manuel Murillo Toro", "peso": 1500, "alto": 1.0, "ancho": 1.2, "profundo": 2.0, "prioridad": 1, "lat": 4.4298, "lon": -75.218},
    {"id": "P09", "cliente": "Cámara de Comercio de Ibagué", "peso": 30, "alto": 0.5, "ancho": 0.4, "profundo": 0.5, "prioridad": 2, "lat": 4.44528, "lon": -75.24189},
    {"id": "P10", "cliente": "Batallón Coronel Jaime Rooke", "peso": 150, "alto": 0.6, "ancho": 0.6, "profundo": 0.8, "prioridad": 2, "lat": 4.42312, "lon": -75.2466},
    {"id": "P11", "cliente": "Clínica Tolima", "peso": 18, "alto": 0.3, "ancho": 0.3, "profundo": 0.4, "prioridad": 3, "lat": 4.44152, "lon": -75.24144},
    {"id": "P12", "cliente": "Finca los Laureles", "peso": 620, "alto": 1.0, "ancho": 1.0, "profundo": 1.2, "prioridad": 2, "lat": 4.41626, "lon": -75.21692},
    {"id": "P13", "cliente": "Estructura metálica para el Centro Comercial La Estación", "peso": 300, "alto": 4.0, "ancho": 3.0, "profundo": 8.0, "prioridad": 1, "lat": 4.44552, "lon": -75.20459},
]
