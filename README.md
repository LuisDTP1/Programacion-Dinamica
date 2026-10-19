# Ruteo de entregas en Ibagué con grafos

Proyecto de Diseño de Algoritmos (Ingeniería de Sistemas, 6.º semestre).

La flota sale del Centro de Distribución de Mirolindo y está formada por **2 camiones** y **2 motos**:

| Vehículo | Paquetes | Espacio de carga | Velocidad |
|---|---|---|---|
| Camión (NPR con furgón) | 100, de todo tipo | 420 × 200 × 200 cm, 3.500 kg | velocidad de la vía |
| Moto con baúl | 15 pequeños | 55 × 45 × 45 cm, 40 kg | 25 % más rápida |

El programa calcula la ruta más eficiente de cada vehículo por las vías de Ibagué, decide cómo acomodar los paquetes en el furgón o el baúl y muestra todo en un mapa interactivo.

## Ejecutar

```bash
python rutas_entregas.py                       # 20 barrios, minimiza tiempo y abre el mapa
python rutas_entregas.py --clientes 24 --semilla 7
python rutas_entregas.py --criterio distancia  # minimiza km
python rutas_entregas.py --resumen             # consola sin la tabla de paquetes
python rutas_entregas.py --no-abrir            # no abre el navegador
python rutas_entregas.py --salida 07:30        # hora de salida del depósito (por defecto 08:00)
python rutas_entregas.py --osm                 # todas las calles reales (pip install osmnx)
```

Solo usa la librería estándar de Python. Cada ejecución guarda en la carpeta `salidas/`:

- `mapa_entregas.html`, que se abre solo en el navegador y necesita internet para el mapa base. En él puedes:
  - ver la ruta trazada de cada vehículo, con sus paradas numeradas;
  - hacer clic en una parada para ver sus paquetes: empaque, elemento, alto, ancho, profundidad y peso;
  - abrir el panel lateral con la distancia, el tiempo, las vías recorridas y las paradas;
  - usar **▶ Recorrer ruta** para animar el vehículo sobre el mapa;
  - usar **Ver carga en 3D** para ver cómo quedan acomodados los paquetes;
  - consultar en **⏱️ ¿Cuánto se tarda de A a B?** el tiempo en camión y en moto, la distancia y las vías entre dos puntos cualesquiera, con el camino resaltado en el mapa;
  - abrir **Ver tiempos entre todos los puntos** para ver la matriz completa de tiempos, en camión o moto, o de distancias;
  - revisar en cada vehículo la tabla **Tiempo de cada tramo**, con lo que tarda de una parada a la siguiente y la hora estimada de llegada.
- un archivo `paquetes_<vehiculo>.csv` por vehículo, que se abre en Excel;
- `tiempos_entre_puntos.csv`, con el tiempo en camión y en moto, la distancia y las vías entre todos los pares de puntos;
- el reporte en consola.

## Estructura de carpetas

```
Programacion-Dinamica/
├── rutas_entregas.py          ← el archivo que se ejecuta
├── README.md
├── entregas/                  ← código del proyecto (paquete de Python)
│   ├── principal.py           flota, flujo general, consola y CSV
│   ├── grafo.py               grafo y Dijkstra
│   ├── ruteo.py               barrido, Held-Karp, 2-opt y tiempos entre puntos
│   ├── carga.py               paquetes y acomodo 3D
│   ├── reporte.py             mapa interactivo HTML
│   ├── config.py              rutas de las carpetas
│   └── datos/
│       └── ibague_red_vial.py barrios (nodos) y vías (arcos) de Ibagué
└── salidas/                   ← lo que genera cada ejecución
    ├── mapa_entregas.html
    ├── paquetes_<vehículo>.csv
    ├── tiempos_entre_puntos.csv
    └── salida_ejemplo.txt
```

## Módulos

| Archivo | Contenido | Algoritmos |
|---|---|---|
| `entregas/datos/ibague_red_vial.py` | Barrios de las 13 comunas (nodos) y vías principales (arcos) | — |
| `entregas/grafo.py` | Grafo con lista de adyacencia; cada arco tiene km y km/h | **Dijkstra** O((V+E) log V), Haversine, BFS |
| `entregas/ruteo.py` | Zonas, ruta más eficiente y tiempos entre puntos | **Barrido**, **Held-Karp** O(n²·2ⁿ), **vecino más cercano + 2-opt** |
| `entregas/carga.py` | Paquetes por elemento y acomodo 3D | **Puntos extremos** (bin packing 3D) |
| `entregas/reporte.py` | Mapa interactivo (Leaflet, three.js) | — |
| `entregas/principal.py` | Flota, flujo general, consola y CSV | — |

## Cómo se reparte el trabajo

1. Los barrios se dividen en 4 zonas con el algoritmo de barrido.
2. Las motos toman las 2 zonas más lejanas, porque ahí su mayor velocidad ahorra más tiempo.
3. Dijkstra calcula la distancia y el tiempo mínimos entre cada par de puntos (todos contra todos: P · O((V+E) log V)).
4. Se resuelve el problema del viajero (TSP) para cada vehículo:
   - con 10 paradas o menos, con Held-Karp, que da el óptimo exacto;
   - con más paradas, con vecino más cercano + 2-opt.

## Paquetes

| Elemento | Vehículo | Frágil | Este lado arriba | Soporta encima |
|---|---|---|---|---|
| Electrodoméstico | camión | no | sí | 30 kg |
| Electrónico | camión | **sí** | sí | 0 |
| Vidrio y cerámica | camión | **sí** | sí | 0 |
| Alimentos no perecederos | camión | no | no | 80 kg |
| Ropa y textiles | camión | no | no | 15 kg |
| Ferretería y repuestos | camión | no | no | 100 kg |
| Documentos y sobres | camión y moto | no | no | 5 kg |
| Electrónico pequeño | moto | **sí** | no | 0 |
| Ropa (bolsa pequeña) | moto | no | no | 8 kg |
| Medicamentos | moto | no | sí | 5 kg |

Además, en todos los vehículos:

- Lo que pesa más de 25 kg va en el piso.
- Al menos el 70 % de la base de cada paquete debe quedar apoyada.
- Lo último que se entrega se carga al fondo (LIFO).

## Notas

- Las coordenadas de los barrios son aproximadas y se pueden ajustar en `entregas/datos/ibague_red_vial.py`.
- En el mapa, la línea de cada ruta se ajusta a las calles reales con el servicio público OSRM. Ese ajuste es solo visual: los km y minutos del reporte son los que calcula Dijkstra sobre el grafo del proyecto.
- Con `--osm`, la red de calles de OpenStreetMap se descarga una sola vez y se guarda en `entregas/datos/ibague_calles.graphml`. En ese modo el grafo es dirigido, así que respeta las calles de un solo sentido.
