# Desarrollo de Sistema Profesional de Corrección, Edición y Validación de Grafo Vial para Chachapoyas

## Contexto del Proyecto

Se requiere desarrollar una solución completa en Python para obtener, visualizar, corregir, editar, validar y persistir un grafo vial del distrito de Chachapoyas a partir de datos de OpenStreetMap (OSM).

El objetivo final no es únicamente visualizar el mapa, sino construir un grafo vial limpio, corregido y topológicamente consistente que posteriormente será utilizado para algoritmos de grafos orientados a:

* Ruta más corta (Shortest Path).
* Dijkstra.
* A*.
* Bellman-Ford.
* Floyd-Warshall.
* Yen K-Shortest Paths.
* Vehicle Routing Problem (VRP).
* Traveling Salesman Problem (TSP).
* Optimización logística.
* Optimización de rutas de transporte.
* Optimización de distribución de mercancías.

Por esta razón, la integridad de los nodos, aristas y especialmente de los pesos de las aristas es crítica.

---

# Objetivos Principales

1. Descargar la red vial de Chachapoyas desde OpenStreetMap.
2. Exportar el grafo original sin modificaciones.
3. Visualizar el grafo mediante una interfaz web local interactiva.
4. Corregir errores presentes en OpenStreetMap.
5. Crear, editar y eliminar nodos.
6. Crear, editar y eliminar aristas.
7. Corregir sentidos de circulación.
8. Corregir conexiones erróneas.
9. Recuperar elementos eliminados.
10. Guardar permanentemente todas las modificaciones.
11. Mantener una copia intacta del grafo original.
12. Generar un grafo corregido listo para algoritmos de optimización de rutas.

---

# Archivos a Generar

## Script 1

```text
grafo_chachapoyas.py
```

Responsabilidades:

* Descargar datos desde OSM.
* Construir el grafo vial.
* Exportar:

```text
grafo_chachapoyas_original.graphml
```

---

## Script 2

```text
editor_grafo_chachapoyas.py
```

Responsabilidades:

* Cargar el grafo original.
* Cargar el grafo corregido si existe.
* Iniciar servidor local.
* Mostrar mapa interactivo.
* Permitir edición avanzada.
* Guardar modificaciones.

---

# Archivos Resultantes

## Grafo Original

```text
grafo_chachapoyas_original.graphml
```

Nunca debe modificarse.

Actúa como respaldo permanente.

---

## Grafo Corregido

```text
grafo_chachapoyas_corregido.graphml
```

Contendrá todas las correcciones realizadas.

---

# Restricciones Técnicas

Antes de implementar la solución:

```bash
uv pip list
```

Analizar las librerías disponibles y aprovecharlas cuando sea posible.

Todos los scripts deben ejecutarse mediante:

```bash
uv run grafo_chachapoyas.py

uv run editor_grafo_chachapoyas.py
```

---

# Tecnologías Deseadas

Priorizar:

* Python
* OSMnx
* NetworkX
* Folium
* Leaflet
* Flask o FastAPI
* Shapely
* Geopy
* PyProj
* GeoPandas

---

# Tipo de Grafo

Utilizar:

```python
networkx.MultiDiGraph
```

porque:

* Permite múltiples aristas.
* Permite calles paralelas.
* Permite sentidos distintos.
* Es compatible con OSMnx.

---

# Interfaz de Edición

La interfaz debe ejecutarse localmente.

Ejemplo:

```text
http://localhost:5000
```

o similar.

Al iniciar el script:

* Debe abrirse automáticamente el navegador.
* Debe cargarse el mapa.
* Debe visualizarse el grafo completo.

---

# Funcionalidades del Mapa

La interfaz debe soportar:

* Zoom.
* Pan.
* Selección de nodos.
* Selección de aristas.
* Creación de nodos.
* Creación de aristas.
* Edición de geometrías.
* Eliminación.
* Restauración.
* Guardado.

Todo debe visualizarse en tiempo real.

No debe ser necesario recargar la página.

---

# Creación de Nodos

## Modo Crear Nodo

El usuario selecciona:

```text
Crear Nodo
```

Luego realiza un click sobre cualquier ubicación del mapa.

El sistema debe:

1. Obtener automáticamente la latitud.
2. Obtener automáticamente la longitud.
3. Crear el nodo.
4. Mostrarlo inmediatamente.

No se solicitarán coordenadas manualmente.

---

# Generación Automática de ID

El ID del nodo debe generarse automáticamente.

Opciones válidas:

```python
uuid.uuid4()
```

o

```python
max(existing_nodes)+1
```

o cualquier mecanismo robusto.

El usuario nunca ingresará IDs manualmente.

---

# Movimiento de Nodos

Los nodos deben poder moverse mediante drag-and-drop.

Al mover un nodo:

* Su posición cambia inmediatamente.
* Las aristas conectadas se actualizan visualmente.

---

# Creación Visual de Aristas

La creación debe ser completamente interactiva.

## Flujo

Seleccionar:

```text
Crear Arista
```

### Paso 1

Click sobre nodo origen.

### Paso 2

Aparece una línea temporal.

La línea debe seguir al cursor en tiempo real.

Ejemplo:

```text
Nodo A ---------- Cursor
```

### Paso 3

Click sobre nodo destino.

La arista queda creada.

---

# Renderizado en Tiempo Real

La nueva arista debe aparecer instantáneamente.

No debe requerirse guardar.

---

# Geometría de Aristas

NO utilizar únicamente:

```python
(source, target)
```

Todas las aristas deben almacenar geometría completa.

Utilizar:

```python
shapely.geometry.LineString
```

---

# Edición Geométrica Avanzada

Las aristas deben comportarse como elementos editables.

Similar a:

* QGIS
* ArcGIS
* JOSM

---

# Inserción de Puntos de Control

Click derecho sobre una arista:

```text
Agregar Punto de Control
```

Se crea un vértice intermedio.

---

# Arrastre de Geometría

El usuario debe poder:

* Tomar un punto de control.
* Arrastrarlo.
* Curvar la arista.
* Modificar la trayectoria.

La experiencia debe sentirse como estirar un hilo.

---

# Múltiples Puntos de Control

Una arista puede contener:

```text
A --●--●--●-- B
```

Todos los puntos deben ser editables.

---

# Edición de Aristas Existentes

Las aristas provenientes de OSM deben poder:

* Cambiar geometría.
* Cambiar sentido.
* Cambiar atributos.
* Eliminarse.
* Restaurarse.

Exactamente igual que las nuevas.

---

# Metadatos Críticos de las Aristas

Cada arista debe almacenar obligatoriamente:

```python
{
    "source": nodo_origen,
    "target": nodo_destino,
    "length": distancia_metros,
    "oneway": True/False,
    "geometry": LineString(...)
}
```

---

# Importancia de los Pesos

El atributo más importante es:

```python
length
```

porque será utilizado posteriormente como:

```python
weight="length"
```

en algoritmos de optimización.

Por tanto:

* Debe recalcularse correctamente.
* Debe mantenerse actualizado.
* Debe ser consistente con la geometría real.

---

# Cálculo Automático de Distancias

Cuando una arista se cree o modifique:

El sistema debe recalcular automáticamente:

```python
length
```

utilizando:

* Shapely
* Geopy
* PyProj

o herramientas equivalentes.

La distancia debe aproximar la longitud real de la calle en metros.

---

# Sentido de Circulación

Cada arista debe almacenar:

```python
oneway
```

Valores:

```python
True
False
```

---

# Corrección de Calles

El sistema debe permitir corregir errores de OSM.

Ejemplos:

* Sentido invertido.
* Doble vía incorrecta.
* Calle desconectada.
* Calle conectada erróneamente.
* Arista faltante.
* Arista duplicada.

---

# Eliminación de Nodos

Debe ser posible:

```text
Eliminar Nodo
```

La eliminación debe reflejarse inmediatamente.

---

# Eliminación de Aristas

Debe ser posible:

```text
Eliminar Arista
```

La eliminación debe reflejarse inmediatamente.

---

# Sistema de Restauración

Debe existir una herramienta:

```text
Restaurar Elementos
```

---

# Restauración de Nodos

Debe recuperar nodos eliminados desde:

```text
grafo_chachapoyas_original.graphml
```

---

# Restauración de Aristas

Debe recuperar aristas eliminadas desde:

```text
grafo_chachapoyas_original.graphml
```

---

# Persistencia

Al presionar:

```text
Guardar Cambios
```

debe ocurrir:

1. Validación topológica.
2. Recalcular geometrías.
3. Recalcular distancias.
4. Actualizar atributos.
5. Exportar.

---

# Archivo de Salida

Guardar en:

```text
grafo_chachapoyas_corregido.graphml
```

---

# Validación Antes de Guardar

Verificar:

* Nodos huérfanos.
* Aristas inválidas.
* Geometrías corruptas.
* Longitudes negativas.
* Conexiones inconsistentes.
* IDs duplicados.

---

# Escalabilidad

La solución debe ser capaz de manejar:

* Miles de nodos.
* Miles de aristas.

sin degradación severa del rendimiento.

---

# Resultado Esperado

Al finalizar, el archivo:

```text
grafo_chachapoyas_corregido.graphml
```

debe representar una red vial corregida, validada y lista para utilizarse directamente en algoritmos de optimización de rutas, donde el peso principal de las aristas será la distancia real recorrida en metros almacenada en el atributo:

```python
length
```

garantizando resultados confiables para problemas de navegación, logística y transporte.
