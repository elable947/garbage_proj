"""
CARP Ulusoy — Route-first-cluster-second.
Parte del circuito Euleriano optimo del DCPP y lo corta en viajes
de capacidad maxima (30 km), insertando retornos y salidas al deposito.

Uso: from carp_ulusoy import carp_ulusoy
"""
import time
import networkx as nx
from collections import defaultdict, Counter

from _data import _load_data
from dcpp import hungarian, _hierholzer


def _build_dcpp_circuit(G, Gu, required):
    """Build the DCPP Eulerian circuit for a set of required edges.
    Returns (circuit_nodes, required_set, phantom_edges, total_serviced)."""
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

    phantom_edges = []
    if sources and sinks:
        src_list = [n for n, q in sources.items() for _ in range(q)]
        snk_list = [n for n, q in sinks.items() for _ in range(q)]
        m = len(src_list)
        dist_cache = {}
        for t in set(snk_list):
            dists, _ = nx.single_source_dijkstra(Gu, t, weight="length")
            dist_cache[t] = dists
        cost_matrix = [[0.0] * m for _ in range(m)]
        for i in range(m):
            dmap = dist_cache[snk_list[i]]
            for j in range(m):
                cost_matrix[i][j] = dmap.get(src_list[j], float("inf"))
        _, assignment = hungarian(cost_matrix)
        for i, j in enumerate(assignment):
            phantom_edges.append((snk_list[i], src_list[j], cost_matrix[i][j]))

    adj = defaultdict(list)
    for u, v, k in required:
        adj[u].append(v)
    for src, dst, _ in phantom_edges:
        adj[src].append(dst)

    # Handle weakly connected components
    undir_test = nx.Graph()
    for u, successors in adj.items():
        for v in successors:
            undir_test.add_edge(u, v)
    components = list(nx.connected_components(undir_test))

    depot_dists, _ = nx.single_source_dijkstra(Gu,
        "af3202cd-3a9f-4a98-bdd0-28e64cac4795", weight="length")

    component_circuits = []
    for comp in components:
        sub_adj = {u: [v for v in adj[u] if v in comp] for u in comp if u in adj}
        if not sub_adj:
            continue
        start = min(sub_adj.keys(), key=lambda n: depot_dists.get(n, float("inf")))
        circuit = _hierholzer(sub_adj, start)
        component_circuits.append(circuit)

    circuit = []
    for comp_circuit in component_circuits:
        if not circuit:
            circuit = comp_circuit
        else:
            prev_end = circuit[-1]
            try:
                bridge = nx.shortest_path(Gu, prev_end, comp_circuit[0], weight="length")
                circuit.extend(bridge[1:] if bridge else [])
            except nx.NetworkXNoPath:
                circuit.append(comp_circuit[0])
            circuit.extend(comp_circuit[1:])

    total_serviced = sum(float(G.edges[u, v, k].get("length", 0)) for u, v, k in required)

    required_set = set()
    for u, v, k in required:
        required_set.add((u, v))

    return circuit, required_set, phantom_edges, total_serviced


def carp_ulusoy(sector_id: int, capacity_m: float = 30000.0):
    t0 = time.perf_counter()

    G, Gu, depot, all_sector_edges = _load_data()
    required = list(all_sector_edges.get(sector_id, []))
    if not required:
        return {
            "sector": sector_id, "error": "sin aristas",
            "route_nodes": [], "total_distance_m": 0.0,
            "total_serviced_m": 0.0, "redundancy": 0.0,
            "estimated_time_h": 0.0, "computation_time_s": 0.0,
            "num_trips": 0,
        }

    circuit, required_set, phantom_edges, total_serviced = \
        _build_dcpp_circuit(G, Gu, required)

    # Walk the circuit, cutting at capacity boundaries
    edge_length = {}
    for u, v, k in required:
        edge_length[(u, v)] = float(G.edges[u, v, k].get("length", 0))

    # Map circuit nodes to the edges they represent
    # Walk through the circuit and accumulate service distance
    trips = []
    current_trip = []
    current_dist = 0.0  # accumulated service distance in this trip
    current_node = depot

    # Start from depot to first circuit node
    first_node = circuit[0]

    for i in range(len(circuit) - 1):
        a = circuit[i]
        b = circuit[i + 1]

        is_required = (a, b) in required_set
        edge_dist = edge_length.get((a, b), 0.0) if is_required else 0.0

        if is_required:
            added = edge_dist

            # Compute deadhead from current position to 'a'
            try:
                access_dist = nx.shortest_path_length(Gu, current_node, a, weight="length")
            except nx.NetworkXNoPath:
                access_dist = 0.0

            # Compute return from 'b' back to depot
            try:
                return_dist = nx.shortest_path_length(Gu, b, depot, weight="length")
            except nx.NetworkXNoPath:
                return_dist = 0.0

            total_if_add = current_dist + access_dist + added + return_dist

            if current_dist > 0 and total_if_add > capacity_m:
                # Cut here: close current trip
                trips.append(current_trip)
                current_trip = []
                current_dist = 0.0
                current_node = depot

            if not current_trip:
                # Start of new trip: depot -> a
                current_node = a

            current_trip.append((a, b))
            current_dist += edge_dist
            current_node = b

    if current_trip:
        trips.append(current_trip)

    # Build full route: expand each trip with shortest paths
    full_route = [depot]
    total_distance = 0.0

    for ti, trip in enumerate(trips):
        if ti == 0:
            # First trip starts from depot
            start_node = depot
        else:
            # Subsequent trips start from depot after returning
            pass

        first_edge = trip[0]
        last_node = full_route[-1]

        # Path from current position to first edge's start
        try:
            path_to = nx.shortest_path(Gu, last_node, first_edge[0], weight="length")
            if len(path_to) > 1:
                full_route.extend(path_to[1:])
            total_distance += nx.shortest_path_length(Gu, last_node, first_edge[0], weight="length")
        except nx.NetworkXNoPath:
            pass

        # Traverse all edges in this trip
        for a, b in trip:
            if full_route[-1] != a:
                try:
                    path = nx.shortest_path(Gu, full_route[-1], a, weight="length")
                    if len(path) > 1:
                        full_route.extend(path[1:])
                    total_distance += nx.shortest_path_length(Gu, full_route[-1], a, weight="length")
                except nx.NetworkXNoPath:
                    pass
            full_route.append(b)
            total_distance += edge_length.get((a, b), 0.0)

        # Return to depot
        try:
            path_back = nx.shortest_path(Gu, full_route[-1], depot, weight="length")
            if len(path_back) > 1:
                full_route.extend(path_back[1:])
            total_distance += nx.shortest_path_length(Gu, full_route[-1], depot, weight="length")
        except nx.NetworkXNoPath:
            pass

    t1 = time.perf_counter()

    redundancy = total_distance / total_serviced if total_serviced > 0 else 0

    return {
        "sector": sector_id,
        "route_nodes": full_route,
        "total_distance_m": total_distance,
        "total_serviced_m": total_serviced,
        "redundancy": redundancy,
        "estimated_time_h": total_distance / 1000 / 5,
        "computation_time_s": t1 - t0,
        "num_trips": len(trips),
    }


if __name__ == "__main__":
    for s in range(5):
        r = carp_ulusoy(s)
        print(f"S{s}: dist={r['total_distance_m']/1000:.2f}km "
              f"serv={r['total_serviced_m']/1000:.2f}km "
              f"red={r['redundancy']:.3f} "
              f"trips={r['num_trips']} "
              f"cpu={r['computation_time_s']:.3f}s")
