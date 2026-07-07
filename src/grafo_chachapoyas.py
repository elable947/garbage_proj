import osmnx as ox
import sys

def main():
    ox.settings.use_cache = True
    ox.settings.log_console = False

    print("Obteniendo ubicación de Chachapoyas...")
    center = ox.geocode("Chachapoyas, Amazonas, Peru")
    print(f"Centro: {center}")

    G = ox.graph_from_point(center, dist=3000, network_type="drive", retain_all=True, simplify=True)

    print(f"\nNodos: {G.number_of_nodes()}")
    print(f"Aristas: {G.number_of_edges()}")
    print(f"Tipo: {type(G).__name__}")

    out_path = "data/grafo_chachapoyas_original.graphml"
    print(f"\nExportando a {out_path}...")
    ox.save_graphml(G, out_path)
    print(f"Grafo original guardado en {out_path}")

if __name__ == "__main__":
    main()
