# Mejoras propuestas — Optimización de rutas de recolección de residuos, Chachapoyas

## Contexto para el agente

Este es un proyecto de optimización de rutas de recolección de basura modelado como
problema de **ruteo de arcos (arc routing)** sobre un grafo vial de Chachapoyas, Perú.

- Grafo: `networkx.MultiDiGraph`, 489 nodos, 1088 aristas, extraído de OpenStreetMap
  con OSMnx. Peso de arista = distancia en metros. Las calles de doble sentido se
  modelan como dos aristas dirigidas opuestas.
- Zonificación: K-Means (k=5, uno por camión) sobre coordenadas (x,y) + ajustes
  manuales + reparación de nodos aislados por BFS. Resultado persistido en
  `sectores.json`.
- Algoritmos de ruteo ya implementados: `src/voraz.py` (línea base golosa),
  `src/dcpp.py` (Directed Chinese Postman: desbalance de grados + Húngaro +
  Hierholzer), `src/carp_tabu.py` (CARP con capacidad 30 km, construcción golosa +
  búsqueda Tabú).
- Stack: Python 3.10, networkx, numpy, scikit-learn, shapely.
- **No se dispone de datos de topografía/elevación** — todas las mejoras deben
  trabajar únicamente con distancia en metros como peso de arista. No proponer ni
  implementar ajustes de pendiente.
- Etapa actual: proyecto académico (curso de Diseño y Análisis de Algoritmos).
  Debe evolucionar hacia un proyecto de investigación formal. Priorizar mejoras
  que sean implementables en tiempo razonable y que fortalezcan tanto el rigor
  algorítmico como la validez experimental.

El objetivo de este documento es que el agente implemente las mejoras descritas
abajo, sector por sector, y actualice el pipeline y el reporte de resultados
(`Tabla 1`, `Tabla 2`, sección de resultados) en consecuencia.

---

## Prioridad ALTA (mayor impacto, complejidad moderada)

### 1. Zonificación consciente de la topología del grafo (no solo coordenadas)

**Problema actual:** K-Means sobre (x, y) ignora la conectividad vial. Esto obligó
a 3 ajustes manuales espaciales y a un algoritmo de reparación de nodos aislados
vía BFS. El desbalance de grados del DCPP por sector (S0=16, S1=12, S2=3, S3=3,
S4=48) correlaciona con la redundancia final (r=0.71 reportado), lo que sugiere
que buena parte de la ineficiencia del ruteo se origina en la partición, no en
el algoritmo de ruteo.

**Tareas:**
- Reemplazar o complementar K-Means con un método de **particionamiento sobre el
  grafo** (no sobre coordenadas crudas):
  - Opción A: `spectral clustering` sobre la matriz de adyacencia/Laplaciano del
    grafo (`sklearn.cluster.SpectralClustering` o implementación propia con
    `networkx`).
  - Opción B: **region-growing / sweep** desde el depósito: crecer cada sector
    incrementalmente por adyacencia vial hasta alcanzar un objetivo de km de
    calle, garantizando conectividad por construcción (elimina la necesidad de
    reparación posterior por BFS).
  - Opción C (si hay tiempo): binding con **METIS** (`pymetis` o `networkx-metis`)
    para partición balanceada minimizando aristas de corte, con pesos de nodo/
    arista proporcionales a longitud de calle.
- Función objetivo de la partición debe balancear explícitamente:
  1. Longitud total de calle por sector (ya se hace implícitamente).
  2. **Desbalance de grados esperado** por sector — es decir, preferir cortes que
     generen pocos nodos con grado de entrada ≠ grado de salida dentro del
     subgrafo requerido. Esto puede aproximarse contando, para cada frontera de
     corte candidata, cuántos nodos quedarían con grado impar/desbalanceado.
- Eliminar (o reducir a casos residuales) los ajustes manuales hardcodeados
  (`S3->S1`, `S4->S2`, `S4->S0`) reemplazándolos por el criterio anterior.
- Mantener el mecanismo de persistencia en JSON (`sectores.json`) para
  reproducibilidad, pero regenerado por el nuevo método.
- Añadir métrica nueva a reportar: **balance de tiempo de ruta entre sectores**
  (max/min de horas estimadas por sector), no solo km. Actualmente va de 5.48h
  (S2) a 9.64h (S4) en DCPP — un factor de ~1.76x que es relevante operativamente
  si los camiones trabajan en el mismo turno.

**Criterio de éxito:** reducir el desbalance total de grados en los sectores
problemáticos (especialmente S4, desbalance=48) sin degradar significativamente
el balance de km por sector, y verificar que la redundancia del DCPP baje en el
sector reparticionado.

---

### 2. Route-first-cluster-second: capacidad vehicular a partir del circuito DCPP

**Problema actual:** El CARP+Tabú actual usa una construcción golosa modificada +
búsqueda Tabú simple (vecindad: intercambio de una arista entre dos viajes,
memoria de 10 movimientos, 150 iteraciones). Los resultados muestran que en los
sectores 1 y 4 el Tabú no mejora nada sobre el Voraz, y en general el CARP+Tabú
(222.21 km total) es peor que el DCPP puro (184.54 km) e incluso similar al Voraz
(225.68 km), lo cual es un resultado débil para un método que debería ser al
menos competitivo.

**Tarea:** Implementar la heurística **"route-first, cluster-second"** (Ulusoy),
que aprovecha el circuito Euleriano ya óptimo del DCPP en vez de partir de una
construcción golosa débil:

1. Tomar el circuito Euleriano completo generado por `dcpp.py` para un sector.
2. Recorrer el circuito acumulando distancia servida.
3. Cada vez que la distancia acumulada alcance la capacidad (30 km), "cortar" el
   circuito en ese punto: insertar un viaje de regreso al depósito (camino más
   corto desde el nodo de corte) y un viaje de salida desde el depósito hacia el
   siguiente nodo no servido del circuito original.
4. Repetir hasta cubrir todo el circuito. El resultado es un conjunto de
   sub-rutas, cada una respetando la capacidad de 30 km.
5. (Opcional, si el tiempo lo permite) Aplicar una mejora local tipo 2-opt o
   Or-opt sobre los puntos de corte para minimizar el km total añadido por los
   viajes de ida/vuelta al depósito.

**Esto reemplaza o complementa `carp_tabu.py`** como constructor inicial —
comparar ambos enfoques (Tabú actual vs. route-first-cluster-second) en la
tabla de resultados.

**Criterio de éxito:** el nuevo método CARP debe ser competitivo con el DCPP sin
capacidad (idealmente distancia total entre el DCPP puro y el Voraz), y
consistentemente mejor que el CARP+Tabú actual en todos los sectores, no solo en
S0.

**Métrica nueva a reportar:** número de viajes (round trips al depósito) por
sector y por algoritmo — actualmente no se reporta y ayuda a diagnosticar si la
restricción de capacidad se está activando realmente.

---

### 3. Validar el modelo dirigido contra el problema mixto real (MCPP)

**Problema actual:** Modelar las calles de doble sentido como dos aristas
dirigidas opuestas obligatorias asume que cada calle de doble sentido requiere
**dos pasadas** de servicio. Si en la operación real basta con una sola pasada
por calle de doble sentido (el camión recolecta de ambos lados en un recorrido),
el modelo actual está **inflando artificialmente** tanto la distancia servida
como el desbalance de grados usado por el DCPP.

**Tarea:**
- Aclarar/parametrizar en el código si una calle de doble sentido requiere 1 o 2
  pasadas de servicio (esto debería ser un parámetro configurable por tipo de
  calle, no un supuesto implícito del modelo).
- Implementar una versión de referencia usando el **Mixed Chinese Postman
  Problem (MCPP)** con la heurística de **Frederickson** (relajación de flujo +
  matching para la parte no dirigida), donde las calles de doble sentido son
  aristas no dirigidas que requieren una sola pasada, y las de un solo sentido
  siguen siendo arcos dirigidos.
- Comparar los resultados (distancia total, redundancia) del DCPP actual
  (dirigido puro) contra el MCPP (mixto real) para cuantificar el costo de la
  simplificación actual.

**Criterio de éxito:** un experimento adicional en la sección de resultados que
muestre explícitamente cuánta distancia/redundancia se gana o se pierde al pasar
de la simplificación dirigida al modelo mixto real. Esto es valioso incluso si
el resultado es "la simplificación es razonable", porque lo convierte en un
resultado validado en vez de un supuesto no verificado.

---

## Prioridad MEDIA (fortalece el rigor experimental)

### 4. Rigor estadístico: múltiples corridas para algoritmos estocásticos

**Problema actual:** K-Means y la búsqueda Tabú son estocásticos (dependen de
inicialización/semilla aleatoria), pero el paper reporta una sola corrida por
sector. Con solo 5 sectores como "muestra", afirmar superioridad "consistente"
del DCPP es una conclusión débil estadísticamente.

**Tareas:**
- Ejecutar K-Means y CARP+Tabú (y el nuevo route-first-cluster-second si aplica
  aleatoriedad en los cortes/mejora local) con al menos 20-30 semillas distintas.
- Reportar media ± desviación estándar para distancia total, redundancia y CPU
  por sector y algoritmo.
- Aplicar una prueba estadística pareada (Wilcoxon signed-rank, dado el tamaño
  pequeño de muestra, o t-test pareado si se asume normalidad) comparando DCPP
  vs. Voraz y DCPP vs. CARP en las corridas repetidas, para respaldar
  estadísticamente la afirmación de superioridad.

**Criterio de éxito:** tablas de resultados actualizadas con intervalos de
confianza o desviación estándar, y un valor p reportado para las comparaciones
principales.

---

### 5. Validación contra benchmarks estándar de la literatura

**Problema actual:** El código se valida únicamente en el caso de estudio real
(Chachapoyas), sin verificar contra instancias de referencia conocidas. Esto
deja abierta la duda de si los resultados reflejan la calidad del algoritmo o
posibles errores de implementación.

**Tarea:**
- Ejecutar las implementaciones de DCPP/CARP sobre al menos un conjunto de
  instancias benchmark públicas y estándar en la literatura de arc routing
  (por ejemplo, instancias tipo `mval` o `egl` usadas comúnmente para CARP).
- Comparar los resultados obtenidos contra los valores óptimos o mejores
  conocidos reportados en la literatura para esas instancias.

**Criterio de éxito:** una tabla adicional (posiblemente en anexo) mostrando que
la implementación reproduce (o se acerca a) resultados conocidos en instancias
estándar, como evidencia de correctitud del código antes de aplicarlo al caso
real.

---

### 6. Análisis de sensibilidad al número de sectores (k)

**Problema actual:** k=5 se fija por la flota actual de la municipalidad, sin
explorar si ese es el número óptimo de sectores dado el grafo vial real.

**Tarea:**
- Ejecutar el pipeline completo (zonificación + DCPP) para k = 3, 4, 5, 6, 7.
- Reportar cómo cambian: distancia total agregada, redundancia promedio, y el
  balance de carga entre sectores (max/min horas de ruta) para cada k.

**Criterio de éxito:** una gráfica o tabla que permita argumentar, con datos, si
la flota de 5 camiones está bien dimensionada, sobredimensionada o
subdimensionada respecto a la red vial actual. Esto convierte el estudio en una
recomendación accionable para la municipalidad, no solo una comparación
algorítmica.

---

## Prioridad BAJA (mejoras de reporte y reproducibilidad, bajo esfuerzo)

### 7. Completar metadatos de reproducibilidad

- Reemplazar "procesador desconocido" por las especificaciones reales del
  hardware usado en los experimentos (CPU, arquitectura).
- Fijar y documentar todas las semillas aleatorias usadas por defecto en
  K-Means y Tabú, para que los resultados de la Tabla 1/2 actuales sean
  reproducibles exactamente.

### 8. Límite explícito de traversaciones por calle en el DCPP

**Problema actual:** El análisis de sensibilidad ya identificó que forzar un
máximo de 3 traversaciones por calle incrementa la distancia entre 85-100% en
los sectores afectados — pero esto se reporta como un experimento post-hoc, no
como una restricción incorporada al modelo.

**Tarea:** Formalizar el límite de traversaciones como parte del algoritmo de
expansión de aristas fantasma (paso 4 del DCPP), en vez de solo medirlo después.
Esto puede requerir modificar la matriz de costos del matching Húngaro para
penalizar progresivamente el reuso de una misma calle a medida que se acerca al
límite, en vez de una penalización fija (factor ×100) aplicada uniformemente.

### 9. Reporte de número de viajes y distancia de deadhead por segmento

Añadir a las métricas actuales (`Distancia total`, `Distancia servida`,
`Redundancia`, `Tiempo`, `CPU`) las siguientes, aplicables a los tres algoritmos:
- Número de viajes (idas y vueltas al depósito).
- Top-N calles con más traversaciones, ya identificado para DCPP en la sección
  3.5 — extenderlo también a Voraz y CARP+Tabú para comparación justa.

---

## Notas para el agente sobre alcance

- **No implementar nada relacionado con pendientes, elevación o topografía** —
  no hay datos disponibles para eso en este proyecto; cualquier mejora debe
  usar exclusivamente distancia en metros como peso de arista.
- Priorizar los ítems 1, 2 y 3 primero (mayor impacto en los resultados
  reportados); los ítems 4-6 fortalecen la validez experimental del estudio
  cuando se convierta en investigación formal; los ítems 7-9 son mejoras de
  bajo esfuerzo que pueden hacerse en paralelo.
- Cada mejora implementada debe actualizar la Tabla 1 (resultados por sector) y
  Tabla 2 (métricas agregadas) del reporte, manteniendo los algoritmos
  originales disponibles para comparación (no sobrescribir `voraz.py`,
  `dcpp.py`, `carp_tabu.py` — crear versiones nuevas o parametrizadas).
