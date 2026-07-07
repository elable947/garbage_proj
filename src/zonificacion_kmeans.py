#!/usr/bin/env python
import os
import sys
import warnings

import json
import networkx as nx
import numpy as np
from sklearn.cluster import KMeans
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


INPUT_FILE = "data/grafo_chachapoyas_corregido.graphml"
OUTPUT_FILE = "data/grafo_chachapoyas_sectorizado.graphml"
FIGURE_FILE = "outputs/zonificacion_kmeans.png"
N_CLUSTERS = 5
RANDOM_STATE = 42

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


def _smart_id(val):
    try:
        return int(val)
    except (ValueError, TypeError):
        return str(val)


def _str_to_float(val):
    if isinstance(val, (int, float)):
        return float(val)
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def main():
    recluster = "--recluster" in sys.argv

    # ── 1. Load ─────────────────────────────────────────────────────
    if not os.path.exists(INPUT_FILE):
        print(f"Error: no se encuentra {INPUT_FILE}")
        sys.exit(1)

    G = nx.read_graphml(INPUT_FILE, node_type=_smart_id)
    if not G.is_multigraph():
        G = nx.MultiDiGraph(G)
    mapping = {n: str(n) for n in G.nodes()}
    nx.relabel_nodes(G, mapping, copy=False)

    nnodes = G.number_of_nodes()
    nedges = G.number_of_edges()
    print(f"Grafo cargado: {nnodes} nodos, {nedges} aristas")
    print(f"Nodos excluidos: {EXCLUDED_NODES}")
    print(f"Aristas excluidas (ruta al deposito): {EXCLUDED_EDGES}")

    # ── 2. Coordinates (ALL nodes, track excluded indices) ──────────
    coords = []
    valid_nodes = []
    excluded_indices = set()
    for n in G.nodes:
        xv = _str_to_float(G.nodes[n].get("x"))
        yv = _str_to_float(G.nodes[n].get("y"))
        if xv is None or yv is None:
            continue
        coords.append([xv, yv])
        valid_nodes.append(n)
        if n in EXCLUDED_NODES:
            excluded_indices.add(len(valid_nodes) - 1)
    X = np.array(coords)
    print(f"Total nodos a clusterizar: {len(valid_nodes)} ({len(excluded_indices)} seran marcados como -1 post-hoc)")

    # ── 3. Assign sectors via nearest centroid (static clustering) ──
    CENTROIDS_PATH = "data/sectores.json"
    if recluster or not os.path.exists(CENTROIDS_PATH):
        print(f"\nKMeans k={N_CLUSTERS} {'(recluster forzado)' if recluster else '(primera ejecucion)'}...")
        km = KMeans(n_clusters=N_CLUSTERS, random_state=RANDOM_STATE, n_init=20)
        km.fit(X)
        centroids = km.cluster_centers_
        print("Centroides calculados.")
    else:
        with open(CENTROIDS_PATH) as f_cent:
            cent_data = json.load(f_cent)
        centroids = np.array(cent_data["centroids"])
        print(f"Cargados {len(centroids)} centroides desde {CENTROIDS_PATH}")

    # Assign each node to nearest centroid
    labels = np.zeros(len(valid_nodes), dtype=int)
    for i in range(len(valid_nodes)):
        d = np.sum((X[i] - centroids) ** 2, axis=1)
        labels[i] = int(np.argmin(d))
    print(f"Asignacion por centroide mas cercano completada.")

    # ── 4. Manual adjustments (solo con centroides estaticos) ────────
    if not recluster:
        excl_set = set(excluded_indices)

        s3_idx = np.where(labels == 3)[0]
        s3_idx = s3_idx[~np.isin(s3_idx, np.array(list(excl_set)))]
        if len(s3_idx) > 0:
            s1_idx = np.where(labels == 1)[0]
            s1_idx = s1_idx[~np.isin(s1_idx, np.array(list(excl_set)))]
            if len(s1_idx) > 0:
                s1_x_max = X[s1_idx, 0].max()
                s1_y_max = X[s1_idx, 1].max()
                cond = (X[s3_idx, 0] < s1_x_max) & (X[s3_idx, 1] > s1_y_max)
                cand = s3_idx[cond]
                cand = cand[np.argsort(X[cand, 1])[::-1]]
                n_move = min(6, len(cand))
                for i in cand[:n_move]:
                    labels[i] = 1
                print(f"Ajuste: {n_move} nodos del sector 3 -> sector 1 (izquierda+arriba de S1)")

        s4_idx = np.where(labels == 4)[0]
        s4_idx = s4_idx[~np.isin(s4_idx, np.array(list(excl_set)))]
        if len(s4_idx) > 0:
            s2_idx = np.where(labels == 2)[0]
            s2_idx = s2_idx[~np.isin(s2_idx, np.array(list(excl_set)))]
            if len(s2_idx) > 0:
                s2_x_min = X[s2_idx, 0].min()
                s2_x_max = X[s2_idx, 0].max()
                s2_y_max = X[s2_idx, 1].max()
                s2_y_min = X[s2_idx, 1].min()
                cond_x = (X[s4_idx, 0] >= s2_x_min) & (X[s4_idx, 0] <= s2_x_max)
                s4_near = s4_idx[cond_x]
                if len(s4_near) > 0:
                    y_dist = np.minimum(
                        np.abs(X[s4_near, 1] - s2_y_max),
                        np.abs(X[s4_near, 1] - s2_y_min)
                    )
                    order = np.argsort(y_dist)
                    n_move = min(6, len(s4_near))
                    for i in s4_near[order[:n_move]]:
                        labels[i] = 2
                    print(f"Ajuste: {n_move} nodos del sector 4 -> sector 2 (mas cercanos a S2 en y)")

        s4_idx = np.where(labels == 4)[0]
        s4_idx = s4_idx[~np.isin(s4_idx, np.array(list(excl_set)))]
        if len(s4_idx) > 0:
            s0_idx = set(np.where(labels == 0)[0])
            s0_idx.difference_update(excl_set)
            if len(s0_idx) > 0:
                s0_list = list(s0_idx)
                s0_x_min = X[s0_list, 0].min()
                s0_y_max = X[s0_list, 1].max()
                cand = []
                for i in s4_idx:
                    n = valid_nodes[i]
                    xn, yn = X[i]
                    if xn > s0_x_min and yn < s0_y_max:
                        for _, v, _ in G.out_edges(n, data=True):
                            if v in valid_nodes:
                                vi = valid_nodes.index(v)
                                if vi in s0_idx:
                                    cand.append(i)
                                    break
                n_move = min(6, len(cand))
                for i in cand[:n_move]:
                    labels[i] = 0
                if n_move > 0:
                    print(f"Ajuste: {n_move} nodos del sector 4 -> sector 0 (cerca de S0 con conexion vial)")

    # ── 6. Mark excluded nodes as -1 ─────────────────────────────────
    cluster_indices = [i for i in range(len(valid_nodes)) if i not in excluded_indices]
    excl_indices_list = sorted(excluded_indices)

    # ── 7. Connectivity: fix isolated nodes ──────────────────────────
    print(f"\n--- Reparando nodos aislados ---")
    for s in range(N_CLUSTERS):
        sect_idx = [i for i in cluster_indices if labels[i] == s]
        if not sect_idx:
            continue
        sect_nodes = [valid_nodes[i] for i in sect_idx]
        sub = G.subgraph(sect_nodes)
        nsn = sub.number_of_nodes()
        if nsn < 2:
            continue
        if nx.is_weakly_connected(sub):
            print(f"Sector {s}: {nsn} nodos, conexo")
        else:
            comps = list(nx.weakly_connected_components(sub))
            main_comp = max(comps, key=len)
            print(f"Sector {s}: {len(comps)} componentes (principal {len(main_comp)}/{nsn})")
            fixed = 0
            for comp in comps:
                if comp is main_comp:
                    continue
                for node in comp:
                    ni = valid_nodes.index(node)
                    neighbor_labels = []
                    for _, v, _ in G.edges(node, data=True):
                        if v in valid_nodes:
                            vi = valid_nodes.index(v)
                            if vi in cluster_indices:
                                neighbor_labels.append(labels[vi])
                    for u, _, _ in G.in_edges(node, data=True):
                        if u in valid_nodes:
                            ui = valid_nodes.index(u)
                            if ui in cluster_indices:
                                neighbor_labels.append(labels[ui])
                    if neighbor_labels:
                        most = max(set(neighbor_labels), key=neighbor_labels.count)
                        old = labels[ni]
                        if most != old:
                            labels[ni] = most
                            fixed += 1
                            print(f"  Reasignado {node}: S{old} -> S{most}")
            if fixed == 0:
                print(f"  (no se pudo reasignar ningun nodo aislado)")
    print(f"Reparacion completada.")

    # ── 8. Statistics ──────────────────────────────────────────────
    final_labels = labels[cluster_indices]
    final_counts = np.bincount(final_labels, minlength=N_CLUSTERS)
    total_clustered = len(final_labels)
    print(f"\n{'='*50}")
    print(f"Total en sectores: {total_clustered}")
    print(f"Excluidos:          {len(excluded_indices)} ({EXCLUDED_NODES})")
    print(f"{'='*50}")
    print(f"{'Sector':>8} {'Nodos':>6} {'%':>7}  {'x range':>22}  {'y range':>22}")
    print(f"{'-'*70}")
    for s in range(N_CLUSTERS):
        cnt = int(final_counts[s])
        pct = 100.0 * cnt / total_clustered
        mask = final_labels == s
        pts = X[cluster_indices][mask]
        xmin, xmax = pts[:, 0].min(), pts[:, 0].max()
        ymin, ymax = pts[:, 1].min(), pts[:, 1].max()
        print(f"  S{s}:   {cnt:>4}  {pct:>5.1f}%   [{xmin:.4f}, {xmax:.4f}]  [{ymin:.4f}, {ymax:.4f}]")
    print(f"{'='*50}")

    # ── 9. Assign sector attribute ───────────────────────────────────
    for i, n in enumerate(valid_nodes):
        if i in excluded_indices:
            G.nodes[n]["sector"] = "-1"
        else:
            G.nodes[n]["sector"] = str(int(labels[i]))

    # ── 10. Visualization ───────────────────────────────────────────
    colors = ["#e74c3c", "#3498db", "#2ecc71", "#f39c12", "#9b59b6"]
    fig, ax = plt.subplots(figsize=(12, 10))
    ax.set_facecolor("white")
    fig.patch.set_facecolor("white")

    for s in range(N_CLUSTERS):
        mask = labels == s
        # Exclude the -1 nodes from plotting (they'll be plotted separately)
        plot_mask = np.array([i not in excluded_indices for i in range(len(labels))]) & mask
        if plot_mask.any():
            ax.scatter(
                X[plot_mask, 0], X[plot_mask, 1],
                c=colors[s],
                label=f"Sector {s} ({int(final_counts[s])} nodos)",
                s=18, edgecolors="black", linewidths=0.3, alpha=0.85, zorder=3,
            )

    DEPOT_ID = "af3202cd-3a9f-4a98-bdd0-28e64cac4795"
    CONNECTOR_ID = "ebde992d-a470-4566-a4b9-3830567e8f78"
    for i, n in enumerate(excl_indices_list):
        dx, dy = X[n]
        node_id = valid_nodes[n]
        if node_id == DEPOT_ID:
            ax.scatter(dx, dy, c="white", edgecolors="black", linewidths=1.5,
                       s=140, marker="s", zorder=6, label="Deposito")
            ax.annotate("Deposito", xy=(dx, dy), xytext=(8, 8),
                        textcoords="offset points", fontsize=9, fontweight="bold",
                        bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="black", lw=0.5))
        elif node_id == CONNECTOR_ID:
            ax.scatter(dx, dy, c="#555555", edgecolors="white", linewidths=1.2,
                       s=80, marker="s", zorder=5, label="Conector")
            ax.annotate("Conector", xy=(dx, dy), xytext=(8, -12),
                        textcoords="offset points", fontsize=8, fontstyle="italic",
                        bbox=dict(boxstyle="round,pad=0.2", fc="#555", ec="white", lw=0.5))
        else:
            ax.scatter(dx, dy, c="#555555", edgecolors="white", linewidths=1.2,
                       s=80, marker="s", zorder=5, label="Excluido")

    # Draw Voronoi-like boundaries from centroids
    x_min, x_max = X[:, 0].min() - 0.005, X[:, 0].max() + 0.005
    y_min, y_max = X[:, 1].min() - 0.005, X[:, 1].max() + 0.005
    xx, yy = np.meshgrid(np.linspace(x_min, x_max, 200),
                         np.linspace(y_min, y_max, 200))
    grid_pts = np.c_[xx.ravel(), yy.ravel()]
    d = np.sum((grid_pts[:, np.newaxis, :] - centroids[np.newaxis, :, :]) ** 2, axis=2)
    Z = np.argmin(d, axis=1).reshape(xx.shape)
    for s in range(N_CLUSTERS):
        mask_z = Z == s
        if mask_z.any():
            ax.contour(xx, yy, Z, levels=[s - 0.5, s + 0.5],
                       colors=[colors[s]], linewidths=0.8, alpha=0.3)

    ax.set_xlabel("Longitud")
    ax.set_ylabel("Latitud")
    ax.set_title(f"Zonificacion KMeans - Chachapoyas ({N_CLUSTERS} sectores)", fontsize=14)
    ax.legend(markerscale=2, fontsize=10)
    ax.grid(True, alpha=0.3, linestyle="--")
    ax.set_aspect("equal")
    plt.tight_layout()
    fig.savefig(FIGURE_FILE, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"\nFigura guardada: {FIGURE_FILE}")

    # ── 11. Export sectores.json (static mapping + centroids) ─────
    with open("data/sectores.json", "w") as f:
        json.dump({
            "sectores": {n: int(G.nodes[n].get("sector", -1)) for n in G.nodes},
            "centroids": centroids.tolist(),
            "excluded": list(EXCLUDED_NODES),
            "excluded_edges": list(EXCLUDED_EDGES),
        }, f, indent=2)
    print(f"Exportado: data/sectores.json ({len(G.nodes)} nodos, {N_CLUSTERS} centroides, {len(EXCLUDED_EDGES)} aristas excluidas)")

    # ── 12. Export graphml ─────────────────────────────────────────
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

    size = os.path.getsize(OUTPUT_FILE)
    print(f"Exportado: {OUTPUT_FILE} ({size / 1024:.0f} KB)")
    print("\nZonificacion completada.")


if __name__ == "__main__":
    main()
