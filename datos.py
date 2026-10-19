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
    {"id": "P01", "cliente": "Farmacia Centro", "peso": 12, "alto": 0.3, "ancho": 0.3, "profundo": 0.4, "prioridad": 3, "lat": 4.4395, "lon": -75.2300},
    {"id": "P02", "cliente": "Tienda Barrio Jordán", "peso": 45, "alto": 0.5, "ancho": 0.5, "profundo": 0.6, "prioridad": 2, "lat": 4.4540, "lon": -75.2080},
    {"id": "P03", "cliente": "Ferretería La 14", "peso": 380, "alto": 0.8, "ancho": 0.8, "profundo": 1.0, "prioridad": 1, "lat": 4.4300, "lon": -75.2250},
    {"id": "P04", "cliente": "Restaurante El Salado", "peso": 60, "alto": 0.5, "ancho": 0.5, "profundo": 0.5, "prioridad": 2, "lat": 4.4180, "lon": -75.2470},
    {"id": "P05", "cliente": "Universidad del Tolima", "peso": 25, "alto": 0.4, "ancho": 0.4, "profundo": 0.5, "prioridad": 3, "lat": 4.4337, "lon": -75.1975},
    {"id": "P06", "cliente": "Supermercado Sur", "peso": 900, "alto": 1.2, "ancho": 1.0, "profundo": 1.5, "prioridad": 1, "lat": 4.4200, "lon": -75.2000},
    {"id": "P07", "cliente": "Oficina Cádiz", "peso": 8, "alto": 0.2, "ancho": 0.2, "profundo": 0.3, "prioridad": 3, "lat": 4.4440, "lon": -75.2450},
    {"id": "P08", "cliente": "Mueblería Norte", "peso": 1500, "alto": 1.0, "ancho": 1.2, "profundo": 2.0, "prioridad": 1, "lat": 4.4500, "lon": -75.1900},
    {"id": "P09", "cliente": "Panadería La Pola", "peso"    : 30, "alto": 0.5, "ancho": 0.4, "profundo": 0.5, "prioridad": 2, "lat": 4.4455, "lon": -75.2330},
    {"id": "P10", "cliente": "Colegio Sur", "peso": 150, "alto": 0.6, "ancho": 0.6, "profundo": 0.8, "prioridad": 2, "lat": 4.4080, "lon": -75.2300},
    {"id": "P11", "cliente": "Clínica Norte", "peso": 18, "alto": 0.3, "ancho": 0.3, "profundo": 0.4, "prioridad": 3, "lat": 4.4620, "lon": -75.2250},
    {"id": "P12", "cliente": "Finca los Laureles", "peso": 620, "alto": 1.0, "ancho": 1.0, "profundo": 1.2, "prioridad": 2, "lat": 4.41626, "lon": -75.21692},
    {"id": "P13", "cliente": "Estructura metálica (fuera de medida)", "peso": 300, "alto": 4.0, "ancho": 3.0, "profundo": 8.0, "prioridad": 1, "lat": 4.4300, "lon": -75.2000},
]
