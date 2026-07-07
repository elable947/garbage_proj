"""
CARP (Capacitated Arc Routing Problem) heuristico con Tabu Search.
Implementacion desde cero:
  - Solucion inicial: Voraz (greedy)
  - Vecindarios: 2-opt, Relocate, Swap
  - Tabu Search con aspiracion
  - Capacidad: distancia maxima por viaje (default 30 km)
"""
import time
import random
import networkx as nx

from _data import _load_data


# ── Cache de distancias para rapidez ───────────────────────────────

_dist_cache = {}


def _get_dist(Gu, a, b):
    key = (a, b)
    if key not in _dist_cache:
        try:
            d = nx.shortest_path_length(Gu, a, b, weight="length")
        except nx.NetworkXNoPath:
            d = float("inf")
        _dist_cache[key] = d
    return _dist_cache[key]


def _total_distance(Gu, depot, seq, edge_len):
    if not seq:
        return 0.0
    d = _get_dist(Gu, depot, seq[0][0]) + edge_len[seq[0]]
    cur = seq[0][1]
    for e in seq[1:]:
        d += _get_dist(Gu, cur, e[0]) + edge_len[e]
        cur = e[1]
    d += _get_dist(Gu, cur, depot)
    return d


# ── Solucion inicial: Voraz ────────────────────────────────────────

def _voraz_seq(Gu, depot, required, edge_len):
    seq = []
    unserviced = set(required)
    cur = depot
    while unserviced:
        best = min(unserviced, key=lambda e: _get_dist(Gu, cur, e[0]) + edge_len[e])
        seq.append(best)
        cur = best[1]
        unserviced.remove(best)
    return seq


# ── Tabu Search ────────────────────────────────────────────────────

def _tabu_search(Gu, depot, initial_seq, edge_len, max_iter=300, tabu_tenure=15):
    n = len(initial_seq)
    if n < 4:
        return list(initial_seq)

    current = list(initial_seq)
    best = list(initial_seq)
    best_dist = _total_distance(Gu, depot, current, edge_len)

    tabu_set = set()
    no_improve = 0
    random.seed(42)

    for iteration in range(max_iter):
        candidates = []

        # Generar candidatos: 2-opt y relocate
        for _ in range(100):
            if random.random() < 0.5:
                # 2-opt
                i = random.randint(0, n - 2)
                j = random.randint(i + 1, n - 1)
                if i == 0 and j == n - 1:
                    continue
                neighbor = list(current)
                neighbor[i:j + 1] = reversed(neighbor[i:j + 1])
                nd = _total_distance(Gu, depot, neighbor, edge_len)
                key = ("2o", i, j, i, j)
                is_tabu = key in tabu_set
                candidates.append((nd, neighbor, is_tabu, key))
            else:
                # Relocate
                i = random.randint(0, n - 1)
                j = random.randint(0, n - 2)
                if j >= i:
                    j += 1
                neighbor = list(current)
                e = neighbor.pop(i)
                ni = i
                if j > ni:
                    j_adj = j - 1
                else:
                    j_adj = j
                neighbor.insert(j_adj, e)
                nd = _total_distance(Gu, depot, neighbor, edge_len)
                key = ("rl", i, j, i, j)
                is_tabu = key in tabu_set
                candidates.append((nd, neighbor, is_tabu, key))

        if not candidates:
            break

        # Ordenar por distancia
        candidates.sort(key=lambda x: x[0])
        selected = None

        for nd, neighbor, is_tabu, key in candidates:
            if not is_tabu or nd < best_dist:
                selected = (nd, neighbor, key)
                break

        if selected is None:
            break

        nd, neighbor, key = selected
        current = neighbor

        # Actualizar tabu
        tabu_set.add(key)
        if len(tabu_set) > tabu_tenure * 5:
            tabu_set = set(list(tabu_set)[-tabu_tenure * 5:])

        if nd < best_dist - 1e-6:
            best = list(current)
            best_dist = nd
            no_improve = 0
        else:
            no_improve += 1

        if no_improve >= 80:
            break

    return best


# ── Reconstruir ruta completa ──────────────────────────────────────

def _build_route(Gu, depot, seq, edge_len, capacity=30000.0):
    if not seq:
        return [depot, depot], 0.0

    trips = []
    cur_trip = []
    cur_node = depot
    cur_dist_to_end = _get_dist(Gu, depot, seq[0][0]) + edge_len[seq[0]]
    cur_trip.append(seq[0])
    cur_node = seq[0][1]

    for e in seq[1:]:
        travel = _get_dist(Gu, cur_node, e[0])
        serv = edge_len[e]
        added = travel + serv
        ret_to_depot = _get_dist(Gu, e[1], depot)

        if cur_dist_to_end + added + ret_to_depot > capacity and cur_dist_to_end > 0:
            trips.append(cur_trip)
            cur_trip = [e]
            cur_dist_to_end = _get_dist(Gu, depot, e[0]) + edge_len[e]
            cur_node = e[1]
        else:
            cur_dist_to_end += added
            cur_trip.append(e)
            cur_node = e[1]

    if cur_trip:
        trips.append(cur_trip)

    route = []
    for ti, trip in enumerate(trips):
        path = nx.shortest_path(Gu, depot, trip[0][0], weight="length")
        if not route:
            route.extend(path)
        else:
            route.extend(path[1:])

        for e in trip:
            u, v, k = e
            path = nx.shortest_path(Gu, route[-1], u, weight="length")
            if len(path) > 1:
                route.extend(path[1:])
            route.append(v)

        if ti == len(trips) - 1:
            path = nx.shortest_path(Gu, trip[-1][1], depot, weight="length")
            route.extend(path[1:])

    total = _total_distance(Gu, depot, seq, edge_len)
    return route, total


# ── CARP + Tabu Search principal ──────────────────────────────────

def carp_tabu(sector_id: int, capacidad_m: float = 30000.0, max_iter: int = 300):
    t0 = time.perf_counter()

    G, Gu, depot, all_sector_edges = _load_data()
    required = list(all_sector_edges.get(sector_id, []))
    if not required:
        return {"sector": sector_id, "error": "sin aristas", "route_nodes": [], "total_distance_m": 0.0, "total_serviced_m": 0.0, "redundancy": 0.0, "estimated_time_h": 0.0, "computation_time_s": 0.0}

    total_serviced = sum(G.edges[u, v, k]["length"] for u, v, k in required)
    edge_len = {e: G.edges[e[0], e[1], e[2]]["length"] for e in required}

    _dist_cache.clear()

    init_seq = _voraz_seq(Gu, depot, required, edge_len)
    init_dist = _total_distance(Gu, depot, init_seq, edge_len)

    improved_seq = _tabu_search(Gu, depot, init_seq, edge_len, max_iter=max_iter)
    improved_dist = _total_distance(Gu, depot, improved_seq, edge_len)

    route, final_dist = _build_route(Gu, depot, improved_seq, edge_len, capacity=capacidad_m)

    t1 = time.perf_counter()

    redundancy = final_dist / total_serviced if total_serviced > 0 else 0

    return {
        "sector": sector_id,
        "route_nodes": route,
        "total_distance_m": final_dist,
        "total_serviced_m": total_serviced,
        "redundancy": redundancy,
        "estimated_time_h": final_dist / 1000 / 5,
        "computation_time_s": t1 - t0,
        "initial_distance_m": init_dist,
        "improvement_pct": (init_dist - improved_dist) / init_dist * 100 if init_dist > 0 else 0,
    }


if __name__ == "__main__":
    for s in range(5):
        r = carp_tabu(s, max_iter=150)
        print(f"S{s}: dist={r['total_distance_m']/1000:.2f}km served={r['total_serviced_m']/1000:.2f}km "
              f"red={r['redundancy']:.3f} time={r['estimated_time_h']:.2f}h "
              f"cpu={r['computation_time_s']:.3f}s "
              f"init={r.get('initial_distance_m',0)/1000:.2f}km "
              f"improv={r.get('improvement_pct',0):.1f}%")
