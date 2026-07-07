# Algoritmos de Ruteo para Recolección de Residuos — Chachapoyas

## 1. Datos y Preprocesamiento

El grafo vial se descarga de OpenStreetMap (~846 nodos, 2399 aristas) y pasa por:

- **Corrección manual**: nodos/aristas editados vía editor web interactivo (`editor_grafo_chachapoyas.py`).
- **Deduplicación de aristas**: se eliminan aristas idénticas (misma dirección u→v con múltiples keys) de los 3 archivos GraphML.
- **Exclusión de rutas al depósito**: 4 nodos y 3 aristas marcados como sector −1; representan 7.21 km de vías de tránsito hacia/desde el depósito, no requieren servicio de recolección.
- **Asignación estática de sectores**: el clustering se ejecuta una sola vez; los centroides se guardan en `sectores.json`. Los nodos nuevos se asignan al centroide más cercano por distancia euclidiana.

**Grafo corregido final**: 256 nodos, 646 aristas (dirigido, multigrafo).

**Distribución de sectores**:
| Sector | Nodos | Calles a servir | Kilómetros |
|--------|-------|----------------|------------|
| S0 | 113 | 272 aristas | 32.77 km |
| S1 | 24 | 69 aristas | 19.51 km |
| S2 | 15 | 42 aristas | 11.96 km |
| S3 | 28 | 80 aristas | 20.99 km |
| S4 | 72 | 182 aristas | 26.04 km |
| **Total** | **252** | **645 aristas** | **111.27 km** |

---

## 2. Clustering (Zonificación)

Se usa **K-Means** con `k=5` sobre las coordenadas `(x, y)` de todos los nodos (excluyendo los 4 nodos de acceso al depósito). Luego se aplican ajustes manuales espaciales:

- **S3 → S1**: calles en la zona izquierda-superior de S1 reasignadas.
- **S4 → S2**: calles con coordenada `y` más cercana a S2.
- **S4 → S0**: calles con conexión vial directa a S0.
- **Reparación de nodos aislados**: nodos sin conectividad al resto de su sector se reasignan al sector del vecino más frecuente.

El resultado se guarda en `sectores.json` con centroides fijos y la lista de aristas excluidas. El editor web, los algoritmos y los visores cargan esta asignación estática.

---

## 3. Algoritmos de Ruteo

Los 3 algoritmos reciben un sector (conjunto de aristas a servir) y un nodo depósito común (`af3202cd`), y producen una ruta que empieza y termina en el depósito.

### 3.1 Voraz (Greedy)

**Enfoque**: Construye la ruta incrementalmente.

1. Desde el depósito, viaja al nodo no servido más cercano (Dijkstra con caché de fuente única).
2. Sirve la arista más cercana a la posición actual.
3. Repite hasta servir todas las aristas del sector.
4. Retorna al depósito por la ruta más corta.

**Ventaja**: Simple y rápido (~0.06 s por sector). **Desventaja**: Sin optimización global; redundancia alta (~1.92).

### 3.2 DCPP (Directed Chinese Postman Problem)

**Enfoque**: Solución óptima para el Problema del Cartero Chino en grafos dirigidos.

1. **Subgrafo requerido**: extrae las aristas del sector.
2. **Balanceo**: calcula δ(v) = indeg(v) − outdeg(v) para cada nodo.
3. **Algoritmo Húngaro** (Kuhn-Munkres, O(n³)): empareja nodos sumidero (δ < 0) con nodos fuente (δ > 0) minimizando la distancia total de rebalanceo. **Corrección crítica**: las aristas fantasma se añaden en dirección sink→source (los sumideros necesitan más aristas salientes, las fuentes más entrantes).
4. **Expansión de aristas fantasma**: los caminos más cortos del matching se expanden sobre el grafo no dirigido con penalización (×100) sobre aristas ya servidas para desincentivar reuso del deadhead.
5. **Hierholzer**: circuito Euleriano sobre el grafo balanceado.
6. **Conexión al depósito**: rutas de ida y vuelta por camino más corto.

**Resultado**: Mejor algoritmo en los 5 sectores. Redundancia promedio: 1.428. Distancia total: 169.82 km (21.9% mejor que Voraz).

### 3.3 CARP + Tabu Search

**Enfoque**: Solución al Capacitated Arc Routing Problem con búsqueda Tabú.

1. **Construcción inicial**: ruta Voraz con capacidad máxima de 30 km por viaje (múltiples viajes si es necesario).
2. **Búsqueda Tabú**: explora vecindarios 2-opt (inversión de segmento) y relocate (reinserción de arista).
   - Memoria Tabú: 15 iteraciones.
   - Criterio de aspiracion: acepta movimientos Tabú si mejoran la mejor solución global.
   - Criterio de parada: 80 iteraciones sin mejora o 150 máximo.
3. **Reconstrucción**: expande la secuencia de aristas con caminos más cortos y retornos al depósito.

**Resultado**: Mejoras modestas en S3 (14.8%) y S2 (4.9%). Tiempo CPU elevado (~3.1 s total).

---

## 4. Resultados Comparativos

Ejecutado con Python 3.10, velocidad asumida 5 km/h.

```
==========================================================================================
  RUTEO DE RECOLECCION DE RESIDUOS - CHACHAPOYAS
  Algoritmos: Voraz (Greedy) | DCPP (Min-Cost Flow + Hierholzer) | CARP + Tabu Search
  Velocidad asumida: 5 km/h  |  Capacidad CARP: 30 km por viaje
==========================================================================================

Total calles a servir: 111.27 km en 5 sectores

==========================================================================================
Sector          Algoritmo   Dist(km)   Serv(km)   Redund  Tiempo(h)   CPU(s)
------------------------------------------------------------------------------------------
     0              Voraz      60.07      32.77    1.833      12.01    0.117
     1              Voraz      35.38      19.51    1.814       7.08    0.040
     2              Voraz      29.66      11.96    2.481       5.93    0.036
     3              Voraz      42.22      20.99    2.011       8.44    0.042
     4              Voraz      49.94      26.04    1.917       9.99    0.080
------------------------------------------------------------------------------------------
     0               DCPP      49.44      32.77    1.509       9.89    0.032  imb=45
     1               DCPP      31.38      19.51    1.609       6.28    0.021  imb=3
     2               DCPP      14.62      11.96    1.223       2.92    0.016  imb=7
     3               DCPP      33.60      20.99    1.601       6.72    0.019  imb=11
     4               DCPP      40.78      26.04    1.566       8.16    0.026  imb=21
------------------------------------------------------------------------------------------
     0          CARP+Tabu      59.89      32.77    1.827      11.98    1.671  mej=0.3%
     1          CARP+Tabu      35.03      19.51    1.796       7.01    0.134  mej=1.0%
     2          CARP+Tabu      28.20      11.96    2.358       5.64    0.158  mej=4.9%
     3          CARP+Tabu      35.53      20.99    1.693       7.11    0.255  mej=15.8%
     4          CARP+Tabu      49.94      26.04    1.917       9.99    0.713  mej=0.0%
==========================================================================================

                ALGORITMO    TOT(km)   REDUND  TIEMPO(h)   CPU(s)
------------------------------------------------------------------------------------------
 TOTAL              Voraz     217.27    2.011      43.45    0.315
 TOTAL               DCPP     169.82    1.501      33.96    0.114
 TOTAL          CARP+Tabu     208.59    1.918      41.72    2.930
==========================================================================================

--- Mejor algoritmo por sector (menor distancia) ---
  Sector 0: DCPP (49.44 km)
  Sector 1: DCPP (31.38 km)
  Sector 2: DCPP (14.62 km)
  Sector 3: DCPP (33.60 km)
  Sector 4: DCPP (40.78 km)
```

---

## 5. Conclusiones

- **DCPP domina en todos los sectores** con 169.82 km totales (21.8% mejor que Voraz) y redundancia promedio 1.501.
- **DCPP es también el más rápido** en CPU (0.114 s total), 26× más rápido que CARP+Tabu y 2.8× más rápido que Voraz.
- **CARP+Tabu** solo mejora significativamente en S3 (15.8%); la capacidad de 30 km limita el espacio de búsqueda en sectores con calles naturalmente agrupadas.
- **Voraz** es una línea base sólida pero consistentemente superada por DCPP.
- La zonificación K-Means con ajustes manuales produce sectores conexos y balanceados (111.27 km totales).
- La corrección de la dirección de aristas fantasma (sink→source) fue crítica para la validez del DCPP.
- Los visores interactivos (`visor_rutas.html` y `visor_live_sectores.py`) permiten inspeccionar visualmente rutas y sectores.
