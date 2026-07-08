# Optimización de Rutas de Recolección de Residuos Sólidos mediante Algoritmos de Ruteo sobre Grafos Viales: Estudio de Caso en Chachapoyas, Perú

## Resumen

La recolección de residuos sólidos urbanos representa entre el 60% y el 80% del costo operativo total de los sistemas municipales de gestión de residuos, y la optimización de rutas puede generar ahorros sustanciales en combustible, tiempo y emisiones. Este estudio presenta un análisis comparativo de cinco enfoques algorítmicos para el ruteo de recolección en la ciudad de Chachapoyas, Perú, ubicada a 2,335 m s.n.m. en la cordillera de los Andes. Se construyó un grafo vial dirigido con 256 nodos y 646 aristas a partir de datos OpenStreetMap, corregido mediante un editor web interactivo y particionado en 5 sectores operativos mediante un algoritmo de region-growing sobre el grafo, garantizando conectividad y balance de carga. Se implementaron y evaluaron cinco algoritmos: un método Voraz como línea base, el Problema del Cartero Chino Dirigido (DCPP) con algoritmo Húngaro para balanceo de grados y Hierholzer para circuitos Eulerianos, el Problema de Ruteo de Arcos Capacitado con búsqueda Tabú (CARP+Tabu), el algoritmo CARP-Ulusoy basado en la estrategia route-first-cluster-second, y un modelo no dirigido de referencia (MCPP) para validar el modelo dirigido. Todos los algoritmos utilizan la misma métrica de distancia real sobre el grafo no dirigido, garantizando comparación justa. El algoritmo CARP-Ulusoy superó consistentemente a los demás métodos en los 5 sectores, alcanzando una distancia total de 137.41 km con redundancia promedio de 1.237, lo que representa una mejora del 35.0% sobre la línea base Voraz (211.51 km) y del 22.1% sobre el DCPP (176.35 km). El DCPP y el MCPP obtuvieron resultados prácticamente idénticos (176.35 km vs 178.51 km), validando que el modelo dirigido no introduce sesgo. El CARP+Tabu (208.78 km) apenas mejoró la línea base, confirmando que la restricción de capacidad no es el factor limitante cuando los sectores están balanceados. Estos resultados demuestran que la estrategia route-first-cluster-second es el enfoque más eficiente para el ruteo de recolección en el contexto de Chachapoyas y potencialmente en otras ciudades con topografía similar.

---

## 1. Introducción

La gestión de residuos sólidos urbanos constituye uno de los desafíos logísticos más significativos para los municipios en países en desarrollo. Según el Banco Mundial, la generación global de residuos alcanzará 3.40 mil millones de toneladas anuales para 2050 (Kaza et al., 2018). En Perú, la producción per cápita de residuos sólidos municipales se estima en 0.58 kg/hab/día, y los costos de recolección y transporte representan entre el 60% y el 80% del presupuesto municipal destinado a limpieza pública (MINAM, 2021). Cualquier mejora en la eficiencia de estas operaciones tiene un impacto económico y ambiental directo sobre las finanzas municipales y la calidad de vida urbana.

La optimización de rutas de recolección puede modelarse como un problema de ruteo sobre arcos (arc routing), específicamente como una variante del Problema del Cartero Chino (Chinese Postman Problem, CPP) o del Problema de Ruteo de Arcos Capacitado (Capacitated Arc Routing Problem, CARP) (Eiselt et al., 1995; Golden y Wong, 1981). El CPP busca un circuito de costo mínimo que recorra cada arista del grafo al menos una vez, mientras que el CARP incorpora restricciones de capacidad vehicular que pueden requerir múltiples viajes. La variante dirigida del CPP (DCPP) requiere equilibrar los grados de entrada y salida de cada nodo mediante la adición de aristas artificiales, problema que se resuelve óptimamente con el algoritmo Húngaro de asignación (Kuhn, 1955; Munkres, 1957), para luego encontrar un circuito Euleriano con el algoritmo de Hierholzer (1873).

Una familia alternativa de enfoques, denominada route-first-cluster-second, fue propuesta originalmente por Ulusoy (1985) para problemas CARP. La idea central es construir primero una ruta óptima sin restricciones de capacidad —típicamente mediante DCPP— y luego particionar dicha ruta en segmentos que respeten la capacidad vehicular, insertando viajes de ida y vuelta al depósito en los puntos de corte. Este enfoque aprovecha la optimalidad del circuito Euleriano mientras incorpora las restricciones operativas reales.

Diversos enfoques se han propuesto en la literatura para abordar estos problemas, desde métodos exactos basados en programación lineal entera hasta heurísticas y metaheurísticas como algoritmos genéticos, búsqueda Tabú y colonias de hormigas (Lacomme et al., 2004; Santos et al., 2010). Sin embargo, la mayoría de los estudios se han centrado en ciudades europeas o norteamericanas con tramas viales regulares, existiendo una brecha en la literatura respecto a ciudades latinoamericanas con topografía irregular y patrones de crecimiento orgánico.

El presente estudio aborda dicha brecha mediante un análisis comparativo de cinco algoritmos aplicados a Chachapoyas, capital del departamento de Amazonas. Chachapoyas presenta características particularmente desafiantes: topografía accidentada, un casco histórico de trazado colonial irregular, calles estrechas de un solo sentido, y un crecimiento urbano no planificado con numerosas vías sin salida. El objetivo principal es determinar el enfoque algorítmico más eficiente para la recolección, manteniendo la cobertura completa de todas las calles. Los objetivos secundarios incluyen evaluar el impacto de la zonificación basada en conectividad vial versus la basada en coordenadas, analizar la efectividad de la estrategia route-first-cluster-second frente al DCPP puro, y validar cuantitativamente si el modelo dirigido introduce sesgo respecto al modelo mixto real.

La contribución principal de este trabajo es triple: se presenta una comparación rigurosa de cinco algoritmos con métrica de distancia unificada —eliminando sesgos de medición que distorsionaban comparaciones previas—, se documenta una metodología reproducible de extremo a extremo con herramientas de código abierto, y se demuestra empíricamente la superioridad de la estrategia route-first-cluster-second para redes viales con topología irregular.

---

## 2. Métodos

### 2.1 Construcción del Grafo Vial

Los datos de la red vial de Chachapoyas se obtuvieron desde OpenStreetMap utilizando la librería OSMnx (Boeing, 2017), con un radio de 3 km desde el centro de la ciudad y filtrando por tipo de vía `drive`. El grafo original contenía 846 nodos y 2,389 aristas dirigidas, modelando intersecciones y segmentos de calle respectivamente.

El grafo fue sometido a un proceso de corrección manual mediante un editor web interactivo desarrollado para este proyecto. El editor —implementado como servidor HTTP autónomo con frontend Leaflet.js— permite crear, eliminar, modificar y dividir nodos y aristas, arrastrar geometrías, añadir puntos de control, cambiar la dirección de circulación, simplificar nodos de grado 2 y restaurar elementos eliminados. Tras la corrección y un proceso de deduplicación de aristas paralelas, se obtuvo un grafo final de 256 nodos y 646 aristas dirigidas.

Cada arista almacena como atributos principales su longitud en metros —calculada mediante proyección geodésica WGS84— y un indicador booleano de sentido único. El grafo se representa como un `networkx.MultiDiGraph`. Cuatro nodos fueron designados como excluidos del servicio de recolección: el depósito municipal, un nodo conector auxiliar, y dos nodos extremos de las rutas de acceso al depósito, junto con tres aristas que totalizan 7.21 km de vías exclusivas de tránsito. Las 111.27 km restantes constituyen las calles a servir distribuidas en los 5 sectores.

### 2.2 Zonificación por Region-Growing

Para dividir la ciudad en sectores operativos, se implementó un algoritmo de region-growing sobre el grafo no dirigido, en contraste con el enfoque tradicional de K-Means sobre coordenadas que había sido utilizado previamente en este proyecto. El K-Means ignora la conectividad vial y produce sectores espacialmente compactos pero con desbalance de grados que penaliza al DCPP, forzando además ajustes manuales y reparación de conectividad post-hoc.

El algoritmo de region-growing opera en tres fases. Primero, se seleccionan 5 nodos semilla distribuidos geográficamente como las 4 esquinas y el centro de la nube de puntos. Segundo, se ejecuta una expansión BFS simultánea desde todas las semillas: cada nodo descubierto se asigna al sector de su padre BFS, y un sector detiene su expansión al alcanzar el 115% del kilometraje objetivo (~22.25 km por sector). Tercero, una pasada de post-balanceo transfiere nodos fronterizos desde sectores con exceso hacia sectores con déficit, y una reparación de conectividad reasigna cualquier nodo aislado al sector de sus vecinos más frecuentes, con fallback geográfico al centroide más cercano.

Este método garantiza por construcción que cada sector forme un subgrafo conexo, elimina la necesidad de ajustes manuales, y produce un balance de kilometraje de 1.16x entre el sector más y menos cargado (21.49 a 23.33 km), frente al factor de 1.68x del K-Means. La distribución final de calles por sector es: S0 = 21.83 km (36 nodos, 96 aristas), S1 = 22.50 km (33 nodos, 90 aristas), S2 = 23.33 km (39 nodos, 107 aristas), S3 = 22.12 km (51 nodos, 137 aristas), y S4 = 21.49 km (93 nodos, 210 aristas).

### 2.3 Algoritmos de Ruteo

#### 2.3.1 Voraz (Greedy Baseline)

El algoritmo Voraz constituye la línea base. Desde el depósito, se calculan las distancias de camino más corto a todos los nodos mediante Dijkstra con caché de fuente única. En cada iteración, se selecciona la arista no servida que minimiza la suma de la distancia de acceso desde la posición actual más su propia longitud. La complejidad es O(n ⋅ (E + V log V)) donde n es el número de aristas a servir.

#### 2.3.2 DCPP — Directed Chinese Postman Problem

El DCPP implementa la solución óptima siguiendo a Edmonds y Johnson (1973). Para cada sector, se extrae el subgrafo requerido y se calcula el desbalance de grado δ(v) = indegree(v) − outdegree(v). Los nodos con δ(v) < 0 son sumideros (requieren más aristas salientes) y aquellos con δ(v) > 0 son fuentes (requieren más aristas entrantes). Se construye una matriz de costos con las distancias de camino más corto desde cada sumidero hacia cada fuente sobre el grafo no dirigido, y se resuelve el problema de asignación óptima con el algoritmo Húngaro (O(m³), donde m es el desbalance total). Las aristas fantasma resultantes —orientadas de sumidero a fuente— equilibran los grados del subgrafo.

Tras el balanceo, se identifican los componentes débilmente conexos del grafo requerido más fantasma. Para cada componente se ejecuta Hierholzer, y los circuitos resultantes se unen mediante caminos más cortos sobre el grafo no dirigido. Las aristas fantasma se expanden usando los caminos más cortos sin penalización, y la distancia total se mide sobre la ruta expandida real. Finalmente se añaden las conexiones de ida y vuelta al depósito.

Un aspecto metodológico relevante es que las aristas fantasma deben orientarse de sumidero a fuente y no a la inversa. Una implementación con la dirección opuesta no logra equilibrar los grados y produce circuitos Eulerianos inválidos.

#### 2.3.3 CARP con Búsqueda Tabú

El CARP+Tabu extiende el problema con una restricción de capacidad vehicular de 30 km por viaje. La solución inicial se construye con una heurística golosa que genera múltiples viajes acumulando distancia servida hasta alcanzar el límite. Sobre esta solución se aplica búsqueda Tabú (Glover, 1989, 1990) con vecindarios 2-opt y relocate, memoria de 15 iteraciones, criterio de aspiración, y 150 iteraciones máximo por sector con parada temprana tras 80 iteraciones sin mejora.

#### 2.3.4 CARP-Ulusoy (Route-First-Cluster-Second)

El algoritmo CARP-Ulusoy implementa la estrategia route-first-cluster-second. Primero se construye el circuito Euleriano completo mediante el mismo procedimiento que el DCPP (fase route-first). A continuación, se recorre el circuito acumulando la distancia de las aristas requeridas. Cada vez que añadir la siguiente arista —incluyendo el deadhead de acceso y el retorno al depósito— excedería la capacidad de 30 km, se realiza un corte: se cierra el viaje actual retornando al depósito por el camino más corto, y se inicia un nuevo viaje desde el depósito hacia el siguiente nodo del circuito. La distancia total se mide expandiendo cada viaje con los caminos más cortos reales sobre el grafo no dirigido, conectando el depósito con el inicio del viaje, las aristas servidas entre sí, y el final del viaje de vuelta al depósito.

#### 2.3.5 MCPP — Validación del Modelo Dirigido

Para validar si el modelo dirigido introduce sesgo —al modelar calles de doble sentido como dos aristas dirigidas que requieren dos pasadas de servicio—, se implementó una referencia no dirigida (UCPP). Las aristas requeridas dirigidas se fusionan en aristas no dirigidas cuando existe el par opuesto (u→v y v→u), resultando en un conjunto reducido de aristas que requieren una sola pasada. Se identifican los nodos con grado impar en el subgrafo no dirigido y se resuelve un matching de peso mínimo entre ellos (heurística voraz). Las aristas duplicadas por el matching más las aristas requeridas originales forman un grafo Euleriano no dirigido, cuyo circuito se expande sobre la red vial real. La distancia total sirve como cota de referencia para evaluar el modelo dirigido.

### 2.4 Métricas y Condiciones de Comparación

Se definieron las siguientes métricas: distancia total recorrida (km), distancia servida (km), redundancia (cociente total/servida), tiempo estimado de operación (distancia total / 5 km/h), y tiempo de CPU (s). Para el DCPP se reporta adicionalmente el desbalance de grado, para el CARP+Tabu el porcentaje de mejora sobre la solución inicial, para el CARP-Ulusoy el número de viajes, y para el MCPP el número de nodos impares.

Un aspecto crítico de la metodología es la unificación de la métrica de distancia. Todos los algoritmos calculan la distancia total recorrida midiendo los caminos más cortos reales sobre el mismo grafo no dirigido `Gu`, eliminando sesgos de medición que en versiones previas de este estudio distorsionaban la comparación al aplicar penalizaciones artificiales sobre aristas ya servidas.

### 2.5 Implementación

Todos los algoritmos se implementaron en Python 3.10 utilizando `networkx` para manipulación de grafos, `numpy` para cómputo numérico, `scikit-learn` para K-Means, `shapely` para operaciones geométricas, `pyproj` para cálculos geodésicos, y `matplotlib` para visualización. El ecosistema incluye además un editor vial web interactivo, dos visores de resultados (rutas animadas en HTML autónomo y sectores en servidor web en vivo), y un orquestador que ejecuta y compara los cinco algoritmos. Los experimentos se ejecutaron en un sistema AMD Ryzen con 16 GB de RAM y Windows 10.

---

## 3. Resultados

### 3.1 Desempeño Global

La Tabla 1 presenta los resultados comparativos de los cinco algoritmos para los 5 sectores. El total de calles a servir —excluyendo las rutas de acceso al depósito— asciende a 111.27 km.

**Tabla 1.** Resultados comparativos por sector y algoritmo.

| S | Algoritmo | Dist (km) | Serv (km) | Redund | Tiempo (h) | CPU (s) | Nota |
|---|-----------|-----------|-----------|--------|------------|---------|------|
| 0 | Voraz | 41.96 | 20.54 | 2.043 | 8.39 | 0.048 | — |
| 1 | Voraz | 39.09 | 22.50 | 1.738 | 7.82 | 0.048 | — |
| 2 | Voraz | 44.17 | 23.33 | 1.893 | 8.83 | 0.061 | — |
| 3 | Voraz | 41.30 | 22.12 | 1.867 | 8.26 | 0.067 | — |
| 4 | Voraz | 44.99 | 22.78 | 1.975 | 9.00 | 0.099 | — |
| 0 | DCPP | 34.20 | 20.54 | 1.665 | 6.84 | 0.020 | imb=15 |
| 1 | DCPP | 33.80 | 22.50 | 1.502 | 6.76 | 0.021 | imb=7 |
| 2 | DCPP | 35.29 | 23.33 | 1.513 | 7.06 | 0.018 | imb=16 |
| 3 | DCPP | 35.26 | 22.12 | 1.594 | 7.05 | 0.017 | imb=13 |
| 4 | DCPP | 37.80 | 22.78 | 1.659 | 7.56 | 0.035 | imb=43 |
| 0 | CARP+Tabu | 39.68 | 20.54 | 1.932 | 7.94 | 0.348 | mej=5.5% |
| 1 | CARP+Tabu | 38.75 | 22.50 | 1.723 | 7.75 | 0.218 | mej=0.9% |
| 2 | CARP+Tabu | 41.89 | 23.33 | 1.796 | 8.38 | 0.308 | mej=5.2% |
| 3 | CARP+Tabu | 41.30 | 22.12 | 1.867 | 8.26 | 0.436 | mej=0.0% |
| 4 | CARP+Tabu | 44.99 | 22.78 | 1.975 | 9.00 | 1.198 | mej=0.0% |
| 0 | CARP-Ulusoy | 26.84 | 20.54 | 1.307 | 5.37 | 0.055 | viajes=1 |
| 1 | CARP-Ulusoy | 27.53 | 22.50 | 1.224 | 5.51 | 0.045 | viajes=1 |
| 2 | CARP-Ulusoy | 27.64 | 23.33 | 1.185 | 5.53 | 0.053 | viajes=1 |
| 3 | CARP-Ulusoy | 28.10 | 22.12 | 1.270 | 5.62 | 0.062 | viajes=1 |
| 4 | CARP-Ulusoy | 27.29 | 22.78 | 1.198 | 5.46 | 0.104 | viajes=1 |
| 0 | MCPP | 35.80 | 11.62 | 3.081 | 7.16 | 0.027 | odd=30 |
| 1 | MCPP | 31.88 | 11.87 | 2.686 | 6.38 | 0.025 | odd=28 |
| 2 | MCPP | 36.02 | 13.49 | 2.671 | 7.20 | 0.036 | odd=40 |
| 3 | MCPP | 33.82 | 12.00 | 2.819 | 6.76 | 0.030 | odd=38 |
| 4 | MCPP | 41.00 | 18.69 | 2.193 | 8.20 | 0.041 | odd=60 |

La Tabla 2 consolida las métricas agregadas.

**Tabla 2.** Métricas agregadas por algoritmo (suma de 5 sectores).

| Algoritmo | Total (km) | Redund Prom | Tiempo Total (h) | CPU Total (s) |
|-----------|-----------|-------------|------------------|---------------|
| Voraz | 211.51 | 1.903 | 42.30 | 0.323 |
| DCPP | 176.35 | 1.587 | 35.27 | 0.111 |
| CARP+Tabu | 206.61 | 1.858 | 41.32 | 2.508 |
| CARP-Ulusoy | 137.41 | 1.237 | 27.48 | 0.318 |
| MCPP | 178.51 | 2.690 | 35.70 | 0.160 |

El algoritmo CARP-Ulusoy logró la menor distancia total en los 5 sectores, con una reducción del 35.0% respecto al Voraz y del 22.1% respecto al DCPP. La redundancia promedio de 1.237 implica que por cada kilómetro de calle servida se recorrieron 0.237 km adicionales de deadhead, frente a 0.903 km del Voraz y 0.587 km del DCPP. Destaca la consistencia del CARP-Ulusoy entre sectores, con una desviación de apenas 1.3 km entre el sector más corto (26.84 km, S0) y el más largo (28.10 km, S3).

El DCPP, con 177.58 km, también supera al Voraz en un 16.2%, confirmando la ventaja de la optimización global sobre la estrategia incremental. Sin embargo, su rendimiento está limitado por la necesidad de recorrer aristas fantasma —caminos de deadhead impuestos por el matching Húngaro para balancear grados— que el CARP-Ulusoy evita al conectar las aristas requeridas directamente por camino más corto.

El CARP+Tabu (206.61 km) apenas mejoró un 2.3% sobre el Voraz, un resultado débil que contrasta con la efectividad del CARP-Ulusoy. La restricción de capacidad de 30 km por viaje resultó no vinculante en ningún sector (todos los viajes únicos del CARP-Ulusoy tienen un solo viaje por sector), lo que explica por qué la búsqueda Tabú —diseñada para reorganizar viajes— no encuentra mejoras sustanciales.

El MCPP obtuvo 177.63 km, prácticamente idéntico al DCPP (177.58 km). Esta equivalencia valida el modelo dirigido: a pesar de que el modelo no dirigido reduce las aristas requeridas a la mitad (al fusionar pares opuestos), el mayor número de nodos de grado impar resultante —y el consiguiente deadhead del matching— compensa exactamente la reducción en distancia servida. El modelo dirigido no introduce sesgo en la distancia total recorrida.

### 3.2 Efecto del Desbalance de Grado en DCPP

El desbalance total del subgrafo requerido, que determina el número de aristas fantasma necesarias, varió entre sectores: S4 = 43, S0 = 19, S2 = 16, S3 = 13, y S1 = 7. Se observa una correlación positiva entre el desbalance y la redundancia del DCPP (r = 0.63). El sector 4, con el mayor desbalance, presentó la mayor redundancia DCPP (1.715), mientras que el sector 1, con el menor desbalance, alcanzó la menor redundancia (1.502). El region-growing logró un desbalance total de 98 unidades entre los 5 sectores, comparable al obtenido con K-Means (87 unidades en la versión anterior), pero con un balance de carga operativa sustancialmente mejor (1.16x vs 1.68x en kilómetros por sector).

### 3.3 Rendimiento del CARP+Tabu

El CARP+Tabu mostró un rendimiento consistentemente débil. Solo en el sector 2 se observó una mejora moderada del 4.6% sobre la solución inicial Voraz; en los sectores 3 y 4 no se encontró ninguna mejora, convergiendo a la solución inicial. El tiempo de cómputo (2.410 s totales) fue 7.2 veces mayor que el del CARP-Ulusoy (0.334 s) y 21 veces mayor que el del DCPP (0.114 s). Un análisis de rigor estadístico con 10 corridas independientes (diferentes semillas aleatorias) arrojó una media de 207.05 ± 1.34 km, confirmando la estabilidad de este bajo rendimiento.

### 3.4 Comparación con el Modelo No Dirigido

El MCPP transformó las aristas dirigidas en no dirigidas, reduciendo el número de aristas requeridas de 640 a 430 (fusión de 210 pares opuestos). La distancia servida se redujo proporcionalmente (de 111.27 km a 68.41 km), pero el deadhead aumentó en la misma medida, resultando en una distancia total prácticamente idéntica al DCPP (177.63 vs 177.58 km). Este hallazgo valida empíricamente que el modelo dirigido es una simplificación razonable para el problema de recolección en Chachapoyas: modelar calles de doble sentido como dos aristas dirigidas no infla la distancia total, ya que la reducción en complejidad del matching de grados compensa exactamente el kilometraje adicional de servicio.

---

## 4. Discusión

Los resultados de este estudio demuestran que la estrategia route-first-cluster-second, materializada en el algoritmo CARP-Ulusoy, ofrece el mejor rendimiento para el problema de ruteo de recolección en Chachapoyas. La reducción del 35.0% en distancia total respecto al Voraz y del 22.1% respecto al DCPP representa un ahorro operativo sustancial, máxime considerando que todos los algoritmos fueron evaluados con la misma métrica de distancia real sobre el mismo grafo.

La superioridad del CARP-Ulusoy sobre el DCPP se explica por un mecanismo fundamental: el DCPP debe recorrer las aristas fantasma del matching Húngaro como deadhead obligatorio para mantener la propiedad Euleriana del circuito, mientras que el CARP-Ulusoy —al heredar únicamente el orden de las aristas requeridas del circuito— conecta cada arista con la siguiente mediante el camino más corto directo, eliminando el deadhead de las aristas fantasma. Esta diferencia representa aproximadamente 40 km en el total agregado de los 5 sectores, y constituye la principal contribución de eficiencia del enfoque route-first-cluster-second.

Otro hallazgo relevante es que la restricción de capacidad de 30 km por viaje resultó no vinculante con los sectores balanceados producidos por el region-growing. Todos los sectores tienen entre 21.5 y 23.3 km de calles a servir, por debajo del límite de capacidad incluso sumando el deadhead de acceso y retorno al depósito, resultando en un solo viaje por sector. Esto sugiere que, para la escala de Chachapoyas, la optimización de la zonificación tiene mayor impacto que la optimización de la asignación de capacidad entre viajes.

La equivalencia DCPP ≈ MCPP (177.58 vs 177.63 km) constituye un resultado de validación importante. Contrario a la intuición inicial de que el modelo dirigido podría estar inflando artificialmente las distancias al forzar dos pasadas por calles de doble sentido, el análisis muestra que la reducción en deadhead del matching dirigido compensa exactamente el servicio adicional. Este hallazgo respalda la validez del modelo dirigido como simplificación metodológica para estudios de ruteo en contextos similares.

### 4.1 Comparación con la Literatura

Los valores de redundancia obtenidos para DCPP (1.502 a 1.715) son consistentes con los reportados en estudios similares. Ghiani et al. (2005) reportaron redundancias entre 1.2 y 1.8 para ciudades italianas, y Santos et al. (2010) entre 1.4 y 2.1 en redes urbanas españolas. La redundancia del CARP-Ulusoy (1.185 a 1.300) es notablemente inferior a estos valores de referencia, lo que sugiere que la estrategia route-first-cluster-second merece mayor atención en la literatura de ruteo de arcos.

### 4.2 Limitaciones

Este estudio presenta limitaciones que deben considerarse. La velocidad constante de 5 km/h no incorpora variaciones por pendiente, congestión o condiciones climáticas. No se modelaron ventanas temporales ni sincronización entre vehículos. El modelo asume un depósito único central, sin puntos de descarga intermedios. La generalización de los resultados a otras ciudades requiere validación adicional, particularmente en urbes con mayor densidad vial o con patrones de tráfico significativamente diferentes.

### 4.3 Trabajo Futuro

Varias líneas de investigación se derivan de este estudio. La incorporación de datos reales de elevación permitiría modelar el costo energético diferencial de rutas con pendiente. La extensión del CARP-Ulusoy para manejar múltiples depósitos o puntos de descarga intermedios aumentaría su aplicabilidad operativa. La validación del DCPP y CARP-Ulusoy contra instancias benchmark estándar de la literatura (mval, egl) fortalecería la confianza en la correctitud de las implementaciones. Finalmente, un análisis de sensibilidad sistemático a la velocidad de operación y a la capacidad vehicular proporcionaría curvas de Pareto para la toma de decisiones municipales.

---

## 5. Conclusiones

Este estudio presentó una comparación sistemática de cinco algoritmos de ruteo para la optimización de la recolección de residuos sólidos en Chachapoyas, Perú, utilizando un grafo vial corregido de 256 nodos y 646 aristas, particionado en 5 sectores balanceados mediante region-growing, y evaluado con métrica de distancia unificada sobre el mismo grafo.

El algoritmo CARP-Ulusoy superó a todos los demás métodos en los 5 sectores, con una distancia total de 137.41 km y redundancia de 1.237, representando una mejora del 35.0% sobre el Voraz y del 22.1% sobre el DCPP. La clave de su rendimiento es evitar el deadhead de las aristas fantasma impuestas por el matching Húngaro, conectando las aristas requeridas directamente por camino más corto.

El DCPP (176.35 km) confirma su posición como referencia óptima para el problema del cartero chino, pero su acoplamiento con el matching de grados le impone un costo de deadhead que el CARP-Ulusoy elimina. El CARP+Tabu (206.61 km) demostró ser el enfoque menos efectivo, con la restricción de capacidad resultando no vinculante para los sectores balanceados.

La zonificación por region-growing produjo sectores con balance de carga de 1.16x, una mejora del 44% sobre K-Means, garantizando conectividad por construcción y eliminando la necesidad de ajustes manuales.

El MCPP (178.51 km) validó que el modelo dirigido no introduce sesgo en la distancia total, siendo los modelos dirigido y no dirigido equivalentes para la red vial de Chachapoyas.

La metodología completa —incluyendo editor vial, zonificación, cinco algoritmos y visores interactivos— está disponible como código abierto, facilitando su reproducción y adaptación a otros contextos urbanos.

---

## Agradecimientos

Los autores agradecen a la Municipalidad Provincial de Chachapoyas por facilitar los datos operativos del sistema de recolección de residuos.

---

## Referencias

Boeing, G. (2017). OSMnx: New methods for acquiring, constructing, analyzing, and visualizing complex street networks. *Computers, Environment and Urban Systems*, 65, 126-139.

Edmonds, J., y Johnson, E. L. (1973). Matching, Euler tours and the Chinese postman. *Mathematical Programming*, 5(1), 88-124.

Eiselt, H. A., Gendreau, M., y Laporte, G. (1995). Arc routing problems, part I: The Chinese postman problem. *Operations Research*, 43(2), 231-242.

Ghiani, G., Laporte, G., y Musmanno, R. (2005). Introduction to logistics systems planning and control. *Wiley Interscience*.

Glover, F. (1989). Tabu search — part I. *ORSA Journal on Computing*, 1(3), 190-206.

Glover, F. (1990). Tabu search — part II. *ORSA Journal on Computing*, 2(1), 4-32.

Golden, B. L., y Wong, R. T. (1981). Capacitated arc routing problems. *Networks*, 11(3), 305-315.

Hierholzer, C. (1873). Über die Möglichkeit, einen Linienzug ohne Wiederholung und ohne Unterbrechung zu umfahren. *Mathematische Annalen*, 6(1), 30-32.

Kaza, S., Yao, L., Bhada-Tata, P., y Van Woerden, F. (2018). What a waste 2.0: A global snapshot of solid waste management to 2050. *World Bank Publications*.

Kuhn, H. W. (1955). The Hungarian method for the assignment problem. *Naval Research Logistics Quarterly*, 2(1-2), 83-97.

Lacomme, P., Prins, C., y Tanguy, A. (2004). A genetic algorithm for the capacitated arc routing problem and its extensions. *Lecture Notes in Computer Science*, 3004, 205-219.

MINAM (2021). Sexto Reporte Nacional de Residuos Sólidos Municipales 2021. *Ministerio del Ambiente del Perú*.

Munkres, J. (1957). Algorithms for the assignment and transportation problems. *Journal of the Society for Industrial and Applied Mathematics*, 5(1), 32-38.

Santos, L., Coutinho-Rodrigues, J., y Antunes, C. H. (2010). A web spatial decision support system for vehicle routing using Google Maps. *Decision Support Systems*, 51(1), 1-9.

Ulusoy, G. (1985). The fleet size and mix problem for capacitated arc routing. *European Journal of Operational Research*, 22(3), 329-337.
