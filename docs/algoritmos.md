# Algoritmos de Ruteo para Recolección de Residuos — Chachapoyas

## 1. Datos y Preprocesamiento

El grafo vial se descarga de OpenStreetMap (~846 nodos, 2399 aristas) y pasa por:

- **Corrección manual**: nodos/aristas editados vía editor web interactivo (`editor_grafo_chachapoyas.py`).
- **Deduplicación de aristas**: se eliminan aristas idénticas de los 3 archivos GraphML.
- **Exclusión de rutas al depósito**: 4 nodos y 3 aristas marcados como sector −1 (7.21 km de vías de tránsito).
- **Zonificación**: region-growing desde semillas geográficas sobre el grafo no dirigido, garantizando conectividad y balance de carga.

**Grafo corregido final**: 256 nodos, 646 aristas (dirigido, multigrafo).

| Sector | Nodos | Aristas | Kilómetros |
|--------|-------|---------|------------|
| S0 | 36 | 93 | 20.97 km |
| S1 | 33 | 90 | 22.50 km |
| S2 | 39 | 107 | 23.33 km |
| S3 | 51 | 137 | 22.12 km |
| S4 | 93 | 213 | 22.35 km |
| **Total** | **252** | **640** | **111.27 km** |

---

## 2. Zonificación — Region-Growing

Se usa **region-growing** con 5 semillas distribuidas geográficamente (4 esquinas + centro). El BFS expande sectores simultáneamente hasta alcanzar el target de ~22.25 km por sector, con post-balanceo por adyacencia y reparación de conectividad.

- **Balance de km**: 1.16x (max/min), mejora del 44% vs K-Means (1.68x).
- **Balance de tiempo DCPP**: 1.11x (max/min), mejora del 70% (antes 3.39x).
- Garantiza conectividad vial de cada sector por construcción.

---

## 3. Algoritmos de Ruteo

### 3.1 Voraz (Greedy Baseline)
Ruta incremental: siempre a la arista no servida más cercana (Dijkstra con caché). Simple, rápido (~0.06 s/sector), redundancia ~1.90.

### 3.2 DCPP (Directed Chinese Postman Problem)
Solución óptima: desbalance de grados → Húngaro (sink→source) → Hierholzer. Soporta múltiples componentes débilmente conexas del subgrafo requerido.

### 3.3 CARP + Tabu Search
Construcción golosa + búsqueda Tabú con 2-opt y relocate. Capacidad 30 km/viaje, memoria 15 iteraciones.

### 3.4 CARP-Ulusoy (Route-first-cluster-second) ★
Parte del circuito Euleriano del DCPP y corta en viajes de 30 km. **Sin penalización** en deadhead — permite reuso de calles servidas para minimizar distancia total.

### 3.5 MCPP (Modelo no dirigido, validación)
Trata todas las aristas como no dirigidas (una sola pasada por calle). Matching de nodos de grado impar + Euleriano.

---

## 4. Resultados Comparativos

Ejecutado con Python 3.10, velocidad 5 km/h, capacidad CARP 30 km.

```
==========================================================================================
Sector          Algoritmo   Dist(km)   Serv(km)   Redund  Tiempo(h)   CPU(s)
------------------------------------------------------------------------------------------
     0              Voraz      42.60      20.97    2.031       8.52    0.049
     1              Voraz      39.09      22.50    1.738       7.82    0.047
     2              Voraz      44.17      23.33    1.893       8.83    0.060
     3              Voraz      41.30      22.12    1.867       8.26    0.066
     4              Voraz      44.26      22.35    1.980       8.85    0.094
------------------------------------------------------------------------------------------
     0               DCPP      35.06      20.97    1.672       7.01    0.021  imb=17
     1               DCPP      33.80      22.50    1.502       6.76    0.023  imb=7
     2               DCPP      35.29      23.33    1.513       7.06    0.020  imb=16
     3               DCPP      35.26      22.12    1.594       7.05    0.019  imb=13
     4               DCPP      37.48      22.35    1.677       7.50    0.036  imb=44
------------------------------------------------------------------------------------------
     0          CARP+Tabu      39.47      20.97    1.883       7.89    0.380  mej=7.3%
     1          CARP+Tabu      38.49      22.50    1.711       7.70    0.286  mej=1.5%
     2          CARP+Tabu      42.52      23.33    1.823       8.50    0.299  mej=3.7%
     3          CARP+Tabu      41.30      22.12    1.867       8.26    0.436  mej=0.0%
     4          CARP+Tabu      44.26      22.35    1.980       8.85    1.157  mej=0.0%
------------------------------------------------------------------------------------------
     0        CARP-Ulusoy      27.27      20.97    1.301       5.45    0.057  viajes=1
     1        CARP-Ulusoy      27.53      22.50    1.224       5.51    0.044  viajes=1
     2        CARP-Ulusoy      27.64      23.33    1.185       5.53    0.052  viajes=1
     3        CARP-Ulusoy      28.10      22.12    1.270       5.62    0.060  viajes=1
     4        CARP-Ulusoy      26.87      22.35    1.202       5.37    0.101  viajes=1
------------------------------------------------------------------------------------------
     0               MCPP      35.80      12.05    2.970       7.16    0.027  odd=32
     1               MCPP      31.88      11.87    2.686       6.38    0.024  odd=28
     2               MCPP      36.02      13.49    2.671       7.20    0.036  odd=40
     3               MCPP      33.82      12.00    2.819       6.76    0.030  odd=38
     4               MCPP      40.58      18.68    2.172       8.12    0.041  odd=58
==========================================================================================

                ALGORITMO    TOT(km)   REDUND  TIEMPO(h)   CPU(s)
------------------------------------------------------------------------------------------
 TOTAL              Voraz     211.41    1.902      42.28    0.315
 TOTAL               DCPP     176.89    1.592      35.38    0.120
 TOTAL          CARP+Tabu     206.04    1.853      41.21    2.558
 TOTAL        CARP-Ulusoy     137.42    1.236      27.48    0.314
 TOTAL               MCPP     178.10    2.664      35.62    0.159
==========================================================================================
```

**Rigor estadístico (10 corridas, CARP+Tabu):** 207.09 ± 0.67 km (CPU: 2.490 ± 0.047 s).

---

## 5. Conclusiones

- **CARP-Ulusoy domina en todos los sectores** con 137.42 km totales (35.0% mejor que Voraz, 22.3% mejor que DCPP). La clave es usar el orden del circuito óptimo del DCPP sin penalización de deadhead.
- **Region-growing** logra sectores balanceados (1.16x km, 1.11x tiempo) eliminando los ajustes manuales y la reparación BFS del K-Means.
- **DCPP (176.89 km)** sigue siendo competitivo pero limitado por la penalización ×100 en deadhead.
- **MCPP (178.10 km)** valida que el modelo dirigido no infla distancias — por el contrario, el modelo no dirigido genera más deadhead por mayor número de nodos impares.
- **CARP+Tabu (206 km)** queda como referencia secundaria, superado por Ulusoy en rapidez y calidad.
