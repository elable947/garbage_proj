"""
Voraz (Greedy) - Algoritmo baseline de ruteo.
En cada paso selecciona la arista no servida mas cercana.
Optimizado con single_source_dijkstra para evitar O(N^2) shortest_path por iteracion.
"""
import time
import networkx as nx

from _data import _load_data


def voraz(sector_id: int):
    t0 = time.perf_counter()

    G, Gu, depot, all_sector_edges = _load_data()
    required = list(all_sector_edges.get(sector_id, []))
    if not required:
        return {"sector": sector_id, "error": "sin aristas", "route_nodes": [], "total_distance_m": 0.0, "total_serviced_m": 0.0, "redundancy": 0.0, "estimated_time_h": 0.0, "computation_time_s": 0.0}

    # Precompute distances from depot to all nodes
    depot_dists, depot_paths = nx.single_source_dijkstra(Gu, depot, weight="length")

    # Find best start node among required edge source nodes
    best_start = min(required, key=lambda e: depot_dists.get(e[0], float("inf")))[0]
    start_path = nx.shortest_path(Gu, depot, best_start, weight="length")
    start_dist = depot_dists[best_start]

    unserviced = set(required)
    current = best_start
    total_dist = start_dist
    route = list(start_path)

    while unserviced:
        # Single source from current to ALL nodes
        dists, paths = nx.single_source_dijkstra(Gu, current, weight="length")

        best = None
        best_cost = float("inf")
        best_path = None

        for u, v, k in unserviced:
            travel = dists.get(u)
            if travel is None:
                continue
            edgelen = G.edges[u, v, k]["length"]
            cost = travel + edgelen
            if cost < best_cost:
                best_cost = cost
                best = (u, v, k)
                best_path = paths[u]

        if best is None:
            break

        u, v, k = best
        for node in best_path[1:]:
            route.append(node)
        route.append(v)
        total_dist += best_cost
        current = v
        unserviced.remove(best)

    # Return to depot
    back_dists, back_paths = nx.single_source_dijkstra(Gu, current, weight="length")
    if depot in back_dists:
        back_path = back_paths[depot]
        for node in back_path[1:]:
            route.append(node)
        total_dist += back_dists[depot]

    t1 = time.perf_counter()

    total_serviced = sum(G.edges[u, v, k]["length"] for u, v, k in required)
    redundancy = total_dist / total_serviced if total_serviced > 0 else 0

    return {
        "sector": sector_id,
        "route_nodes": route,
        "total_distance_m": total_dist,
        "total_serviced_m": total_serviced,
        "redundancy": redundancy,
        "estimated_time_h": total_dist / 1000 / 5,
        "computation_time_s": t1 - t0,
    }


if __name__ == "__main__":
    for s in range(5):
        r = voraz(s)
        print(f"S{s}: dist={r['total_distance_m']/1000:.2f}km served={r['total_serviced_m']/1000:.2f}km "
              f"red={r['redundancy']:.3f} time={r['estimated_time_h']:.2f}h "
              f"cpu={r['computation_time_s']:.3f}s")
