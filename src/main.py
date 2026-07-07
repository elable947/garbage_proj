"""
Orquestador principal.
Ejecuta los 3 algoritmos de ruteo sobre los 5 sectores de Chachapoyas
y presenta una tabla comparativa de metricas.

Uso: python src/main.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import time
from collections import defaultdict

from _data import _load_data
from voraz import voraz
from dcpp import dcpp
from carp_tabu import carp_tabu


def _print_separator(char="="):
    print(char * 90)


def _print_header():
    _print_separator()
    print(f"{'Sector':>6} {'Algoritmo':>18} {'Dist(km)':>10} {'Serv(km)':>10} "
          f"{'Redund':>8} {'Tiempo(h)':>10} {'CPU(s)':>8}")
    _print_separator("-")


def _print_row(sector, algo, dist_km, serv_km, redund, time_h, cpu_s, extra=""):
    print(f"{sector:>6} {algo:>18} {dist_km:>10.2f} {serv_km:>10.2f} "
          f"{redund:>8.3f} {time_h:>10.2f} {cpu_s:>8.3f}  {extra}")


def main():
    print("=" * 90)
    print("  RUTEO DE RECOLECCION DE RESIDUOS - CHACHAPOYAS")
    print("  Algoritmos: Voraz (Greedy) | DCPP (Min-Cost Flow + Hierholzer) | CARP + Tabu Search")
    print("  Velocidad asumida: 5 km/h  |  Capacidad CARP: 30 km por viaje")
    print("=" * 90)

    G, _Gu, _depot, sector_edges = _load_data()
    sector_km = {}
    for u, v, k in G.edges(keys=True):
        s = G.nodes[u].get("sector", -1)
        if 0 <= s <= 4:
            sector_km[s] = sector_km.get(s, 0) + G.edges[u, v, k]["length"] / 1000
    total_serv_km = sum(sector_km.values())

    print(f"\nTotal calles a servir: {total_serv_km:.2f} km en 5 sectores\n")

    # ── Voraz ──
    _print_header()
    voraz_results = {}
    for s in range(5):
        r = voraz(s)
        voraz_results[s] = r
        _print_row(s, "Voraz", r["total_distance_m"] / 1000,
                   r["total_serviced_m"] / 1000, r["redundancy"],
                   r["estimated_time_h"], r["computation_time_s"])

    # ── DCPP ──
    _print_separator("-")
    dcpp_results = {}
    for s in range(5):
        r = dcpp(s)
        dcpp_results[s] = r
        _print_row(s, "DCPP", r["total_distance_m"] / 1000,
                   r["total_serviced_m"] / 1000, r["redundancy"],
                   r["estimated_time_h"], r["computation_time_s"],
                   f"imb={r.get('imbalance_units',0)}")

    # ── CARP + Tabu ──
    _print_separator("-")
    carp_results = {}
    for s in range(5):
        r = carp_tabu(s, max_iter=150)
        carp_results[s] = r
        _print_row(s, "CARP+Tabu", r["total_distance_m"] / 1000,
                   r["total_serviced_m"] / 1000, r["redundancy"],
                   r["estimated_time_h"], r["computation_time_s"],
                   f"mej={r.get('improvement_pct',0):.1f}%")

    # ── Resumen ──
    _print_separator()
    print(f"\n{'':>6} {'ALGORITMO':>18} {'TOT(km)':>10} {'REDUND':>8} {'TIEMPO(h)':>10} {'CPU(s)':>8}")
    _print_separator("-")

    for algo_name, results in [("Voraz", voraz_results), ("DCPP", dcpp_results), ("CARP+Tabu", carp_results)]:
        tot_km = sum(r["total_distance_m"] for r in results.values()) / 1000
        avg_red = sum(r["redundancy"] for r in results.values()) / 5
        tot_h = sum(r["estimated_time_h"] for r in results.values())
        tot_cpu = sum(r["computation_time_s"] for r in results.values())
        print(f"{'TOTAL':>6} {algo_name:>18} {tot_km:>10.2f} {avg_red:>8.3f} {tot_h:>10.2f} {tot_cpu:>8.3f}")

    _print_separator()

    # Mejor algoritmo por sector
    print("\n--- Mejor algoritmo por sector (menor distancia) ---")
    for s in range(5):
        best = min(
            ("Voraz", voraz_results[s]),
            ("DCPP", dcpp_results[s]),
            ("CARP+Tabu", carp_results[s]),
            key=lambda x: x[1]["total_distance_m"],
        )
        print(f"  Sector {s}: {best[0]} ({best[1]['total_distance_m']/1000:.2f} km)")


def main_detailed():
    """Version detallada con ruta completa."""
    algo = input("Algoritmo (voraz|dcpp|carp): ").strip().lower()
    sector = int(input("Sector (0-4): ").strip())

    if algo == "voraz":
        r = voraz(sector)
    elif algo == "dcpp":
        r = dcpp(sector)
    elif algo == "carp":
        r = carp_tabu(sector, max_iter=150)
    else:
        print("Algoritno invalido")
        return

    print(f"\n{'='*60}")
    print(f"  {algo.upper()} - Sector {sector}")
    print(f"  Distancia total:  {r['total_distance_m']/1000:.2f} km")
    print(f"  Distancia servida: {r['total_serviced_m']/1000:.2f} km")
    print(f"  Redundancia:     {r['redundancy']:.3f}")
    print(f"  Tiempo estimado: {r['estimated_time_h']:.2f} h")
    print(f"  Tiempo CPU:      {r['computation_time_s']:.3f} s")
    if 'initial_distance_m' in r:
        print(f"  Mejora Tabu:     {r.get('improvement_pct',0):.1f}%")
    print(f"  Nodos en ruta:   {len(r['route_nodes'])}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
