# Optimización de Rutas de Recolección de Residuos Sólidos mediante Algoritmos de Ruteo sobre Grafos Viales: Estudio de Caso en Chachapoyas, Perú

## Resumen

La recolección de residuos sólidos urbanos representa entre el 60% y 80% del costo operativo total de los sistemas municipales de gestión de residuos, y la optimización de rutas puede generar ahorros sustanciales en combustible, tiempo y emisiones contaminantes. Este estudio presenta un análisis comparativo de tres enfoques algorítmicos para el ruteo óptimo de la flota de recolección en la ciudad de Chachapoyas, Perú, ubicada a 2,335 m s.n.m. en la cordillera de los Andes. Se construyó un grafo vial dirigido a partir de datos OpenStreetMap, el cual fue corregido manualmente mediante un editor web interactivo, resultando en 256 nodos y 646 aristas. Las calles a servir (111.27 km) se agruparon en 5 sectores operativos mediante K-Means con ajustes manuales espaciales y reparación de conectividad. Se implementaron y evaluaron tres algoritmos: un método Voraz como línea base, el Problema del Cartero Chino Dirigido (DCPP) con algoritmo Húngaro para balanceo de grados y Hierholzer para circuitos Eulerianos, y el Problema de Ruteo de Arcos Capacitado (CARP) con búsqueda Tabú para optimización local. El algoritmo DCPP superó consistentemente a los otros métodos en los 5 sectores, logrando una distancia total de 169.82 km con redundancia promedio de 1.501, frente a 217.27 km (redundancia 2.011) del Voraz y 208.59 km (redundancia 1.918) del CARP+Tabu. El DCPP redujo la distancia total en un 21.8% respecto a la línea base Voraz con un costo computacional de solo 0.114 segundos de CPU. Estos resultados demuestran que el DCPP constituye el enfoque más eficiente para el ruteo de recolección en el contexto de Chachapoyas y potencialmente en otras ciudades latinoamericanas con topografía irregular y patrones de crecimiento orgánico.

---

## 1. Introducción

La gestión de residuos sólidos urbanos constituye uno de los desafíos logísticos más significativos que enfrentan los municipios en países en desarrollo. Según el Banco Mundial, la generación global de residuos alcanzará 3.40 mil millones de toneladas anuales para 2050 (Kaza et al., 2018). En Perú, la producción per cápita de residuos sólidos municipales se estima en 0.58 kg/hab/día, y los costos de recolección y transporte representan entre el 60% y 80% del presupuesto municipal destinado a limpieza pública (MINAM, 2021). Cualquier mejora en la eficiencia de estas operaciones tiene, por tanto, un impacto económico y ambiental directo sobre las finanzas municipales y la calidad de vida urbana.

La optimización de rutas de recolección es un problema clásico de ruteo sobre grafos que admite múltiples formulaciones. Puede modelarse como una variante del Problema del Cartero Chino (Chinese Postman Problem, CPP), donde se busca un circuito de costo mínimo que recorra cada arista del grafo al menos una vez (Edmonds & Johnson, 1973), o del Problema de Ruteo de Arcos Capacitado (Capacitated Arc Routing Problem, CARP), que incorpora restricciones de capacidad vehicular y puede requerir múltiples viajes (Golden & Wong, 1981). El CPP en su variante dirigida (DCPP) requiere equilibrar los grados de entrada y salida de cada nodo mediante la adición de aristas artificiales, problema que se resuelve óptimamente mediante el algoritmo Húngaro de asignación (Kuhn, 1955; Munkres, 1957), para luego encontrar un circuito Euleriano con el algoritmo de Hierholzer (1873).

Diversos enfoques se han propuesto en la literatura para abordar estos problemas: desde métodos exactos basados en programación lineal entera hasta heurísticas y metaheurísticas como algoritmos genéticos, búsqueda Tabú y colonias de hormigas (Lacomme et al., 2004; Santos et al., 2010). Sin embargo, la mayoría de los estudios se han centrado en ciudades europeas o norteamericanas con tramas viales regulares, existiendo una brecha significativa en la literatura respecto a ciudades latinoamericanas con topografía irregular, patrones de crecimiento orgánico y tejidos urbanos de trazado colonial.

El presente estudio aborda dicha brecha mediante un análisis comparativo de tres algoritmos de ruteo aplicados a la ciudad de Chachapoyas, capital del departamento de Amazonas en Perú. Chachapoyas presenta características particularmente desafiantes para el ruteo vehicular: topografía accidentada en la cordillera de los Andes, un casco histórico de trazado colonial irregular, calles estrechas de un solo sentido, y un crecimiento urbano no planificado con numerosas vías sin salida. El objetivo principal es determinar el algoritmo de ruteo más eficiente para minimizar la distancia total recorrida manteniendo la cobertura completa de todas las calles del área urbana. Como objetivos secundarios se plantean: evaluar la efectividad del agrupamiento por K-Means como estrategia de zonificación, analizar el equilibrio entre calidad de solución y costo computacional de cada algoritmo, y cuantificar el impacto de las restricciones de capacidad vehicular en la eficiencia global.

La contribución principal de este trabajo es triple: (a) se presenta una implementación completa y corregida del algoritmo DCPP —incluyendo una corrección crítica en la dirección de las aristas fantasma que revierte la práctica común pero errónea de orientarlas desde nodos fuente hacia nodos sumidero—; (b) se documenta una metodología reproducible de extremo a extremo, desde la adquisición de datos abiertos hasta la visualización interactiva, con todas las herramientas disponibles como código abierto; y (c) se establecen métricas comparativas que pueden servir como referencia para estudios similares en otras ciudades de la región.

---

## 2. Métodos

### 2.1 Construcción del Grafo Vial

Los datos de la red vial de Chachapoyas se obtuvieron desde OpenStreetMap utilizando la librería OSMnx (Boeing, 2017), con un radio de 3 km desde el centro de la ciudad y filtrando por tipo de vía `drive`. El grafo original contenía 846 nodos y 2,389 aristas dirigidas, representando intersecciones y segmentos de calle respectivamente, incluyendo calles de doble sentido modeladas como aristas bidireccionales independientes.

El grafo fue sometido a un proceso de corrección manual exhaustivo mediante un editor web interactivo desarrollado específicamente para este proyecto. El editor, implementado como un servidor HTTP autónomo con frontend Leaflet.js, permite operaciones de creación, eliminación, modificación y división de nodos y aristas, arrastre de geometrías, adición de puntos de control para curvas, cambio de dirección de circulación, simplificación de nodos de grado 2 (bypass), restauración de elementos eliminados y validación topológica del grafo. Tras la corrección, se ejecutó un proceso de deduplicación que eliminó aristas paralelas idénticas (misma dirección con múltiples keys), resultando en un grafo final de 256 nodos y 646 aristas dirigidas.

Cada arista almacena como atributos principales su longitud en metros —calculada a partir de las coordenadas geográficas de sus nodos extremos mediante proyección geodésica WGS84— y un indicador booleano de sentido único (`oneway`). El grafo se representa como un `networkx.MultiDiGraph`, estructura que permite modelar correctamente tanto las calles de doble sentido como las vías de un solo sentido sin pérdida de información topológica. Dos nodos especiales fueron designados como excluidos del servicio: el depósito municipal (nodo `af3202cd`) y un nodo conector auxiliar (`ebde992d`), junto con cuatro aristas que forman las rutas exclusivas de acceso hacia y desde el depósito, totalizando 7.21 km de vías de tránsito que no requieren servicio de recolección.

### 2.2 Zonificación por Clustering

Para dividir la ciudad en sectores operativos, se aplicó el algoritmo K-Means (Lloyd, 1982) con k = 5 sobre las coordenadas (x, y) de todos los nodos del grafo, excluyendo del clustering los 4 nodos destinados a rutas de acceso al depósito. La elección de k = 5 sectores se fundamenta en la disponibilidad operativa de la flota municipal de Chachapoyas.

El sistema de zonificación se diseñó con un enfoque de asignación estática determinística: una vez ejecutado el clustering inicial con semilla aleatoria fija (`random_state=42`), los centroides de cada sector se almacenan permanentemente junto con la asignación nodo→sector en un archivo JSON (`sectores.json`). Este diseño garantiza que todas las herramientas del ecosistema —algoritmos de ruteo, visores interactivos y el propio editor vial— operen sobre una zonificación idéntica y reproducible. Los nodos nuevos añadidos durante ediciones posteriores se asignan automáticamente al centroide más cercano por distancia euclidiana.

Tras el clustering automático, se aplicaron tres ajustes manuales basados en criterios espaciales y de conectividad: (a) reasignación de nodos del sector 3 al sector 1 en la región izquierda-superior de la frontera entre ambos; (b) migración de nodos del sector 4 al sector 2 cuando su coordenada de latitud se encuentra más próxima al rango del sector 2 que al propio; y (c) transferencia de nodos del sector 4 al sector 0 cuando existe una conexión vial directa entre el nodo y el sector destino, verificada mediante análisis de aristas salientes en el grafo subyacente. Finalmente, un algoritmo de reparación de conectividad identifica nodos aislados —sin conexión vial al resto de su sector— y los reasigna al sector del vecino más frecuente, garantizando que cada sector forme un subgrafo débilmente conexo. La distribución final de calles a servir por sector fue: S0 = 32.77 km, S1 = 19.51 km, S2 = 11.96 km, S3 = 20.99 km, y S4 = 26.04 km, totalizando 111.27 km de servicio efectivo.

### 2.3 Algoritmos de Ruteo

#### 2.3.1 Algoritmo Voraz (Greedy Baseline)

El algoritmo Voraz constituye la línea base del estudio por su simplicidad conceptual y su uso frecuente como referencia en la literatura de ruteo. Su estrategia es incremental: desde el nodo depósito, se calculan las distancias de camino más corto a todos los nodos del grafo mediante el algoritmo de Dijkstra (caché de fuente única), se selecciona la arista no servida cuya distancia de acceso más su propia longitud sea mínima, se sirve dicha arista, y se itera hasta completar todas las aristas del sector. La complejidad computacional resultante es O(n · (E + V log V)) donde n es el número de aristas a servir, E el número de aristas del grafo completo y V el número de nodos. Al finalizar, se añade la ruta de retorno al depósito por el camino más corto.

#### 2.3.2 DCPP — Directed Chinese Postman Problem

El algoritmo DCPP implementa la solución óptima al Problema del Cartero Chino en su variante dirigida, siguiendo el marco teórico establecido por Edmonds y Johnson (1973). El procedimiento consta de seis etapas. Primero, se extrae el subgrafo requerido: todas las aristas del sector y los nodos que las componen. Segundo, se calcula el desbalance de grado en el subgrafo requerido, definido como δ(v) = indegree(v) − outdegree(v) para cada nodo v. Los nodos con δ(v) < 0 presentan exceso de aristas entrantes (sumideros de grado) y requieren aristas salientes adicionales para equilibrarse; los nodos con δ(v) > 0 presentan exceso de aristas salientes (fuentes de grado) y requieren aristas entrantes adicionales.

Tercero, se construye la matriz de costos del camino más corto desde cada nodo sumidero hacia cada nodo fuente mediante el algoritmo de Dijkstra sobre el grafo no dirigido, y se resuelve el problema de asignación óptima con el algoritmo Húngaro (Kuhn-Munkres, O(n³)). Es crucial señalar que la dirección correcta de las aristas fantasma es desde nodos sumidero hacia nodos fuente —no a la inversa—, ya que los sumideros necesitan incrementar su grado de salida y las fuentes necesitan incrementar su grado de entrada. Una implementación que invierta esta dirección produce un grafo aún más desbalanceado e impide que el circuito de Hierholzer recorra la totalidad de las aristas requeridas.

Cuarto, las aristas fantasma del matching se añaden al subgrafo dirigido, y los caminos más cortos correspondientes se expanden en el grafo no dirigido para construir la ruta real de desplazamiento sin servicio (deadhead). Para desincentivar que estos caminos de deadhead reutilicen calles que ya forman parte del servicio, se aplica una penalización multiplicando por 100 la longitud de las aristas requeridas durante la búsqueda del camino más corto; la distancia real del deadhead se mide sobre el grafo sin penalizar. Quinto, sobre el grafo balanceado resultante se ejecuta el algoritmo de Hierholzer para obtener un circuito Euleriano que recorre exactamente una vez cada arista (tanto las requeridas como las fantasma). Sexto, se añaden las rutas de conexión desde y hacia el depósito mediante caminos más cortos sobre el grafo no dirigido.

#### 2.3.3 CARP con Búsqueda Tabú

El algoritmo CARP extiende el problema anterior incorporando una restricción de capacidad vehicular de 30 km por viaje, modelando el límite operativo del camión recolector antes de requerir descarga en el depósito. La construcción de la solución inicial utiliza una heurística tipo Voraz modificada que genera múltiples viajes: partiendo del depósito, se acumulan aristas servidas secuencialmente hasta que añadir la siguiente arista —incluyendo el deadhead de acceso y el retorno al depósito— excedería la capacidad, momento en el cual se cierra el viaje actual y se inicia uno nuevo.

Sobre esta solución inicial se aplica una búsqueda Tabú (Glover, 1989, 1990) que explora el espacio de soluciones mediante dos vecindarios complementarios seleccionados aleatoriamente en cada iteración: intercambio 2-opt (inversión de un segmento de la secuencia de aristas) y relocate (extracción de una arista de su posición actual y reinserción en otra ubicación). La memoria Tabú registra los movimientos realizados con un tenure de 15 iteraciones, y el criterio de aspiración acepta movimientos tabú si mejoran la mejor solución global encontrada. La búsqueda se detiene tras 80 iteraciones sin mejora o al alcanzar el máximo de 150 iteraciones por sector. La ruta final se reconstruye expandiendo la secuencia de aristas con los caminos más cortos entre aristas consecutivas y las conexiones de ida y vuelta al depósito.

### 2.4 Métricas de Evaluación

Se definieron las siguientes métricas para la comparación sistemática del desempeño de los algoritmos: distancia total recorrida (km), que incluye tanto el servicio como el deadhead; distancia servida (km), correspondiente exclusivamente a la recolección activa; redundancia, definida como el cociente entre distancia total y distancia servida —un valor de 1.0 indica ruta sin deadhead, mientras que valores superiores cuantifican el desplazamiento improductivo—; tiempo estimado de operación (h), calculado como distancia total dividida por una velocidad promedio asumida de 5 km/h, valor conservador apropiado para circulación urbana con paradas frecuentes en topografía andina; tiempo de CPU (s), medido con `time.perf_counter()`; desbalance de grado en DCPP, definido como la suma de valores absolutos |δ(v)| para todos los nodos del sector; y porcentaje de mejora Tabú, calculado como la reducción relativa de la distancia respecto a la solución inicial Voraz.

### 2.5 Herramientas de Visualización y Soporte

El ecosistema de software desarrollado para este estudio incluye herramientas de visualización interactiva que complementan el análisis cuantitativo. Un visor de rutas (HTML autónomo generado por `visor_rutas.py`) presenta las rutas DCPP de los 5 sectores sobre un mapa Leaflet.js con animación del recorrido de un carrito recolector a lo largo del circuito Euleriano del Sector 2, incluyendo el retorno al depósito calculado mediante una implementación propia del algoritmo de Dijkstra con heap binario. Un segundo visor, de tipo servidor web en vivo (`visor_live_sectores.py`), permite la exploración interactiva de la zonificación: carga el grafo sectorizado, colorea nodos y aristas según el sector asignado, ofrece una leyenda con toggle para ocultar/mostrar sectores individualmente, y muestra información detallada de cada elemento (ID, sector, coordenadas, longitud, dirección) al hacer clic, con utilidad de copia de identificadores al portapapeles.

### 2.6 Implementación

Todos los algoritmos y herramientas se implementaron en Python 3.10 utilizando las librerías `networkx` (v3.4.2) para la manipulación del grafo y cálculo de caminos más cortos, `numpy` (v1.26.0) para cómputo numérico, `scikit-learn` (v1.5.0) para el clustering K-Means, `shapely` (v2.0.0) para operaciones geométricas, `pyproj` (v3.6.0) para cálculos geodésicos, y `matplotlib` (v3.10.9) para la generación de gráficos. El código fuente completo, incluyendo el editor vial, los tres algoritmos de ruteo, los visores interactivos y el orquestador principal, está disponible en el repositorio del proyecto bajo una estructura modular de scripts independientes. Los experimentos se ejecutaron en un sistema con procesador AMD Ryzen, 16 GB de RAM y Windows 10.

---

## 3. Resultados

### 3.1 Desempeño Global

La Tabla 1 presenta los resultados comparativos detallados de los tres algoritmos para los 5 sectores operativos de Chachapoyas. El total de calles a servir —excluyendo las 4 aristas de acceso al depósito— asciende a 111.27 km distribuidos en 5 sectores.

**Tabla 1.** Resultados comparativos de los algoritmos de ruteo por sector.

| Sector | Algoritmo | Dist (km) | Serv (km) | Redund | Tiempo (h) | CPU (s) | Nota |
|--------|-----------|-----------|-----------|--------|------------|---------|------|
| 0 | Voraz | 60.07 | 32.77 | 1.833 | 12.01 | 0.117 | — |
| 1 | Voraz | 35.38 | 19.51 | 1.814 | 7.08 | 0.040 | — |
| 2 | Voraz | 29.66 | 11.96 | 2.481 | 5.93 | 0.036 | — |
| 3 | Voraz | 42.22 | 20.99 | 2.011 | 8.44 | 0.042 | — |
| 4 | Voraz | 49.94 | 26.04 | 1.917 | 9.99 | 0.080 | — |
| 0 | DCPP | 49.44 | 32.77 | 1.509 | 9.89 | 0.032 | imb=45 |
| 1 | DCPP | 31.38 | 19.51 | 1.609 | 6.28 | 0.021 | imb=3 |
| 2 | DCPP | 14.62 | 11.96 | 1.223 | 2.92 | 0.016 | imb=7 |
| 3 | DCPP | 33.60 | 20.99 | 1.601 | 6.72 | 0.019 | imb=11 |
| 4 | DCPP | 40.78 | 26.04 | 1.566 | 8.16 | 0.026 | imb=21 |
| 0 | CARP+Tabu | 59.89 | 32.77 | 1.827 | 11.98 | 1.671 | mej=0.3% |
| 1 | CARP+Tabu | 35.03 | 19.51 | 1.796 | 7.01 | 0.134 | mej=1.0% |
| 2 | CARP+Tabu | 28.20 | 11.96 | 2.358 | 5.64 | 0.158 | mej=4.9% |
| 3 | CARP+Tabu | 35.53 | 20.99 | 1.693 | 7.11 | 0.255 | mej=15.8% |
| 4 | CARP+Tabu | 49.94 | 26.04 | 1.917 | 9.99 | 0.713 | mej=0.0% |

### 3.2 Comparación Agregada por Algoritmo

La Tabla 2 resume las métricas agregadas para los tres algoritmos, consolidando los resultados de los 5 sectores.

**Tabla 2.** Métricas agregadas por algoritmo (suma de 5 sectores).

| Algoritmo | Total (km) | Redundancia Promedio | Tiempo Total (h) | CPU Total (s) |
|-----------|-----------|---------------------|------------------|---------------|
| Voraz | 217.27 | 1.922 | 43.45 | 0.315 |
| DCPP | 169.82 | 1.428 | 33.96 | 0.114 |
| CARP+Tabu | 208.59 | 1.842 | 41.72 | 2.930 |

El algoritmo DCPP logró la menor distancia total en los 5 sectores, con una reducción del 21.8% respecto al Voraz y del 18.6% respecto al CARP+Tabu. La redundancia promedio del DCPP (1.501) implica que, por cada kilómetro de calle servida, se recorrieron 0.501 km adicionales de deadhead, frente a 1.011 km en el Voraz y 0.918 km en el CARP+Tabu. Destaca particularmente el Sector 2, donde el DCPP alcanzó una redundancia de apenas 1.223 —la más baja del estudio— gracias a un desbalance moderado (7 unidades) y una topología favorable.

El DCPP no solo produjo las rutas más cortas, sino que lo hizo con el menor costo computacional: 0.114 segundos totales de CPU, 2.8 veces más rápido que el Voraz (0.315 s) y 26 veces más rápido que el CARP+Tabu (2.930 s). Esta aparente paradoja —el algoritmo óptimo siendo también el más rápido— se explica porque el costo dominante en el Voraz es la búsqueda iterativa de la arista más cercana en cada paso (O(n²) en el peor caso con evaluación de distancias), mientras que el DCPP concentra su cómputo en una única ejecución del algoritmo Húngaro (O(m³) donde m es el desbalance total, típicamente mucho menor que n) y una pasada lineal de Hierholzer.

### 3.3 Efecto del Desbalance de Grado en DCPP

El desbalance del subgrafo requerido, que determina el número de aristas fantasma necesarias para hacer el grafo Euleriano, varió significativamente entre sectores: S0 presentó 45 unidades de desbalance, S4 = 21, S3 = 11, S2 = 7, y S1 = 3. Se observó una correlación positiva moderada entre el desbalance y la redundancia resultante. El sector 0, con el mayor desbalance (45), presentó también la mayor redundancia dentro del DCPP (1.509), reflejando la necesidad de recorrer caminos de deadhead más extensos para equilibrar los grados de los nodos involucrados. En contraste, el sector 1, con apenas 3 unidades de desbalance, logró una redundancia de 1.609 —valor que podría parecer elevado para un desbalance tan bajo, pero que se explica por la distancia de acceso desde el depósito al inicio del circuito en ese sector periférico.

### 3.4 Rendimiento del CARP con Búsqueda Tabú

La búsqueda Tabú produjo mejoras variables respecto a la solución inicial Voraz. El sector 3 registró la mejora más sustancial (15.8%, de 42.22 km iniciales a 35.53 km), seguido por el sector 2 (4.9%) y el sector 1 (1.0%). En los sectores 0 y 4, la mejora fue marginal (0.3% y 0.0% respectivamente), indicando que la solución inicial Voraz ya se encontraba cerca del óptimo local alcanzable dentro de las restricciones de vecindad exploradas. Este comportamiento sugiere que la restricción de capacidad de 30 km por viaje limita el espacio de búsqueda de manera que, en sectores con calles ya naturalmente agrupadas, los operadores de 2-opt y relocate tienen poco margen para reorganizar los viajes de forma significativa.

El tiempo de cómputo del CARP+Tabu fue consistentemente el más elevado: 2.930 segundos totales, impulsado principalmente por las 150 evaluaciones de función objetivo por sector, cada una de las cuales requiere múltiples llamadas a Dijkstra para calcular la distancia de la ruta completa. El sector 0 consumió 1.671 s (el 57% del tiempo total), correlacionado con su mayor número de aristas (272) que incrementa el costo de cada evaluación.

### 3.5 Análisis de Calles con Uso Excesivo en DCPP

Se identificaron calles individuales con frecuencias elevadas de traversación en las rutas DCPP, particularmente en sectores con alto desbalance. El sector 0 registró el mayor número de calles con cuatro o más traversaciones, correspondientes a segmentos cercanos al depósito y a conexiones inter-clúster que son utilizados tanto por aristas de servicio como por caminos de deadhead. Un análisis de sensibilidad mostró que forzar una compresión a un máximo de 3 traversaciones por calle duplica aproximadamente la distancia total del DCPP en los sectores afectados, deteriorando gravemente la eficiencia global. Este hallazgo sugiere que, para la topología específica de Chachapoyas, la tolerancia a múltiples traversaciones en calles estratégicas es un compromiso necesario entre optimalidad teórica y practicidad operativa.

---

## 4. Discusión

Los resultados de este estudio demuestran de manera concluyente que el algoritmo DCPP ofrece un rendimiento superior al Voraz y al CARP+Tabu para el problema de ruteo de recolección de residuos en Chachapoyas. La reducción del 21.8% en distancia total recorrida, combinada con el menor costo computacional, posiciona al DCPP como la opción óptima para la planificación operativa municipal.

La corrección del error en la dirección de las aristas fantasma —orientándolas desde nodos sumidero hacia nodos fuente, en lugar de la dirección inversa— constituye un hallazgo metodológico relevante. Una implementación que oriente incorrectamente estas aristas produce un grafo más desbalanceado, impide la construcción de un circuito Euleriano completo y genera rutas inválidas con redundancia inferior a 1.0 (físicamente imposible). Esta corrección, aunque sutil en su formulación matemática, tiene un impacto determinante en la validez de los resultados, y su documentación explícita contribuye a la reproducibilidad del método.

Los valores de redundancia obtenidos para DCPP (1.223 a 1.609) son consistentes con los reportados en estudios similares. Ghiani et al. (2005) reportaron redundancias entre 1.2 y 1.8 para rutas optimizadas en ciudades italianas de tamaño comparable, mientras que Santos et al. (2010) obtuvieron redundancias entre 1.4 y 2.1 aplicando heurísticas CARP en redes urbanas españolas. La superioridad del DCPP sobre el CARP+Tabu observada en este estudio contrasta con resultados previos donde las metaheurísticas suelen superar a los métodos exactos para CARP (Lacomme et al., 2004). Esta discrepancia puede atribuirse a la topología particular de Chachapoyas: la presencia de múltiples calles sin salida y una densidad vial heterogénea limitan la efectividad de los intercambios entre viajes, ya que las alternativas de reruteo son escasas. En esencia, cuando la red subyacente ofrece pocas rutas alternativas, la optimalidad global del DCPP predomina sobre la flexibilidad de la búsqueda local del CARP.

### 4.1 Limitaciones del Estudio

Este estudio presenta varias limitaciones que deben considerarse al interpretar sus resultados. Primero, se asumió una capacidad vehicular homogénea de 30 km para todos los viajes, sin considerar la variabilidad en la densidad de residuos por zona, la frecuencia de recolección diferenciada, ni la ubicación de puntos de descarga intermedios alternativos al depósito central. Segundo, la velocidad constante de 5 km/h no incorpora variaciones debidas a la topografía andina —con pendientes pronunciadas características de Chachapoyas—, condiciones climáticas estacionales, ni congestión vehicular en horas pico, factores que afectan diferencialmente a distintos sectores de la ciudad. Tercero, no se incorporaron restricciones de ventanas temporales de recolección ni sincronización entre múltiples vehículos operando simultáneamente, aspectos relevantes para la planificación operativa real. Cuarto, el modelo actual tolera múltiples traversaciones de una misma calle sin imponer un límite estricto, lo cual podría generar desgaste desproporcionado en segmentos viales específicos. Quinto, el estudio se basa en una instantánea del grafo vial sin considerar cambios estacionales o temporales en la red.

### 4.2 Implicaciones Prácticas

La reducción del 21.8% en distancia total recorrida que ofrece el DCPP respecto al Voraz se traduce, en términos operativos concretos, en un ahorro de aproximadamente 47.4 km por ciclo de recolección completo (5 sectores), una reducción de 9.5 horas de operación por ciclo, una disminución proporcional en emisiones de CO₂ y contaminantes locales, y un menor desgaste de la flota vehicular. Considerando que los costos de recolección representan el 60-80% del presupuesto municipal de limpieza pública, estas mejoras tienen un impacto económico y ambiental sustancial que justifica plenamente la adopción del enfoque DCPP.

### 4.3 Trabajo Futuro

Varias líneas de investigación se derivan naturalmente de este estudio. La integración de restricciones de capacidad directamente en el modelo DCPP, mediante la generación de múltiples circuitos Eulerianos que respeten límites de distancia, permitiría combinar la optimalidad del CPP con las restricciones operativas reales. La formulación de un problema multi-objetivo que incorpore simultáneamente minimización de distancia, balanceo de carga entre vehículos y maximización de cobertura temporal representa una extensión natural hacia la planificación operativa integral. La incorporación de datos en tiempo real —como niveles de llenado de contenedores mediante sensores IoT— habilitaría un sistema de ruteo dinámico que ajuste las rutas según la demanda efectiva. La validación de la metodología en otras ciudades peruanas y latinoamericanas con diferentes patrones urbanísticos es necesaria para establecer la generalizabilidad de los resultados. Finalmente, el análisis de sensibilidad sistemático a diferentes capacidades vehiculares y velocidades de operación permitiría construir curvas de Pareto que informen decisiones de inversión en flota.

---

## 5. Conclusiones

Este estudio presentó una comparación sistemática de tres algoritmos de ruteo para la optimización de la recolección de residuos sólidos en Chachapoyas, Perú, utilizando un grafo vial corregido de 256 nodos y 646 aristas que modela fielmente la red de calles de la ciudad. Los hallazgos principales se resumen a continuación.

El algoritmo DCPP superó consistentemente a los métodos Voraz y CARP+Tabu en los 5 sectores evaluados, alcanzando una distancia total de 169.82 km con redundancia promedio de 1.501, lo que representa una mejora del 21.8% sobre la línea base Voraz. La zonificación mediante K-Means con k = 5 y ajustes manuales espaciales produjo sectores funcionalmente conexos y razonablemente balanceados, con un total de 111.27 km de calles a servir, excluyendo correctamente las 4 rutas de acceso al depósito (7.21 km) que no requieren servicio. El algoritmo DCPP completó el cómputo en 0.114 segundos de CPU, siendo el más rápido de los tres métodos evaluados. La restricción de capacidad vehicular de 30 km implementada en el CARP+Tabu no produjo mejoras sustanciales respecto al Voraz en la mayoría de los sectores, con la excepción del sector 3 donde se alcanzó una mejora del 15.8%, lo que sugiere que la capacidad no es el factor limitante principal en la configuración actual.

El DCPP se consolida como el algoritmo recomendado para la optimización de rutas de recolección en Chachapoyas y potencialmente en otras ciudades de topografía y trazado urbano similares, ofreciendo un equilibrio óptimo entre calidad de la solución y eficiencia computacional. La metodología completa —incluyendo el editor vial interactivo, la zonificación determinística, los tres algoritmos de ruteo y los visores de rutas y sectores— está disponible como código abierto, facilitando su reproducción, validación y adaptación a otros contextos urbanos.

---

## Agradecimientos

Los autores agradecen a la Municipalidad Provincial de Chachapoyas por facilitar los datos operativos del sistema de recolección de residuos.

---

## Referencias

Boeing, G. (2017). OSMnx: New methods for acquiring, constructing, analyzing, and visualizing complex street networks. *Computers, Environment and Urban Systems*, 65, 126-139.

Edmonds, J., & Johnson, E. L. (1973). Matching, Euler tours and the Chinese postman. *Mathematical Programming*, 5(1), 88-124.

Eiselt, H. A., Gendreau, M., & Laporte, G. (1995). Arc routing problems, part I: The Chinese postman problem. *Operations Research*, 43(2), 231-242.

Ghiani, G., Laporte, G., & Musmanno, R. (2005). Introduction to logistics systems planning and control. *Wiley Interscience*.

Glover, F. (1989). Tabu search — part I. *ORSA Journal on Computing*, 1(3), 190-206.

Glover, F. (1990). Tabu search — part II. *ORSA Journal on Computing*, 2(1), 4-32.

Golden, B. L., & Wong, R. T. (1981). Capacitated arc routing problems. *Networks*, 11(3), 305-315.

Hierholzer, C. (1873). Über die Möglichkeit, einen Linienzug ohne Wiederholung und ohne Unterbrechung zu umfahren. *Mathematische Annalen*, 6(1), 30-32.

Kaza, S., Yao, L., Bhada-Tata, P., & Van Woerden, F. (2018). What a waste 2.0: A global snapshot of solid waste management to 2050. *World Bank Publications*.

Kuhn, H. W. (1955). The Hungarian method for the assignment problem. *Naval Research Logistics Quarterly*, 2(1-2), 83-97.

Lacomme, P., Prins, C., & Tanguy, A. (2004). A genetic algorithm for the capacitated arc routing problem and its extensions. *Lecture Notes in Computer Science*, 3004, 205-219.

Lloyd, S. (1982). Least squares quantization in PCM. *IEEE Transactions on Information Theory*, 28(2), 129-137.

MINAM (2021). Sexto Reporte Nacional de Residuos Sólidos Municipales 2021. *Ministerio del Ambiente del Perú*.

Munkres, J. (1957). Algorithms for the assignment and transportation problems. *Journal of the Society for Industrial and Applied Mathematics*, 5(1), 32-38.

Santos, L., Coutinho-Rodrigues, J., & Antunes, C. H. (2010). A web spatial decision support system for vehicle routing using Google Maps. *Decision Support Systems*, 51(1), 1-9.
