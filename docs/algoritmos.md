# Algoritmos de Ruteo para Recoleccion de Residuos - Chachapoyas

## 1. Datos y Preprocesamiento

El grafo vial se descarga de OpenStreetMap (~846 nodos, 2399 aristas) y pasa por:

- **Correccion manual**: nodos/aristas editados via editor web interactivo.
- **Deduplicacion de aristas**: se eliminan 44 aristas identicas (key=0 y key=1) duplicadas durante la normalizacion del grafo.
- **Asignacion estatica de sectores**: el clustering se ejecuta una sola vez; los centroides se guardan en `sectores.json` y las ejecuciones posteriores cargan la asignacion desde ahi. Los nodos nuevos se asignan al centroide mas cercano por distancia euclidiana.

**Grafo final**: 489 nodos, 1088 aristas (dirigido, multigrafo).

**Distribucion de sectores**:
| Sector | Calles a servir | Kilometros |
|--------|----------------|------------|
| S0     | 72 nodos       | 29.13 km   |
| S1     | 135 nodos      | 24.39 km   |
| S2     | 22 nodos       | 13.93 km   |
| S3     | 103 nodos      | 19.79 km   |
| S4     | 155 nodos      | 32.83 km   |
| **Total** | **487 nodos** | **120.06 km** |

---

## 2. Clustering (Zonificacion)

Se usa **K-Means** con `k=5` sobre las coordenadas `(x, y)` de todos los nodos. Luego se aplican ajustes manuales espaciales:

- **S3 -> S1**: calles en la zona izquierda-superior de S1 reasignadas.
- **S4 -> S2**: calles con coordenada `y` mas cercana a S2.
- **S4 -> S0**: calles con conexion vial directa a S0.
- **Reparacion de nodos aislados**: BFS desde cada sector para reconectar componentes desconectados.

El resultado se guarda en `sectores.json` con centroides fijos. El editor web y los algoritmos cargan esta asignacion estatica.

---

## 3. Algoritmos de Ruteo

Los 3 algoritmos reciben un sector (conjunto de aristas a servir) y un nodo deposito comun, y producen una ruta que empieza y termina en el deposito, recorriendo todas las aristas del sector.

### 3.1 Voraz (Greedy)

**Enfoque**: Construye la ruta incrementalmente.

1. Desde el deposito, viaja al nodo no servido mas cercano (Dijkstra).
2. Sirve la arista mas cercana a la posicion actual.
3. Repite hasta servir todas las aristas del sector.
4. Retorna al deposito por la ruta mas corta.

**Ventaja**: Simple y rapido (~1 s por sector).
**Desventaja**: Sin optimizacion global; redundancia alta (~1.94).

### 3.2 DCPP (Directed Chinese Postman Problem)

**Enfoque**: Solucion optima para el Problema del Cartero Chino en grafos dirigidos.

1. **Subgrafo requerido**: extrae las aristas del sector.
2. **Balanceo**: calcula el desbalance (grado entrada - grado salida) de cada nodo.
3. **Algoritmo Hungaro** (Kuhn-Munkres): empareja nodos con superavit y deficit de grado para minimizar la distancia total de los caminos de rebalanceo.
4. **Expansion de aristas fantasma**: los caminos mas cortos del matching se anaden al grafo con penalizacion (x100) sobre aristas ya servidas para desincentivar reuso.
5. **Hierholzer**: encuentra un circuito Euleriano en el grafo balanceado.
6. **Conexion al deposito**: ruta de ida y vuelta desde/hacia el deposito.

**Resultado**: Mejor algoritmo en los 5 sectores. Redundancia promedio: ~1.59.

**Observacion**: algunas calles near el deposito pueden ser recorridas 4-7 veces; la compresion forzada a <=3 usos duplica la distancia total, por lo que se acepta el sobreuso como compromiso.

### 3.3 CARP + Tabu Search

**Enfoque**: Solucion aproximada al Capacitated Arc Routing Problem con busqueda Tabu.

1. **Construccion inicial**: ruta Voraz con capacidad maxima de 30 km por viaje (multiple viajes si es necesario).
2. **Busqueda Tabu**: intercambia segmentos de ruta entre viajes para minimizar la distancia total.
   - Vecindad: mover una arista servida de un viaje a otro.
   - Memoria Tabu: evita repetir movimientos recientes (10 iteraciones).
   - Criterio de aspiracion: acepta movimientos Tabu si mejoran la mejor solucion global.
3. **150 iteraciones** por sector.

**Resultado**: Similar al Voraz en sectores con baja capacidad ociosa (S1, S4). Mejora ~5.7% en S0. Promedio: ~1.91 de redundancia.

---

## 4. Resultados Comparativos

Ejecutado con Python 3.10.4, CPU desconocido, velocidad asumida 5 km/h.

```
==========================================================================================
  RUTEO DE RECOLECCION DE RESIDUOS - CHACHAPOYAS
  Algoritmos: Voraz (Greedy) | DCPP (Min-Cost Flow + Hierholzer) | CARP + Tabu Search
  Velocidad asumida: 5 km/h  |  Capacidad CARP: 30 km por viaje
==========================================================================================

Total calles a servir: 120.06 km en 5 sectores

==========================================================================================
Sector          Algoritmo   Dist(km)   Serv(km)   Redund  Tiempo(h)   CPU(s)
------------------------------------------------------------------------------------------
     0              Voraz      50.15      29.13    1.722      10.03    0.730
     1              Voraz      52.45      24.39    2.150      10.49    1.068
     2              Voraz      31.22      13.93    2.242       6.24    0.286
     3              Voraz      39.87      19.79    2.015       7.97    0.838
     4              Voraz      51.99      32.83    1.584      10.40    1.273
------------------------------------------------------------------------------------------
     0               DCPP      39.93      29.13    1.371       7.99    0.154  imb=16
     1               DCPP      37.43      24.39    1.534       7.49    0.202  imb=12
     2               DCPP      27.38      13.93    1.966       5.48    0.154  imb=3
     3               DCPP      31.62      19.79    1.598       6.32    0.153  imb=3
     4               DCPP      48.19      32.83    1.468       9.64    0.288  imb=48
------------------------------------------------------------------------------------------
     0          CARP+Tabu      47.28      29.13    1.623       9.46    3.878  mej=5.7%
     1          CARP+Tabu      52.45      24.39    2.150      10.49   10.917  mej=0.0%
     2          CARP+Tabu      30.76      13.93    2.209       6.15    0.832  mej=1.5%
     3          CARP+Tabu      39.73      19.79    2.008       7.95    4.712  mej=0.4%
     4          CARP+Tabu      51.99      32.83    1.584      10.40   12.923  mej=0.0%
==========================================================================================

                ALGORITMO    TOT(km)   REDUND  TIEMPO(h)   CPU(s)
------------------------------------------------------------------------------------------
 TOTAL              Voraz     225.68    1.942      45.14    4.195
 TOTAL               DCPP     184.54    1.587      36.91    0.951
 TOTAL          CARP+Tabu     222.21    1.915      44.44   33.262
==========================================================================================

--- Mejor algoritmo por sector (menor distancia) ---
  Sector 0: DCPP (39.93 km)
  Sector 1: DCPP (37.43 km)
  Sector 2: DCPP (27.38 km)
  Sector 3: DCPP (31.62 km)
  Sector 4: DCPP (48.19 km)
```

---

## 5. Conclusiones

- **DCPP domina en todos los sectores** con la menor distancia total (184.54 km) y la menor redundancia (1.587). Tambien es el mas rapido en CPU (~1 s total).
- **CARP+Tabu** solo mejora al Voraz en S0 (5.7%) y marginalmente en S2/S3; en S1 y S4 no encuentra mejoria porque la capacidad de 30 km no permite reagrupar viajes de forma significativa.
- **Voraz** es una linea base solida pero consistentemente superada por DCPP.
- La zonificacion K-Means con ajustes manuales produce sectores conectados y balanceados (120 km totales de servicio).
- El visor interactivo (`visor_rutas.html`) permite inspeccionar visualmente la ruta del sector 2 con animacion del recorrido.
