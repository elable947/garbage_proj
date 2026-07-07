"""
Dijkstra desde scratch sobre grafo dirigido.
Implementacion standalone con heap binario.
"""
import heapq


def dijkstra(adj, source, target=None):
    """
    Dijkstra desde fuente a todos los nodos (o hasta target).

    Args:
        adj: dict {node: {neighbor: weight}} — adyacencia con pesos >= 0
        source: nodo origen
        target: opcional, nodo destino para terminacion temprana

    Returns:
        (dist, prev)
        dist: dict {node: distancia_desde_source}
        prev: dict {node: nodo_anterior_en_camino_minimo}
    """
    dist = {source: 0.0}
    prev = {}
    pq = [(0.0, source)]
    visited = set()

    while pq:
        d, u = heapq.heappop(pq)
        if u in visited:
            continue
        visited.add(u)

        if target is not None and u == target:
            break

        for v, w in adj.get(u, {}).items():
            if v in visited:
                continue
            nd = d + w
            if nd < dist.get(v, float("inf")):
                dist[v] = nd
                prev[v] = u
                heapq.heappush(pq, (nd, v))

    return dist, prev


def shortest_path(adj, source, target):
    """
    Camino minimo dirigido entre source y target.

    Args:
        adj: dict {node: {neighbor: weight}}
        source: nodo origen
        target: nodo destino

    Returns:
        (path_list, total_distance)
        path_list: [source, ..., target] (vacio si no hay camino)
        total_distance: float (inf si no hay camino)
    """
    if source == target:
        return [source], 0.0

    dist, prev = dijkstra(adj, source, target)
    if target not in prev and source != target:
        return [], float("inf")

    path = [target]
    while path[-1] != source:
        path.append(prev[path[-1]])
    path.reverse()

    return path, dist[target]


def build_adjacency(G, weight="length"):
    """
    Construye dict de adyacencia desde un networkx.MultiDiGraph.

    Args:
        G: networkx.MultiDiGraph
        weight: nombre del atributo de peso

    Returns:
        dict {node: {neighbor: min_weight}}
    """
    adj = {}
    for u, v, d in G.edges(data=True):
        w = float(d.get(weight, 1))
        if u not in adj:
            adj[u] = {}
        if v not in adj[u] or w < adj[u][v]:
            adj[u][v] = w
    return adj


if __name__ == "__main__":
    # Test simple
    adj = {
        "A": {"B": 1, "C": 4},
        "B": {"C": 2, "D": 5},
        "C": {"D": 1},
        "D": {},
    }

    path, dist = shortest_path(adj, "A", "D")
    print(f"A->D: path={path}, dist={dist}")

    dists, _ = dijkstra(adj, "A")
    print(f"Dist from A: {dists}")
