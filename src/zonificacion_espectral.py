#!/usr/bin/env python
"""
Zonificacion por region-growing desde semillas distribuidas sobre el grafo vial.
Garantiza conectividad por construccion y balance de kilometros entre sectores.

A diferencia de K-Means (coordenadas) y Spectral Clustering (matriz laplaciana),
el region-growing expande sectores mediante BFS sobre la red vial, respetando
la topologia y balanceando explicitamente la carga de trabajo.

Uso: python src/zonificacion_espectral.py
"""
import os
import sys
import json
import heapq
import networkx as nx
import numpy as np
from collections import deque
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

INPUT_FILE = "data/grafo_chachapoyas_corregido.graphml"
OUTPUT_FILE = "data/grafo_chachapoyas_sectorizado.graphml"
FIGURE_FILE = "outputs/zonificacion_espectral.png"
SECTORES_FILE = "data/sectores.json"
N_CLUSTERS = 5

EXCLUDED_NODES = {
    "af3202cd-3a9f-4a98-bdd0-28e64cac4795",
    "ebde992d-a470-4566-a4b9-3830567e8f78",
    "5430646999",
    "635223275",
}

EXCLUDED_EDGES = {
    "d82847bd-8dff-47ef-aad7-212a4d8aea52",
    "81ceeece-6c08-4bd3-9d47-1deca6a3941b",
    "f25eb237-f2ed-49e4-85d7-0f0ac12326f2",
}

COLORS = ["#e74c3c", "#3498db", "#2ecc71", "#f39c12", "#9b59b6"]
DEPOT_ID = "af3202cd-3a9f-4a98-bdd0-28e64cac4795"
CONNECTOR_ID = "ebde992d-a470-4566-a4b9-3830567e8f78"


def _smart_id(val):
    try:
        return int(val)
    except (ValueError, TypeError):
        return str(val)


def _select_seeds(G, cluster_nodes, k):
    """Pick k seed nodes spaced geographically across the graph."""
    # Get coordinates
    nodes_xy = []
    for n in cluster_nodes:
        x = float(G.nodes[n].get("x", 0))
        y = float(G.nodes[n].get("y", 0))
        nodes_xy.append((n, x, y))
    if not nodes_xy:
        return []

    arr = np.array([(x, y) for _, x, y in nodes_xy])
    # Pick the 4 corners + center
    seeds = []
    # Top-left
    seeds.append(nodes_xy[np.argmin(arr[:, 0] + arr[:, 1])][0])
    # Bottom-right
    seeds.append(nodes_xy[np.argmax(arr[:, 0] + arr[:, 1])][0])
    # Top-right
    seeds.append(nodes_xy[np.argmax(arr[:, 0] - arr[:, 1])][0])
    # Bottom-left
    seeds.append(nodes_xy[np.argmin(arr[:, 0] - arr[:, 1])][0])
    # Center (closest to mean)
    center = arr.mean(axis=0)
    seeds.append(nodes_xy[np.argmin(np.sum((arr - center)**2, axis=1))][0])

    # Deduplicate
    seen = set()
    unique = []
    for s in seeds:
        if s not in seen:
            seen.add(s)
            unique.append(s)
    return unique[:k]


def main():
    if not os.path.exists(INPUT_FILE):
        print(f"Error: no se encuentra {INPUT_FILE}")
        sys.exit(1)

    G = nx.read_graphml(INPUT_FILE, node_type=_smart_id)
    if not G.is_multigraph():
        G = nx.MultiDiGraph(G)
    mapping = {n: str(n) for n in G.nodes()}
    nx.relabel_nodes(G, mapping, copy=False)

    print(f"Grafo cargado: {G.number_of_nodes()} nodos, {G.number_of_edges()} aristas")
    print(f"Nodos excluidos: {EXCLUDED_NODES}")
    print(f"Aristas excluidas (ruta al deposito): {EXCLUDED_EDGES}")

    Gu = G.to_undirected()
    # Normalize edge lengths to float for Dijkstra
    for u, v, d in Gu.edges(data=True):
        try:
            d["length"] = float(d.get("length", 0))
        except (ValueError, TypeError):
            d["length"] = 0.0
    cluster_nodes = [n for n in Gu.nodes if n not in EXCLUDED_NODES]
    print(f"Nodos para clustering: {len(cluster_nodes)} (excluidos {len(EXCLUDED_NODES)})")

    # Calculate edge lengths per node (sum of incident required edge lengths)
    node_km = {}
    for u, v, k in G.edges(keys=True):
        try:
            w = float(G.edges[u, v, k].get("length", 0))
        except (ValueError, TypeError):
            w = 0
        if w > 0:
            node_km[u] = node_km.get(u, 0) + w

    total_km = sum(node_km.get(n, 0) for n in cluster_nodes)
    target_km = total_km / N_CLUSTERS
    print(f"Total km a servir: {total_km / 1000:.2f}")
    print(f"Target por sector: {target_km / 1000:.2f} km")

    # Select seeds using furthest-point sampling
    seeds = _select_seeds(G, cluster_nodes, N_CLUSTERS)
    print(f"Semillas seleccionadas: {len(seeds)}")

    # Simultaneous BFS from all seeds: assign each node to its parent's sector
    labels = {n: -1 for n in cluster_nodes}
    sector_km = [0.0] * N_CLUSTERS
    parent_sector = {}

    # Initialize frontiers
    frontier = deque()
    for i, seed in enumerate(seeds):
        labels[seed] = i
        sector_km[i] += node_km.get(seed, 0)
        parent_sector[seed] = i
        frontier.append(seed)

    target_each = total_km / N_CLUSTERS

    while frontier:
        node = frontier.popleft()
        current_sector = parent_sector[node]
        for neighbor in Gu.neighbors(node):
            if neighbor not in cluster_nodes:
                continue
            if labels[neighbor] >= 0:
                continue
            # Only expand if the parent's sector still needs more km
            if sector_km[current_sector] < target_each * 1.15:
                labels[neighbor] = current_sector
                parent_sector[neighbor] = current_sector
                sector_km[current_sector] += node_km.get(neighbor, 0)
                frontier.append(neighbor)
            # else: leave unassigned for now, will be handled below

    # Assign any remaining unassigned nodes to nearest active sector
    unassigned = [n for n in cluster_nodes if labels[n] < 0]
    if unassigned:
        print(f"  Asignando {len(unassigned)} nodos residuales al sector mas cercano...")
        for n in unassigned:
            neighbor_sectors = {}
            for neighbor in Gu.neighbors(n):
                nl = labels.get(neighbor, -1)
                if nl >= 0:
                    neighbor_sectors[nl] = neighbor_sectors.get(nl, 0) + 1
            if neighbor_sectors:
                chosen = max(neighbor_sectors, key=neighbor_sectors.get)
            else:
                chosen = int(np.argmin(sector_km))
            labels[n] = chosen
            sector_km[chosen] += node_km.get(n, 0)

    # Post-balancing: move boundary nodes from over-capacity to under-capacity sectors
    max_iter = 20
    for iteration in range(max_iter):
        over = [i for i in range(N_CLUSTERS) if sector_km[i] > target_each * 1.05]
        under = [i for i in range(N_CLUSTERS) if sector_km[i] < target_each * 0.95]
        if not over or not under:
            break
        moved = 0
        for o in over:
            for n in list(cluster_nodes):
                if labels.get(n, -1) != o:
                    continue
                neighbors_sectors = set()
                for neighbor in Gu.neighbors(n):
                    nl = labels.get(neighbor, -1)
                    if nl >= 0 and nl != o:
                        neighbors_sectors.add(nl)
                for u in under:
                    if u in neighbors_sectors:
                        km_n = node_km.get(n, 0)
                        if sector_km[u] + km_n < target_each * 1.05:
                            labels[n] = u
                            sector_km[o] -= km_n
                            sector_km[u] += km_n
                            moved += 1
                            break
        if moved == 0:
            break

    # Connectivity repair: fix isolated nodes
    print("\n--- Reparando nodos aislados ---")
    # Pre-compute centroids for geographic fallback
    _coords = [[] for _ in range(N_CLUSTERS)]
    for n in cluster_nodes:
        s = labels.get(n, -1)
        if s >= 0:
            _coords[s].append([float(G.nodes[n].get("x", 0)), float(G.nodes[n].get("y", 0))])
    _centroids = np.zeros((N_CLUSTERS, 2))
    for s in range(N_CLUSTERS):
        if _coords[s]:
            _centroids[s] = np.array(_coords[s]).mean(axis=0)

    for s in range(N_CLUSTERS):
        sect_nodes = [n for n in cluster_nodes if labels.get(n, -1) == s]
        if len(sect_nodes) < 2:
            continue
        sub = Gu.subgraph(sect_nodes)
        if nx.is_connected(sub):
            print(f"Sector {s}: {len(sect_nodes)} nodos, CONEXO")
        else:
            comps = list(nx.connected_components(sub))
            main_comp = max(comps, key=len)
            print(f"Sector {s}: {len(comps)} componentes (principal {len(main_comp)}/{len(sect_nodes)})")
            fixed = 0
            for comp in comps:
                if comp is main_comp:
                    continue
                for node in comp:
                    neighbor_labels = []
                    for neighbor in Gu.neighbors(node):
                        nl = labels.get(neighbor, -1)
                        if nl >= 0 and nl != s:
                            neighbor_labels.append(nl)
                    if neighbor_labels:
                        most = max(set(neighbor_labels), key=neighbor_labels.count)
                        old = labels[node]
                        if most != old:
                            km_n = node_km.get(node, 0)
                            sector_km[old] -= km_n
                            sector_km[most] += km_n
                            labels[node] = most
                            fixed += 1
                            print(f"  Reasignado {node}: S{old} -> S{most}")
            if fixed == 0:
                # Fallback: geographic reassignment for nodes with no neighbor sectors
                for comp in comps:
                    if comp is main_comp:
                        continue
                    for node in comp:
                        nx_n = float(G.nodes[node].get("x", 0))
                        ny_n = float(G.nodes[node].get("y", 0))
                        best_s = min((si for si in range(N_CLUSTERS) if si != s),
                                     key=lambda si: (_centroids[si][0] - nx_n)**2 + (_centroids[si][1] - ny_n)**2)
                        km_n = node_km.get(node, 0)
                        sector_km[s] -= km_n
                        sector_km[best_s] += km_n
                        labels[node] = best_s
                        fixed += 1
                        print(f"  Reasignado (geografico) {node}: S{s} -> S{best_s}")
                if fixed == 0:
                    print(f"  (no se pudo reasignar ningun nodo aislado)")
    print("Reparacion completada.")

    # Assign excluded nodes
    labels_full = dict(labels)
    for n in EXCLUDED_NODES:
        labels_full[n] = -1

    # Write sector attribute to G
    for n in G.nodes:
        s = labels_full.get(n, -1)
        G.nodes[n]["sector"] = str(s)

    # Rebuild coords and centroids for statistics + visualization
    coords_list = [[] for _ in range(N_CLUSTERS)]
    for n in cluster_nodes:
        s = labels.get(n, -1)
        if s >= 0:
            coords_list[s].append([float(G.nodes[n].get("x", 0)), float(G.nodes[n].get("y", 0))])

    centroids = np.zeros((N_CLUSTERS, 2))
    for s in range(N_CLUSTERS):
        if coords_list[s]:
            centroids[s] = np.array(coords_list[s]).mean(axis=0)

    # Statistics
    print(f"\n{'='*50}")
    print(f"Sectores generados por region-growing")
    print(f"Total km servido: {sum(sector_km)/1000:.2f}")
    print(f"{'Sector':>8} {'Nodos':>6}  {'km':>8}  {'x range':>22}  {'y range':>22}")
    print(f"{'-'*70}")
    for s in range(N_CLUSTERS):
        cnt = sum(1 for n in cluster_nodes if labels.get(n, -1) == s)
        pts = np.array(coords_list[s]) if coords_list[s] else np.zeros((1, 2))
        xmin, xmax = pts[:, 0].min(), pts[:, 0].max()
        ymin, ymax = pts[:, 1].min(), pts[:, 1].max()
        print(f"  S{s}:   {cnt:>4}  {sector_km[s]/1000:>7.2f}   [{xmin:.4f}, {xmax:.4f}]  [{ymin:.4f}, {ymax:.4f}]")
    print(f"{'='*50}")

    # Visualization
    fig, ax = plt.subplots(figsize=(12, 10))
    ax.set_facecolor("white")
    fig.patch.set_facecolor("white")

    for s in range(N_CLUSTERS):
        pts = np.array(coords_list[s]) if coords_list[s] else np.empty((0, 2))
        if len(pts) > 0:
            ax.scatter(pts[:, 0], pts[:, 1], c=COLORS[s],
                       label=f"Sector {s} ({len(pts)} nodos, {sector_km[s]/1000:.1f} km)",
                       s=18, edgecolors="black", linewidths=0.3, alpha=0.85, zorder=3)

    for n in EXCLUDED_NODES:
        if n in G.nodes:
            dx = float(G.nodes[n].get("x", 0))
            dy = float(G.nodes[n].get("y", 0))
            lbl = "Deposito" if n == DEPOT_ID else "Conector" if n == CONNECTOR_ID else "Excluido"
            ax.scatter(dx, dy, c="white" if n == DEPOT_ID else "#555",
                       edgecolors="black", linewidths=1.5,
                       s=140 if n == DEPOT_ID else 80,
                       marker="s", zorder=6, label=lbl)

    ax.set_xlabel("Longitud")
    ax.set_ylabel("Latitud")
    ax.set_title("Zonificacion Region-Growing - Chachapoyas (5 sectores)", fontsize=14)
    ax.legend(markerscale=2, fontsize=9)
    ax.grid(True, alpha=0.3, linestyle="--")
    ax.set_aspect("equal")
    plt.tight_layout()
    os.makedirs(os.path.dirname(FIGURE_FILE), exist_ok=True)
    fig.savefig(FIGURE_FILE, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"\nFigura guardada: {FIGURE_FILE}")

    # Export sectores.json
    with open(SECTORES_FILE, "w") as f:
        json.dump({
            "sectores": {n: int(G.nodes[n].get("sector", -1)) for n in G.nodes},
            "centroids": centroids.tolist(),
            "excluded": list(EXCLUDED_NODES),
            "excluded_edges": list(EXCLUDED_EDGES),
        }, f, indent=2)
    print(f"Exportado: {SECTORES_FILE}")

    # Export graphml
    for n in G.nodes:
        for k, v in list(G.nodes[n].items()):
            if isinstance(v, bool):
                G.nodes[n][k] = str(v).lower()
            elif isinstance(v, (int, float)) and k != "sector":
                G.nodes[n][k] = str(v)
    G.graph["node_default"] = {}
    G.graph["edge_default"] = {}
    tmp_path = OUTPUT_FILE + ".tmp"
    try:
        nx.write_graphml(G, tmp_path)
        os.replace(tmp_path, OUTPUT_FILE)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise
    print(f"Exportado: {OUTPUT_FILE} ({os.path.getsize(OUTPUT_FILE) / 1024:.0f} KB)")
    print("\nZonificacion por region-growing completada.")


if __name__ == "__main__":
    main()
