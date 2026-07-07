"""
Elimina aristas duplicadas (misma direccion u→v con multiples keys)
de los 3 archivos graphml. Conserva solo la key mas baja por par (u,v).
"""
import os
import networkx as nx
from collections import defaultdict

FILES = [
    "data/grafo_chachapoyas_original.graphml",
    "data/grafo_chachapoyas_corregido.graphml",
    "data/grafo_chachapoyas_sectorizado.graphml",
]

for fp in FILES:
    if not os.path.exists(fp):
        print(f"No encontrado: {fp}")
        continue

    G = nx.read_graphml(fp, node_type=str)
    if not G.is_multigraph():
        G = nx.MultiDiGraph(G)

    before = G.number_of_edges()

    # For each (u,v) keep only the smallest key
    to_remove = []
    for u, v in set(G.edges()):
        keys = sorted(G[u][v].keys())
        if len(keys) > 1:
            for k in keys[1:]:
                to_remove.append((u, v, k))

    for u, v, k in to_remove:
        G.remove_edge(u, v, k)

    after = G.number_of_edges()
    removed = before - after
    print(f"{os.path.basename(fp)}: {before} -> {after} aristas ({removed} eliminadas)")

    if removed == 0:
        continue

    tmp = fp + ".tmp"
    try:
        nx.write_graphml(G, tmp)
        os.replace(tmp, fp)
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise

print("\nDeduplicacion completada.")
