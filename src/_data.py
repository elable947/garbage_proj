import json
import networkx as nx
import numpy as np
from collections import defaultdict


def _load_data():
    with open("data/sectores.json") as f:
        si = json.load(f)
    static_sectores = si["sectores"]
    centroids = np.array(si["centroids"])

    G = nx.read_graphml("data/grafo_chachapoyas_corregido.graphml", node_type=str)
    if not G.is_multigraph():
        G = nx.MultiDiGraph(G)
    for n in G.nodes:
        G.nodes[n]["x"] = float(G.nodes[n]["x"])
        G.nodes[n]["y"] = float(G.nodes[n]["y"])
        if n in static_sectores:
            G.nodes[n]["sector"] = static_sectores[n]
        else:
            xn, yn = G.nodes[n]["x"], G.nodes[n]["y"]
            d = np.sum((centroids - np.array([xn, yn]))**2, axis=1)
            G.nodes[n]["sector"] = int(np.argmin(d))
    for u, v, k in G.edges(keys=True):
        G.edges[u, v, k]["length"] = float(G.edges[u, v, k].get("length", 0))
        G.edges[u, v, k]["oneway"] = str(G.edges[u, v, k].get("oneway", "false")).lower() == "true"

    depot = "af3202cd-3a9f-4a98-bdd0-28e64cac4795"
    Gu = G.to_undirected()

    sector_edges = defaultdict(list)
    for u, v, k in G.edges(keys=True):
        s = G.nodes[u].get("sector", -1)
        if 0 <= s <= 4:
            sector_edges[s].append((u, v, k))

    return G, Gu, depot, dict(sector_edges)
