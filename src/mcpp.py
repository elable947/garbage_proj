"""
MCPP (Mixed Chinese Postman Problem) — validacion del modelo dirigido.

Implementa el problema del cartero chino NO DIRIGIDO (UCPP) como referencia
para cuantificar cuanto infla el modelo dirigido puro actual.

Enfoque: todas las aristas requeridas se tratan como no dirigidas,
permitiendo recorrerlas en cualquier sentido. Calles de doble sentido
requieren una sola pasada en vez de dos.

Uso: from mcpp import mcpp
"""
import time
import itertools
import networkx as nx
from collections import defaultdict, Counter

from _data import _load_data


def _minimum_weight_matching(G, odd_nodes):
    """Find minimum weight perfect matching of odd-degree nodes.
    Uses greedy heuristic (O(n^2)) since exact matching is NP-hard for general graphs.
    For small sets (<20 nodes), this is adequate.
    """
    if len(odd_nodes) < 2:
        return []

    # Compute all-pairs shortest paths among odd nodes
    pairs = []
    odd_list = list(odd_nodes)
    for i in range(len(odd_list)):
        dists, paths = nx.single_source_dijkstra(G, odd_list[i], weight="length")
        for j in range(i + 1, len(odd_list)):
            if odd_list[j] in dists:
                pairs.append((dists[odd_list[j]], odd_list[i], odd_list[j], paths[odd_list[j]]))

    # Greedy matching: sort by distance, pick shortest non-conflicting pairs
    pairs.sort()
    matched = set()
    matching = []

    for dist, u, v, path in pairs:
        if u not in matched and v not in matched:
            matched.add(u)
            matched.add(v)
            matching.append((u, v, dist, path))

    return matching


def mcpp(sector_id: int):
    """Undirected Chinese Postman Problem.
    Treats all required edges as undirected (traversable in either direction).
    """
    t0 = time.perf_counter()

    G, Gu, depot, all_sector_edges = _load_data()
    required = list(all_sector_edges.get(sector_id, []))
    if not required:
        return {
            "sector": sector_id, "error": "sin aristas",
            "route_nodes": [], "total_distance_m": 0.0,
            "total_serviced_m": 0.0, "redundancy": 0.0,
            "estimated_time_h": 0.0, "computation_time_s": 0.0,
        }

    # Build undirected required graph: deduplicate opposite-direction pairs
    undirected_edges = {}  # (min(u,v), max(u,v)) -> min_length
    for u, v, k in required:
        key = (min(u, v), max(u, v))
        length = float(G.edges[u, v, k].get("length", 0))
        if key not in undirected_edges or length < undirected_edges[key]:
            undirected_edges[key] = length

    total_serviced = sum(undirected_edges.values())
    print(f"  MCPP S{sector_id}: {len(required)} aristas dirigidas -> {len(undirected_edges)} aristas no dirigidas, "
          f"serv={total_serviced/1000:.2f} km")

    # Build undirected required subgraph
    req_G = nx.Graph()
    for (a, b), length in undirected_edges.items():
        req_G.add_edge(a, b, length=length)

    # Find nodes with odd degree in required subgraph
    odd_nodes = [n for n in req_G.nodes if req_G.degree(n) % 2 == 1]
    print(f"  Nodos impares: {len(odd_nodes)}")

    # Match odd-degree nodes (make graph Eulerian)
    matching = _minimum_weight_matching(Gu, set(odd_nodes))
    extra_distance = sum(d for _, _, d, _ in matching)
    print(f"  Matching: {len(matching)} pares, {extra_distance/1000:.2f} km extra")

    # Build expanded graph: required edges + matched paths
    expanded_G = req_G.copy()
    for u, v, d, path in matching:
        for i in range(len(path) - 1):
            a, b = path[i], path[i + 1]
            if not expanded_G.has_edge(a, b):
                expanded_G.add_edge(a, b, length=0)
            # Double the edge (add traversal)

    # Find Eulerian circuit using Fleury-like approach (networkx)
    try:
        circuit_edges = list(nx.eulerian_circuit(expanded_G))
        circuit_nodes = [circuit_edges[0][0]] + [v for _, v in circuit_edges]
    except nx.NetworkXError:
        # Fallback: use DFS
        circuit_nodes = [list(req_G.nodes)[0]]
        visited = set()
        stack = [circuit_nodes[0]]
        while stack:
            u = stack[-1]
            neighbors = [v for v in expanded_G.neighbors(u) if (u, v) not in visited and (v, u) not in visited]
            if neighbors:
                v = neighbors[0]
                visited.add((u, v))
                stack.append(v)
            else:
                circuit_nodes.append(stack.pop())
        circuit_nodes = circuit_nodes

    # Expand circuit: traverse edges using Gu (real road network)
    expanded_route = [circuit_nodes[0]]
    total_circuit_dist = 0.0

    for i in range(len(circuit_nodes) - 1):
        a = circuit_nodes[i]
        b = circuit_nodes[i + 1]
        try:
            sp = nx.shortest_path(Gu, a, b, weight="length")
            expanded_route.extend(sp[1:])
            total_circuit_dist += nx.shortest_path_length(Gu, a, b, weight="length")
        except nx.NetworkXNoPath:
            expanded_route.append(b)
            total_circuit_dist += 0

    # Connect to/from depot
    circuit_start = circuit_nodes[0]
    circuit_end = expanded_route[-1]

    path_to = nx.shortest_path(Gu, depot, circuit_start, weight="length")
    path_to_dist = nx.shortest_path_length(Gu, depot, circuit_start, weight="length")

    path_from = nx.shortest_path(Gu, circuit_end, depot, weight="length")
    path_from_dist = nx.shortest_path_length(Gu, circuit_end, depot, weight="length")

    full_route = path_to + expanded_route[1:] + path_from[1:]
    total_dist = path_to_dist + total_circuit_dist + path_from_dist

    t1 = time.perf_counter()
    redundancy = total_dist / total_serviced if total_serviced > 0 else 0

    return {
        "sector": sector_id,
        "route_nodes": full_route,
        "total_distance_m": total_dist,
        "total_serviced_m": total_serviced,
        "redundancy": redundancy,
        "estimated_time_h": total_dist / 1000 / 5,
        "computation_time_s": t1 - t0,
        "odd_nodes": len(odd_nodes),
        "undirected_edges": len(undirected_edges),
    }


if __name__ == "__main__":
    for s in range(5):
        r = mcpp(s)
        print(f"S{s}: dist={r['total_distance_m']/1000:.2f}km "
              f"serv={r['total_serviced_m']/1000:.2f}km "
              f"red={r['redundancy']:.3f} "
              f"odd={r['odd_nodes']} "
              f"cpu={r['computation_time_s']:.3f}s")
