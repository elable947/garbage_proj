# Garbage Route Optimization - Chachapoyas

Optimización de rutas de recolección de residuos sólidos para la ciudad de Chachapoyas, Amazonas, Perú, utilizando algoritmos de ruteo sobre grafos dirigidos.

---

## Flujo de ejecución de scripts

```
1. grafo_chachapoyas.py        Descarga la red vial de OSM
         |
2. editor_grafo_chachapoyas.py Edita/corrige el grafo manualmente
         |
3. dedup_edges.py              Elimina aristas duplicadas
         |
4. zonificacion_kmeans.py      Divide la ciudad en 5 sectores (K-Means)
         |
5. main.py                     Ejecuta los 3 algoritmos de ruteo y compara
    ├── voraz.py               Algoritmo Greedy (baseline)
    ├── dcpp.py                Chinese Postman Problem óptimo
    └── carp_tabu.py           CARP + Búsqueda Tabú
         |
6. visor_rutas.py              Genera visor HTML interactivo con animación
```

---

## Scripts y funcionalidades

### 1. `src/grafo_chachapoyas.py`
Descarga la red vial de Chachapoyas desde OpenStreetMap usando OSMnx.
- **Input:** Coordenadas de Chachapoyas (hardcoded)
- **Output:** `data/grafo_chachapoyas_original.graphml`
- **Parámetros:** Radio 3 km, tipo `drive`, simplificación automática
- **Uso:** `python src/grafo_chachapoyas.py`

### 2. `src/editor_grafo_chachapoyas.py`
Editor web interactivo del grafo vial (servidor HTTP propio, sin Flask).
- **Carga:** `data/grafo_chachapoyas_corregido.graphml` (o crea copia del original)
- **Output:** `data/grafo_chachapoyas_corregido.graphml` + backup automático en `backups/`
- **Funcionalidades:**
  - Visualización del grafo sobre OpenStreetMap + Leaflet.js
  - Crear/eliminar/mover nodos (drag & drop)
  - Crear/eliminar/dividir aristas
  - Agregar puntos de control a geometrías
  - Cambiar dirección de aristas (ida/vuelta/doble sentido)
  - Simplificar nodos de grado 2 (bypass)
  - Restaurar nodos/aristas eliminados (papelera)
  - Validación topológica del grafo
  - Guardado atómico con respaldo
- **Uso:** `python src/editor_grafo_chachapoyas.py` → abre `http://localhost:8000`

### 3. `src/dedup_edges.py`
Elimina aristas paralelas duplicadas (mismo par u→v con múltiples keys) de los 3 archivos GraphML.
- **Input:** `data/grafo_chachapoyas_{original,corregido,sectorizado}.graphml`
- **Uso:** `python src/dedup_edges.py`

### 4. `src/zonificacion_kmeans.py`
Divide el grafo en 5 sectores operativos usando K-Means sobre coordenadas de nodos.
- **Input:** `data/grafo_chachapoyas_corregido.graphml`
- **Output:**
  - `data/grafo_chachapoyas_sectorizado.graphml` (grafo con atributo `sector` por nodo)
  - `data/sectores.json` (asignación estática nodo→sector + centroides)
  - `outputs/zonificacion_kmeans.png` (visualización con fronteras Voronoi)
- **Funcionalidades:**
  - K-Means con k=5 y `random_state=42` (determinístico)
  - Ajustes manuales espaciales (S3→S1, S4→S2, S4→S0 por cercanía y conectividad vial)
  - Reparación de nodos aislados (re-asignación al sector vecino más frecuente)
  - Nodos excluidos (depósito y conector) marcados como sector -1
  - Ejecución estática: carga centroides guardados sin re-clusterizar
  - Flag `--recluster` para forzar nuevo K-Means
- **Uso:** `python src/zonificacion_kmeans.py` o `python src/zonificacion_kmeans.py --recluster`

### 5. `src/visor_live_sectores.py`
Visor web interactivo en vivo de los sectores (servidor HTTP propio).
- **Carga:** `data/grafo_chachapoyas_sectorizado.graphml` (fallback a `corregido`)
- **Funcionalidades:**
  - Mapa Leaflet.js con nodos y aristas coloreados por sector
  - Leyenda interactiva: click en un sector para ocultarlo/mostrarlo
  - Click en nodo: muestra ID, sector, coordenadas (con botón copiar)
  - Click en arista: muestra ID, sector, longitud, dirección, extremos (con botón copiar)
  - Recarga de datos vía API `/api/sectors` (solo recargar navegador)
- **Uso:** `python src/visor_live_sectores.py` → abre `http://localhost:8000`

### 6. `src/main.py`
Orquestador principal. Ejecuta los 3 algoritmos sobre los 5 sectores y muestra tabla comparativa.
- **Input:** `data/grafo_chachapoyas_corregido.graphml` + `data/sectores.json`
- **Output:** Tabla en consola con distancias, redundancia, tiempo estimado y CPU
- **Algoritmos:**
  - **Voraz (Greedy):** Ruta incremental, siempre a la arista no servida más cercana
  - **DCPP:** Chinese Postman Problem óptimo (Hungarian + Hierholzer)
  - **CARP + Tabú:** Capacitated Arc Routing Problem con búsqueda Tabú (2-opt, relocate)
- **Uso:** `python src/main.py`
- **Modo detallado:** ejecutar `main_detailed()` para ver ruta completa de un algoritmo/sector

### 7. `src/visor_rutas.py`
Genera un visor HTML interactivo con las rutas DCPP de los 5 sectores y animación del carrito en Sector 2.
- **Output:** `outputs/visor_rutas.html`
- **Funcionalidades:**
  - Mapa Leaflet.js con rutas de los 5 sectores en colores distintivos
  - Animación del carrito recorriendo el circuito Euleriano del Sector 2
  - Retorno al depósito vía Dijkstra (implementación scratch) con animación
  - Controles: Play/Pause, Reset, Velocidad ajustable
  - Leyenda con distancias por sector
  - Cálculo DCPP completo embebido en el HTML generado
- **Uso:** `python -m src.visor_rutas`

### 8. `src/_data.py`
Módulo compartido de carga de datos. Usado por voraz.py, dcpp.py y carp_tabu.py.
- Carga el grafo corregido, asigna sectores desde `sectores.json`
- Prepara: `G` (dirigido), `Gu` (no dirigido), `depot`, `sector_edges`
- Las rutas son absolutas respecto al directorio del script

### 9. `src/dijkstra.py`
Implementación desde cero del algoritmo de Dijkstra con heap binario.
- Funciones: `dijkstra()`, `shortest_path()`, `build_adjacency()`
- Usado por `visor_rutas.py` para el retorno al depósito

---

## Archivos de datos

| Archivo | Descripción |
|---------|-------------|
| `data/grafo_chachapoyas_original.graphml` | Red vial original de OSM (~846 nodos, 2389 aristas) |
| `data/grafo_chachapoyas_corregido.graphml` | Grafo corregido/limpiado manualmente (~256 nodos, 646 aristas) |
| `data/grafo_chachapoyas_sectorizado.graphml` | Grafo con asignación de sectores por nodo |
| `data/sectores.json` | Mapa estático nodo→sector + coordenadas de centroides |
| `outputs/visor_rutas.html` | Visor interactivo de rutas generado |
| `outputs/zonificacion_kmeans.png` | Visualización de la zonificación K-Means |
| `cache/` | Caché de solicitudes OSMnx |

---

## Resultados comparativos (3 algoritmos × 5 sectores)

```
                           TOTAL(km)   REDUND   TIEMPO(h)   CPU(s)
Voraz                       217.27     2.011      43.45      0.315
DCPP (óptimo)               169.82     1.501      33.96      0.114
CARP + Tabú                 208.59     1.918      41.72      2.930
```

DCPP es el mejor algoritmo en todos los sectores (21.8% mejor que Voraz).

---

## Requisitos

- Python >= 3.10
- Dependencias: `networkx`, `numpy`, `osmnx`, `scikit-learn`, `matplotlib`, `shapely`, `pyproj`
- Instalación: `uv sync` o `pip install -e .`
