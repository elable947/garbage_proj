#!/usr/bin/env python
"""
Visor live de rutas con animacion de carrito recolector.
Ejecuta los algoritmos para los 5 sectores y permite elegir
sector y algoritmo para la animacion.

Uso: python src/visor_rutas_anim.py
"""
import json
import os
import sys
import webbrowser
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import networkx as nx
from shapely import wkt as wkt_module

from _data import _load_data
from voraz import voraz
from dcpp import dcpp
from carp_tabu import carp_tabu
from carp_ulusoy import carp_ulusoy

SECTOR_COLORS = {0: "#e74c3c", 1: "#3498db", 2: "#2ecc71", 3: "#f39c12", 4: "#9b59b6"}
SECTOR_NAMES = {0: "S0", 1: "S1", 2: "S2", 3: "S3", 4: "S4"}
ALGO_NAMES = {
    "voraz": "Voraz", "dcpp": "DCPP",
    "carp_tabu": "CARP+Tabu", "carp_ulusoy": "CARP-Ulusoy",
}

G = None
Gu = None
depot = None
all_routes = {}
best_algo = {}
edge_geoms = {}  # {(u, v): [(lat, lon), ...]}


def _parse_geometry(val):
    if not val:
        return None
    try:
        if isinstance(val, str):
            if "LINESTRING" not in val:
                return None
            geom = wkt_module.loads(val)
        else:
            geom = val
        return [(lat, lon) for lon, lat in geom.coords]
    except Exception:
        return None


def _node_ll(n):
    return (G.nodes[n]["y"], G.nodes[n]["x"])


def _build_edge_geoms():
    global edge_geoms
    for u, v, k in G.edges(keys=True):
        val = G.edges[u, v, k].get("geometry")
        pts = _parse_geometry(val)
        if pts:
            edge_geoms[(u, v)] = pts
        else:
            # Fallback: use node coordinates as 2-point geometry
            try:
                ux, uy = float(G.nodes[u]["x"]), float(G.nodes[u]["y"])
                vx, vy = float(G.nodes[v]["x"]), float(G.nodes[v]["y"])
                edge_geoms[(u, v)] = [(uy, ux), (vy, vx)]
            except (ValueError, KeyError, TypeError):
                pass


def _edge_coords(a, b):
    pts = edge_geoms.get((a, b))
    if pts:
        return pts
    pts = edge_geoms.get((b, a))
    if pts:
        return list(reversed(pts))
    return None


def _route_to_coords(nodes):
    if not nodes:
        return []
    coords = [_node_ll(nodes[0])]
    for i in range(len(nodes) - 1):
        a, b = nodes[i], nodes[i + 1]
        if a == b:
            continue
        geom = _edge_coords(a, b)
        if geom and len(geom) > 1:
            for pt in geom[1:]:
                coords.append(pt)
        else:
            # Edge not in graph: expand shortest path through intermediate nodes
            try:
                sp = nx.shortest_path(Gu, a, b, weight="length")
                for j in range(1, len(sp)):
                    seg = _edge_coords(sp[j-1], sp[j])
                    if seg and len(seg) > 1:
                        for pt in (seg if j == 1 else seg[1:]):
                            coords.append(pt)
                    else:
                        coords.append(_node_ll(sp[j]))
            except nx.NetworkXNoPath:
                coords.append(_node_ll(b))
    return coords


def compute_all_routes():
    global G, Gu, depot, all_routes, best_algo
    print("Cargando datos...")
    G, Gu, depot, _se = _load_data()
    _build_edge_geoms()
    print(f"  Geometrias: {len(edge_geoms)} aristas con curvas")

    algos = [
        ("voraz", voraz, {}),
        ("dcpp", dcpp, {}),
        ("carp_tabu", carp_tabu, {"max_iter": 150}),
        ("carp_ulusoy", carp_ulusoy, {}),
    ]

    for key, func, kwargs in algos:
        print(f"  Ejecutando {key}...")
        for s in range(5):
            r = func(s, **kwargs)
            coords = _route_to_coords(r["route_nodes"])
            last_node = r["route_nodes"][-1] if r["route_nodes"] else depot
            if last_node != depot:
                try:
                    sp = nx.shortest_path(Gu, last_node, depot, weight="length")
                    return_coords = _route_to_coords(sp)
                except nx.NetworkXNoPath:
                    return_coords = []
            else:
                return_coords = []
            all_routes[(s, key)] = {
                "coords": coords,
                "return_coords": return_coords,
                "dist_km": round(r["total_distance_m"] / 1000, 2),
                "serv_km": round(r["total_serviced_m"] / 1000, 2),
                "redund": round(r["redundancy"], 3),
                "extra": r.get("imbalance_units", r.get("num_trips",
                         r.get("improvement_pct", ""))),
            }

    for s in range(5):
        best = min((k for k in [a[0] for a in algos]),
                   key=lambda k: all_routes[(s, k)]["dist_km"])
        best_algo[s] = best
        print(f"  S{s}: mejor = {ALGO_NAMES[best]} ({all_routes[(s,best)]['dist_km']} km)")

    print(f"Listo. {len(all_routes)} rutas calculadas.")


HTML = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Rutas Animadas - Chachapoyas</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:system-ui,sans-serif;background:#1a1a2e;color:#eee;display:flex;flex-direction:column;height:100vh}
#map{flex:1;width:100%}
#panel{background:#16213e;padding:10px 16px;display:flex;align-items:center;gap:12px;flex-wrap:wrap;border-top:2px solid #0f3460;font-size:13px}
#panel button{background:#0f3460;color:#fff;border:none;padding:7px 16px;border-radius:6px;cursor:pointer;font-size:13px;font-weight:bold}
#panel button:hover{background:#1a4a8a}
#panel select{background:#1a1a2e;color:#eee;border:1px solid #0f3460;padding:6px 10px;border-radius:6px;font-size:13px}
#panel label{font-size:12px;color:#aaa;display:flex;align-items:center;gap:4px}
#panel input[type=range]{width:70px;accent-color:#2ecc71}
#status{font-size:12px;color:#888;flex:1;text-align:right}
.legend{background:rgba(22,33,62,.92);padding:10px 14px;border-radius:8px;font-size:12px;line-height:1.7;min-width:180px;color:#ddd}
.legend i{display:inline-block;width:12px;height:3px;border-radius:2px;margin-right:6px;vertical-align:middle}
.info-msg{background:rgba(22,33,62,.92);padding:10px 14px;border-radius:8px;font-size:12px;margin-top:6px;color:#ddd}
</style>
</head>
<body>
<div id="map"></div>
<div id="panel">
  <label>Sector:
    <select id="sectorSelect">
      <option value="0">S0</option><option value="1">S1</option>
      <option value="2">S2</option><option value="3">S3</option><option value="4">S4</option>
    </select>
  </label>
  <label>Algoritmo:
    <select id="algoSelect">
      <option value="voraz">Voraz</option><option value="dcpp">DCPP</option>
      <option value="carp_tabu">CARP+Tabu</option><option value="carp_ulusoy">CARP-Ulusoy</option>
    </select>
  </label>
  <button id="playBtn">&#9654; Play</button>
  <button id="resetBtn">&#8634; Reset</button>
  <label>Vel: <input type="range" id="speedSlider" min="1" max="20" value="5">
  <span id="speedLabel">5x</span></label>
  <div style="font-size:12px;color:#aaa">Progreso: <span id="progress">0</span>/<span id="total">0</span></div>
  <div id="status">Cargando...</div>
</div>
<script>
const COLORS = __COLORS__;
const ALGO_NAMES = __ALGO_NAMES__;
const SECTOR_NAMES = __SECTOR_NAMES__;
const BEST_ALGO = __BEST_ALGO__;
const DEPOT = __DEPOT__;

const map = L.map("map", {zoomControl: true}).setView([-6.23, -77.87], 14);
L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", {
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>',
  maxZoom: 19,
}).addTo(map);

L.circleMarker(DEPOT, {radius:8, color:"#000", fillColor:"#fff", fillOpacity:1, weight:3})
  .addTo(map).bindTooltip("Deposito", {permanent:true, direction:"top"});

const cartIcon = L.divIcon({
  html: '<div style="background:#fff;border:2px solid #e67e22;border-radius:50%;width:14px;height:14px;box-shadow:0 0 8px #e67e22"></div>',
  iconSize: [14,14], iconAnchor: [7,7],
});
const cartMarker = L.marker([0,0], {icon: cartIcon, zIndexOffset:1000}).addTo(map);
const trailLine = L.polyline([], {color:"#e67e22", weight:4, opacity:0.9, dashArray:"6,4"}).addTo(map);
const returnLine = L.polyline([], {color:"#e74c3c", weight:4, opacity:0.8, dashArray:"10,6"}).addTo(map);
const bgLines = {};

let allData = {};
let playing = false, idx = 0, speed = 5, animTimer = null;
let currentSector = 0, currentAlgo = "";

const legend = L.control({position:"bottomright"});
legend.onAdd = function() {
  const div = L.DomUtil.create("div", "legend");
  div.id = "legendDiv";
  div.innerHTML = "<b>Rutas</b><br>Cargando...";
  return div;
};
legend.addTo(map);

const info = L.control({position:"bottomleft"});
info.onAdd = function() {
  const div = L.DomUtil.create("div", "info-msg");
  div.id = "infoBox";
  div.innerHTML = "Cargando rutas...";
  return div;
};
info.addTo(map);

async function loadRoutes() {
  const resp = await fetch("/api/routes");
  allData = await resp.json();
  document.getElementById("status").textContent = "Listo";
  document.getElementById("infoBox").innerHTML = "Elige sector y algoritmo, luego Play";
  updateBgRoutes();
  updateLegend();
  selectBestAlgo(0);
}

function updateBgRoutes() {
  for (const key of Object.keys(bgLines)) { map.removeLayer(bgLines[key]); delete bgLines[key]; }
  for (const [skey, route] of Object.entries(allData)) {
    const sid = parseInt(skey.split(":")[0]);
    const isActive = (sid === currentSector);
    bgLines[skey] = L.polyline(route.coords, {
      color: COLORS[sid],
      weight: isActive ? 4 : 2,
      opacity: isActive ? 0.6 : 0.25,
    }).addTo(map);
  }
}

function updateLegend() {
  let h = "<b>Rutas (" + (currentAlgo ? ALGO_NAMES[currentAlgo] : "---") + ")</b><br>";
  for (let s = 0; s < 5; s++) {
    const r = allData[s + ":" + (currentAlgo || "voraz")];
    if (r) {
      h += '<i style="background:' + COLORS[s] + '"></i> S' + s + ': ' + r.dist_km + 'km';
      if (s === currentSector) h += ' <b>&#9733;</b>';
      h += '<br>';
    }
  }
  h += '<hr style="border-color:#444;margin:4px 0">';
  h += '<i style="background:#e67e22"></i> Recorrido<br>';
  h += '<i style="background:#e74c3c"></i> Retorno dep&oacute;sito';
  document.getElementById("legendDiv").innerHTML = h;
}

function selectBestAlgo(sector) {
  currentAlgo = BEST_ALGO[sector];
  currentSector = sector;
  document.getElementById("algoSelect").value = currentAlgo;
  document.getElementById("sectorSelect").value = sector;
  resetAnim();
  updateBgRoutes();
  updateLegend();
}

function getCurrentRoute() {
  return allData[currentSector + ":" + currentAlgo];
}

function loadAnimation() {
  const route = getCurrentRoute();
  if (!route) return;
  document.getElementById("total").textContent = route.coords.length;
  cartMarker.setLatLng(route.coords[0]);
  document.getElementById("infoBox").innerHTML =
    ALGO_NAMES[currentAlgo] + " S" + currentSector + ": " +
    route.dist_km + "km, redund=" + route.redund;
}

function resetAnim() {
  if (animTimer) { clearInterval(animTimer); animTimer = null; }
  playing = false;
  document.getElementById("playBtn").textContent = "\u25B6 Play";
  idx = 0;
  trailLine.setLatLngs([]);
  returnLine.setLatLngs([]);
  loadAnimation();
  updateProgress();
  document.getElementById("status").textContent = "Reiniciado";
}

function updateProgress() { document.getElementById("progress").textContent = idx; }

function doReturnPath() {
  playing = false;
  document.getElementById("playBtn").textContent = "\u25B6 Play";
  if (animTimer) { clearInterval(animTimer); animTimer = null; }
  const route = getCurrentRoute();
  if (!route || !route.return_coords || route.return_coords.length < 2) {
    document.getElementById("status").textContent = "Completado";
    return;
  }
  document.getElementById("status").textContent = "Retornando al dep\u00f3sito...";
  returnLine.setLatLngs(route.return_coords);
  let ri = 0;
  const retTimer = setInterval(function() {
    if (ri < route.return_coords.length) {
      cartMarker.setLatLng(route.return_coords[ri]);
      trailLine.setLatLngs(route.coords.concat(route.return_coords.slice(0, ri + 1)));
      ri++;
    } else {
      clearInterval(retTimer);
      document.getElementById("status").textContent = "Completado";
    }
  }, Math.max(10, 80 / speed));
}

function stepAnimation() {
  const route = getCurrentRoute();
  if (!route) return;
  if (idx < route.coords.length - 1) {
    idx++;
    cartMarker.setLatLng(route.coords[idx]);
    trailLine.setLatLngs(route.coords.slice(0, idx + 1));
    updateProgress();
    document.getElementById("infoBox").innerHTML =
      ALGO_NAMES[currentAlgo] + " S" + currentSector + " \u2014 paso " + idx + "/" + route.coords.length;
  } else {
    document.getElementById("status").textContent = "Circuito completado";
    doReturnPath();
  }
}

function togglePlay() {
  const route = getCurrentRoute();
  if (!route) return;
  const btn = document.getElementById("playBtn");
  if (playing) {
    playing = false; btn.textContent = "\u25B6 Play";
    if (animTimer) { clearInterval(animTimer); animTimer = null; }
  } else {
    if (idx >= route.coords.length) resetAnim();
    playing = true; btn.textContent = "\u23F8 Pause";
    animTimer = setInterval(stepAnimation, Math.max(10, 80 / speed));
  }
}

document.getElementById("playBtn").addEventListener("click", togglePlay);
document.getElementById("resetBtn").addEventListener("click", resetAnim);
document.getElementById("sectorSelect").addEventListener("change", function() {
  selectBestAlgo(parseInt(this.value));
});
document.getElementById("algoSelect").addEventListener("change", function() {
  currentAlgo = this.value;
  resetAnim();
  updateBgRoutes();
  updateLegend();
});
document.getElementById("speedSlider").addEventListener("input", function() {
  speed = parseInt(this.value);
  document.getElementById("speedLabel").textContent = speed + "x";
  if (playing) { if (animTimer) clearInterval(animTimer); animTimer = setInterval(stepAnimation, Math.max(10, 80 / speed)); }
});

selectBestAlgo(0);
loadRoutes();
</script>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "/index.html":
            self._serve_html()
        elif path == "/api/routes":
            self._serve_json({f"{s}:{k}": {
                "coords": v["coords"], "return_coords": v["return_coords"],
                "dist_km": v["dist_km"], "serv_km": v["serv_km"],
                "redund": v["redund"], "extra": v["extra"],
            } for (s, k), v in all_routes.items()})
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'{"error":"not found"}')

    def _serve_html(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        page = (HTML
                .replace("__COLORS__", json.dumps({str(i): SECTOR_COLORS[i] for i in range(5)}))
                .replace("__ALGO_NAMES__", json.dumps(ALGO_NAMES))
                .replace("__SECTOR_NAMES__", json.dumps(SECTOR_NAMES))
                .replace("__BEST_ALGO__", json.dumps({str(k): v for k, v in best_algo.items()}))
                .replace("__DEPOT__", json.dumps(list(_node_ll(depot)))))
        self.wfile.write(page.encode("utf-8"))

    def _serve_json(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def log_message(self, format, *args):
        pass


def main():
    compute_all_routes()
    port = 8000
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    url = f"http://localhost:{port}"
    print(f"\n  Visor de rutas animadas: {url}")
    print(f"  Presiona Ctrl+C para detener.\n")
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido.")
        server.server_close()


if __name__ == "__main__":
    main()
