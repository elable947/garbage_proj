# ¿Cómo funciona cada algoritmo? — Explicación paso a paso

> Guía para entender la lógica interna de los 5 algoritmos sin necesidad de leer el código.

---

## 1. Voraz (Greedy) — La línea base

**Idea:** "Siempre ve a la calle más cercana que aún no has limpiado."

Es la estrategia más simple posible: el camión empieza en el depósito, mira todas las calles que le faltan por servir, elige la que está más cerca (considerando tanto el camino para llegar como la longitud de la calle), va hasta allí, la limpia, y repite.

```
Paso 1: [Depósito] → ¿cuál es la arista no servida más cercana? → Voy a ella
Paso 2: Ya estoy en el nodo X → ¿cuál es la siguiente arista más cercana? → Voy a ella
Paso 3: ...
Paso N: Ya serví todas → Regreso al depósito por el camino más corto
```

**Ejemplo concreto:** Imagina que estás en el depósito y tienes 3 calles pendientes: calle A a 2 km, calle B a 5 km, calle C a 3 km. El voraz elige A. Luego desde el final de A, vuelve a evaluar: ¿B está a 4 km? ¿C a 1 km? Elige C. Así sucesivamente.

**Ventaja:** Muy rápido (~0.05 segundos por sector).  
**Desventaja:** Decisiones locales sin visión global. Como elegir siempre el carril más rápido en el tráfico sin saber que más adelante se cierra.

---

## 2. DCPP — Directed Chinese Postman Problem (Óptimo)

**Idea:** "Encuentra el circuito perfecto que recorre cada calle exactamente una vez."

Este es el algoritmo matemáticamente óptimo para el problema del cartero. Funciona en 4 fases:

### Fase 1: Identificar el desbalance
Para cada cruce (nodo), cuenta cuántas calles ENTRAN y cuántas SALEN de ese cruce dentro del sector.

```
Nodo X: entran 3 calles, salen 1 calle → desbalance = 3 - 1 = +2
Nodo Y: entran 1 calle, salen 3 calles → desbalance = 1 - 3 = -2
```

- Si entran más que salen: el nodo es **sumidero** (necesita más salidas)
- Si salen más que entran: el nodo es **fuente** (necesita más entradas)
- Si entran = salen: el nodo está **balanceado** ✓

Para que exista un circuito que recorra cada calle exactamente una vez, TODOS los nodos deben estar balanceados. Si no lo están, hay que añadir "calles fantasma".

### Fase 2: Emparejar fuentes con sumideros (Algoritmo Húngaro)
Imagina que tienes 5 fuentes (necesitan entradas) y 5 sumideros (necesitan salidas). El algoritmo Húngaro encuentra la forma de emparejarlos para que el costo total de los caminos entre ellos sea mínimo.

```
Sumidero A → Fuente X:  3 km  ← mejor emparejamiento
Sumidero A → Fuente Y:  8 km
Sumidero B → Fuente X:  6 km
Sumidero B → Fuente Y:  2 km  ← mejor emparejamiento
...
```

**Analogía:** 5 taxis (fuentes) necesitan pasajeros y 5 personas (sumideros) necesitan taxi. El Húngaro encuentra qué taxi debe recoger a qué persona para minimizar la distancia total recorrida.

Las "calles fantasma" que se añaden van **de sumidero a fuente** (sentido correcto: el sumidero necesita más salidas, la fuente necesita más entradas). Esto es crucial — si se orientan al revés, el circuito no funciona.

### Fase 3: Construir el circuito (Algoritmo de Hierholzer)
Con todas las calles reales + las calles fantasma, el grafo ya está balanceado. Hierholzer encuentra un circuito que recorre cada calle exactamente una vez.

```
El circuito sería algo como:
Depósito → Calle 1 → Calle 2 → [fantasma A→B] → Calle 3 → Calle 4 → [fantasma C→D] → ...
```

Las calles fantasma NO son calles reales — son atajos que el algoritmo usa para saltar de una parte del circuito a otra. En la ruta real, se recorren como caminos más cortos entre nodos.

### Fase 4: Conectar con el depósito
El circuito empieza en un nodo del sector. Hay que añadir la ida desde el depósito hasta ese nodo, y la vuelta desde el último nodo del circuito hasta el depósito.

```
Depósito → [camino más corto] → Inicio del circuito → ...circuito... → Fin → [camino más corto] → Depósito
```

**Resultado:** Ruta óptima (~176 km totales para Chachapoyas), redundancia 1.59. Pero tiene que recorrer TODAS las aristas fantasma, lo que añade deadhead (~40 km).

---

## 3. CARP + Tabu Search

**Idea:** "Construye una ruta golosa y luego mejórala intercambiando calles entre viajes."

### Fase 1: Construcción inicial (Voraz con capacidad)
Igual que el voraz, pero con un límite: cuando el camión ya recorrió 30 km (capacidad del tanque/carga), DEBE volver al depósito y empezar un nuevo viaje.

```
Viaje 1: Depósito → Calle A → Calle B → ... → [30 km alcanzados] → Regreso al depósito
Viaje 2: Depósito → Calle X → Calle Y → ... → Regreso al depósito
```

### Fase 2: Búsqueda Tabú
Toma la solución inicial y prueba a INTERCAMBIAR calles entre viajes para ver si la distancia total baja.

**2-opt:** Toma un segmento de la ruta y lo invierte.
```
Original: ... → A → B → C → D → ...
2-opt:    ... → A → D → C → B → ...
```

**Relocate:** Saca una calle de su posición actual y la pone en otro viaje.
```
Antes:  Viaje 1 = [A, B, C]    Viaje 2 = [X, Y]
Después: Viaje 1 = [A, C]      Viaje 2 = [X, B, Y]  ← B se movió de viaje
```

### Memoria Tabú
Si un movimiento ya se probó recientemente, se prohíbe temporalmente (evita ciclos). La memoria guarda los últimos 15 movimientos.

### Criterio de parada
Si pasan 80 intentos sin mejorar, se detiene. Máximo 150 intentos por sector.

**Resultado:** Mejora muy modesta (~206 km totales, solo 2.3% mejor que Voraz). La capacidad de 30 km casi nunca se alcanza porque cada sector tiene ~22 km.

---

## 4. CARP-Ulusoy (Route-First-Cluster-Second) ★ EL MEJOR

**Idea:** "Toma el circuito perfecto del DCPP, pero recórrelo de forma más inteligente."

### Fase 1: Route-First — Obtener el orden óptimo
Ejecuta el DCPP exactamente igual que antes. El resultado es un circuito Euleriano que visita todas las calles en un orden óptimo.

### Fase 2: Cluster-Second — Cortar en viajes
Recorre el circuito secuencialmente, acumulando distancia. Cuando añadir la siguiente calle + volver al depósito excedería 30 km, CORTA el circuito:

```
Circuito DCPP: A → B → C → D → E → F → ...

Recorriendo:
"A → B (2km), llevo 2km. Siguiente: C (3km más = 5km). Siguiente: D (20km más = 25km). 
¿E? E añadiría 8km más + 5km de vuelta al depósito = 38km > 30km → ¡CORTAR aquí!"

Viaje 1: Depósito → A → B → C → D → (retorno por camino más corto) → Depósito (27km)
Viaje 2: Depósito → (camino más corto a E) → E → F → ... → Depósito
```

### La diferencia CLAVE con DCPP
El DCPP recorre TODAS las aristas fantasma (saltos entre componentes del circuito). Ulusoy toma SOLO las calles reales del circuito y las conecta entre sí por el camino más corto directo.

```
DCPP:     Calle 1 → [fantasma A→B: 3km de rodeo] → Calle 2 → [fantasma C→D: 5km] → Calle 3
Ulusoy:   Calle 1 → [camino más corto directo: 1km] → Calle 2 → [camino más corto: 2km] → Calle 3
```

**Resultado en Chachapoyas:** 137.41 km totales (vs 176.35 del DCPP). Los ~39 km de diferencia son las aristas fantasma que Ulusoy evita.

---

## 5. MCPP — Validación del modelo

**Idea:** "¿Qué pasaría si las calles de doble sentido solo necesitaran UNA pasada en vez de dos?"

En el modelo actual (dirigido), una calle de doble sentido se modela como dos aristas:
```
Calle X: u → v (ida)
Calle X: v → u (vuelta)
```
Ambas deben ser servidas → el camión pasa DOS veces.

En el MCPP (no dirigido), esa misma calle es una sola arista que se puede recorrer en cualquier dirección:
```
Calle X: u — v (no dirigida, una sola pasada)
```

### Implementación
1. **Fusionar pares opuestos:** Si existen u→v y v→u, se convierten en una arista no dirigida (u,v).
2. **Nodos impares:** En un grafo no dirigido, un circuito Euleriano existe si TODOS los nodos tienen grado PAR. Los nodos con grado impar deben emparejarse.
3. **Matching de impares:** Se buscan los caminos más cortos entre nodos impares y se duplican (se añade una segunda copia de esas aristas).
4. **Circuito Euleriano:** Sobre el grafo con aristas duplicadas, se encuentra el circuito.

### Resultado
MCPP: 178.51 km vs DCPP: 176.35 km. Son prácticamente IGUALES.

**Conclusión:** El modelo dirigido NO infla las distancias. Aunque el MCPP reduce las aristas a la mitad (menos servicio), genera MUCHOS más nodos impares que requieren matching, y el deadhead extra compensa exactamente la reducción.

---

## Comparación visual

```
ALGORITMO        ESTRATEGIA                      RESULTADO    vs VORAZ
─────────────────────────────────────────────────────────────────────
Voraz            "La más cercana, siempre"       211.51 km    baseline
DCPP             "Circuito perfecto (Euler)"     176.35 km    -16.6%
CARP+Tabu        "Goloso + mejora local"         206.61 km     -2.3%
CARP-Ulusoy ★    "Circuito DCPP + atajos"        137.41 km    -35.0%
MCPP             "Calles doble sentido = 1 vez"  178.51 km    (validación)
```

---

## ¿Por qué CARP-Ulusoy es el mejor?

La intuición es simple: el DCPP encuentra el ORDEN perfecto para visitar las calles, pero desperdicia distancia recorriendo "calles fantasma" (rutas artificiales que el algoritmo crea para balancear el grafo). Ulusoy toma ese mismo orden perfecto pero conecta las calles directamente por el camino más corto, ahorrando ~40 km de deadhead.

**Analogía:** El DCPP es como Google Maps dándote la ruta perfecta pero obligándote a pasar por puntos de control innecesarios. Ulusoy sigue la misma ruta pero te deja tomar atajos entre los puntos que realmente importan.
