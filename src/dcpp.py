"""
Directed Chinese Postman Problem (DCPP).
Implementacion desde cero:
  - Algoritmo Hungaro (Kuhn-Munkres) para matching optimo
  - Hierholzer para circuito Euleriano
"""
import time
import networkx as nx
from collections import defaultdict, Counter


from _data import _load_data


# ── Algoritmo Hungaro (Kuhn-Munkres) O(n^3) ────────────────────────

def hungarian(cost):
    """
    cost: matriz n×n (list of lists), minimizacion
    Retorna: (total_cost, assignment) con assignment[i] = j
    Implementacion O(n^3) con arreglos 1-indexados internamente.
    """
    n = len(cost)
    if n == 0:
        return 0.0, []

    # Matriz 1-indexada: a[1..n][1..n]
    a = [[0.0] * (n + 1) for _ in range(n + 1)]
    for i in range(n):
        for j in range(n):
            a[i + 1][j + 1] = float(cost[i][j])

    u = [0.0] * (n + 1)  # potencial filas
    v = [0.0] * (n + 1)  # potencial columnas
    p = [0] * (n + 1)    # p[j] = fila asignada a columna j
    way = [0] * (n + 1)  # reconstruccion de camino

    for i in range(1, n + 1):
        p[0] = i
        j0 = 0
        minv = [float("inf")] * (n + 1)
        used = [False] * (n + 1)

        while True:
            used[j0] = True
            i0 = p[j0]
            delta = float("inf")
            j1 = 0

            for j in range(1, n + 1):
                if not used[j]:
                    cur = a[i0][j] - u[i0] - v[j]
                    if cur < minv[j]:
                        minv[j] = cur
                        way[j] = j0
                    if minv[j] < delta:
                        delta = minv[j]
                        j1 = j

            for j in range(n + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta

            j0 = j1
            if p[j0] == 0:
                break

        # Aumentar matching
        while True:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
            if j0 == 0:
                break

    assignment = [-1] * n
    for j in range(1, n + 1):
        if p[j] > 0:
            assignment[p[j] - 1] = j - 1

    total = sum(cost[i][assignment[i]] for i in range(n))
    return total, assignment


# ── Hierholzer (circuito Euleriano) ────────────────────────────────

def _hierholzer(adj, start):
    """
    adj: dict {node: [sucesores]}
    Retorna lista de nodos en orden de visita.
    """
    if not adj:
        return [start]

    out_edges = {n: list(adj[n]) for n in adj}
    stack = [start]
    circuit = []

    while stack:
        u = stack[-1]
        if out_edges.get(u):
            v = out_edges[u].pop()
            stack.append(v)
        else:
            circuit.append(stack.pop())

    return circuit[::-1]


# ── DCPP principal ─────────────────────────────────────────────────

def dcpp(sector_id: int):
    t0 = time.perf_counter()

    G, Gu, depot, all_sector_edges = _load_data()
    required = list(all_sector_edges.get(sector_id, []))
    if not required:
        return {"sector": sector_id, "error": "sin aristas", "route_nodes": [], "total_distance_m": 0.0, "total_serviced_m": 0.0, "redundancy": 0.0, "estimated_time_h": 0.0, "computation_time_s": 0.0}

    indeg = Counter()
    outdeg = Counter()
    for u, v, k in required:
        outdeg[u] += 1
        indeg[v] += 1

    sources = {}
    sinks = {}
    all_nodes = set(list(indeg.keys()) + list(outdeg.keys()))
    for n in all_nodes:
        imb = outdeg[n] - indeg[n]
        if imb > 0:
            sources[n] = imb
        elif imb < 0:
            sinks[n] = -imb

    total_imbalance = sum(sources.values())
    total_serviced = sum(G.edges[u, v, k]["length"] for u, v, k in required)

    phantom_edges = []
    if sources and sinks:
        src_list = []
        for n, qty in sources.items():
            src_list.extend([n] * qty)
        snk_list = []
        for n, qty in sinks.items():
            snk_list.extend([n] * qty)

        m = len(src_list)

        # Cache de distancias desde sinks para encontrar caminos minimos a sources
        dist_cache = {}
        for t in set(snk_list):
            dists, _ = nx.single_source_dijkstra(Gu, t, weight="length")
            dist_cache[t] = dists

        cost_matrix = [[0.0] * m for _ in range(m)]
        for i in range(m):
            dmap = dist_cache[snk_list[i]]
            for j in range(m):
                cost_matrix[i][j] = dmap.get(src_list[j], float("inf"))

        min_cost, assignment = hungarian(cost_matrix)

        for i, j in enumerate(assignment):
            phantom_edges.append((snk_list[i], src_list[j], cost_matrix[i][j]))

    adj = defaultdict(list)
    for u, v, k in required:
        adj[u].append(v)
    for src, dst, _ in phantom_edges:
        adj[src].append(dst)

    total_phantom = sum(d for _, _, d in phantom_edges)

    depot_dists, _ = nx.single_source_dijkstra(Gu, depot, weight="length")
    circuit_start = min(adj.keys(), key=lambda n: depot_dists.get(n, float("inf")))
    start_dist = depot_dists.get(circuit_start, 0.0)

    circuit = _hierholzer(adj, circuit_start)

    # Expandir pasos phantom del circuito en caminos reales (solo para ruta nodos)
    # Penalizar aristas ya servidas para evitar que el deadhead re-use la misma calle
    required_set = set()
    required_undirected = set()
    for u, v, k in required:
        required_set.add((u, v))
        required_undirected.add((min(u, v), max(u, v)))
    Gu_penalty = Gu.copy()
    for u_pen, v_pen in required_undirected:
        if Gu_penalty.has_edge(u_pen, v_pen):
            for key in Gu_penalty[u_pen][v_pen]:
                Gu_penalty[u_pen][v_pen][key]["length"] *= 100.0
    expanded = [circuit[0]]
    actual_circuit_dist = 0.0
    for i in range(len(circuit) - 1):
        a, b = circuit[i], circuit[i + 1]
        if (a, b) not in required_set:
            try:
                sp = nx.shortest_path(Gu_penalty, a, b, weight="length")
                expanded.extend(sp[1:])
            except nx.NetworkXNoPath:
                try:
                    sp = nx.shortest_path(Gu, a, b, weight="length")
                    expanded.extend(sp[1:])
                except nx.NetworkXNoPath:
                    sp = [a, b]
                    expanded.append(b)
            actual_circuit_dist += nx.shortest_path_length(Gu, sp[0], sp[-1], weight="length")
        else:
            expanded.append(b)
            k = next(iter(G[a][b]))
            actual_circuit_dist += G.edges[a, b, k]["length"]

    path_to = nx.shortest_path(Gu, depot, circuit_start, weight="length")
    path_to_dist = nx.shortest_path_length(Gu, depot, circuit_start, weight="length")

    circuit_end = expanded[-1]
    path_from = nx.shortest_path(Gu, circuit_end, depot, weight="length")
    path_from_dist = nx.shortest_path_length(Gu, circuit_end, depot, weight="length")

    full_route = path_to + expanded[1:]
    if circuit_end != depot:
        full_route.extend(path_from[1:])

    total_dist = path_to_dist + actual_circuit_dist + path_from_dist

    t1 = time.perf_counter()

    redundancy = total_dist / total_serviced if total_serviced > 0 else 0

    return {
        "sector": sector_id,
        "route_nodes": full_route,
        "total_distance_m": total_dist,
        "total_serviced_m": total_serviced,
        "total_deadhead_m": total_phantom + path_to_dist + path_from_dist,
        "redundancy": redundancy,
        "estimated_time_h": total_dist / 1000 / 5,
        "computation_time_s": t1 - t0,
        "imbalance_units": total_imbalance,
        "phantom_edges": len(phantom_edges),
    }


if __name__ == "__main__":
    for s in range(5):
        r = dcpp(s)
        print(f"S{s}: dist={r['total_distance_m']/1000:.2f}km served={r['total_serviced_m']/1000:.2f}km "
              f"red={r['redundancy']:.3f} time={r['estimated_time_h']:.2f}h "
              f"cpu={r['computation_time_s']:.3f}s "
              f"imb={r['imbalance_units']} ph={r['phantom_edges']}")
