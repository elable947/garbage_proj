"""
Visor HTML interactivo de rutas DCPP con animacion de carrito.
Sector 2: recorrido animado con retorno al deposito via Dijkstra (scratch).

Uso: python -m src.visor_rutas
"""
import os, json, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import networkx as nx
from collections import defaultdict, Counter

from src._data import _load_data
from src.dcpp import _hierholzer, hungarian, dcpp
from src.dijkstra import build_adjacency, shortest_path as dijkstra_path
from shapely.wkt import loads as wkt_loads


def _parse_wkt(wkt):
    if not wkt or "LINESTRING" not in wkt:
        return []
    geom = wkt_loads(wkt)
    return [(lat, lon) for lon, lat in geom.coords]


def _node_ll(G, n):
    return (G.nodes[n]["y"], G.nodes[n]["x"])


def _route_to_coords(G, nodes, edge_lookup):
    coords = []
    for i in range(len(nodes) - 1):
        a, b = nodes[i], nodes[i + 1]
        if i == 0:
            coords.append(_node_ll(G, a))
        geom = edge_lookup.get((a, b))
        if geom:
            for pt in geom[1:]:
                coords.append(pt)
        else:
            coords.append(_node_ll(G, b))
    return coords


# ── Load data ─────────────────────────────────────────────────

G, Gu, depot, all_sector_edges = _load_data()

edge_lookup = {}
for u, v, k in G.edges(keys=True):
    geom = G.edges[u, v, k].get("geometry", "")
    pts = _parse_wkt(geom)
    if pts:
        edge_lookup[(u, v)] = pts

SECTOR_COLORS = {0: "#e74c3c", 1: "#3498db", 2: "#2ecc71", 3: "#f39c12", 4: "#9b59b6"}
SECTOR_NAMES = {0: "S0 NE", 1: "S1 S", 2: "S2 NW", 3: "S3 Centro", 4: "S4 SW"}

print("Ejecutando DCPP para 5 sectores...")
all_routes = {}
for s in range(5):
    r = dcpp(s)
    coords = _route_to_coords(G, r["route_nodes"], edge_lookup)
    r["coords"] = coords
    all_routes[s] = r
    print(f"  S{s}: {r['total_distance_m']/1000:.2f}km  {len(coords)} pts")

# ── Circuit and return for S2 ──────────────────────────────────

print("\nConstruyendo circuito sector 2...")
req = all_sector_edges[2]

indeg, outdeg = Counter(), Counter()
for u, v, k in req:
    outdeg[u] += 1
    indeg[v] += 1

sources, sinks = {}, {}
for n in set(list(indeg) + list(outdeg)):
    imb = outdeg[n] - indeg[n]
    if imb > 0: sources[n] = imb
    elif imb < 0: sinks[n] = -imb

src_list = [n for n, q in sources.items() for _ in range(q)]
snk_list = [n for n, q in sinks.items() for _ in range(q)]
m = len(src_list)

dist_cache = {}
for t in set(snk_list):
    dists, _ = nx.single_source_dijkstra(Gu, t, weight="length")
    dist_cache[t] = dists

cost_matrix = [[dist_cache[snk_list[i]].get(src_list[j], float("inf")) for j in range(m)] for i in range(m)]
_, assignment = hungarian(cost_matrix)

# ── Circuito Euleriano expandido ──────────────────────────────

adj = defaultdict(list)
for u, v, k in req:
    adj[u].append(v)
for i, j in enumerate(assignment):
    adj[snk_list[i]].append(src_list[j])

depot_dists, _ = nx.single_source_dijkstra(Gu, depot, weight="length")
circuit_start = min(adj, key=lambda n: depot_dists.get(n, float("inf")))
circuit_raw = _hierholzer(adj, circuit_start)

required_set = set()
required_undirected = set()
for u, v, k in req:
    required_set.add((u, v))
    required_undirected.add((min(u, v), max(u, v)))
Gu_penalty = Gu.copy()
for u_pen, v_pen in required_undirected:
    if Gu_penalty.has_edge(u_pen, v_pen):
        for key in Gu_penalty[u_pen][v_pen]:
            Gu_penalty[u_pen][v_pen][key]["length"] *= 100.0

circuit_expanded = [circuit_raw[0]]
for i in range(len(circuit_raw) - 1):
    a, b = circuit_raw[i], circuit_raw[i + 1]
    if (a, b) not in required_set:
        try:
            sp = nx.shortest_path(Gu_penalty, a, b, weight="length")
            circuit_expanded.extend(sp[1:])
        except nx.NetworkXNoPath:
            try:
                sp = nx.shortest_path(Gu, a, b, weight="length")
                circuit_expanded.extend(sp[1:])
            except nx.NetworkXNoPath:
                circuit_expanded.append(b)
    else:
        circuit_expanded.append(b)

circuit_coords = _route_to_coords(G, circuit_expanded, edge_lookup)
print(f"  Circuito raw: {len(circuit_raw)} nodos, expandido: {len(circuit_expanded)} nodos, coords: {len(circuit_coords)} pts")

print("Calculando retorno Dijkstra (scratch)...")
adj_dict = build_adjacency(G, weight="length")
end_node = circuit_raw[-1]
ret_path, ret_dist = dijkstra_path(adj_dict, end_node, depot)
if not ret_path:
    Gu_adj = build_adjacency(G.to_undirected(), weight="length")
    ret_path, ret_dist = dijkstra_path(Gu_adj, end_node, depot)
ret_coords = _route_to_coords(G, ret_path, edge_lookup)
print(f"  Retorno: {len(ret_coords)} pts, {ret_dist/1000:.2f} km")

# ── JSON data for JS ──────────────────────────────────────────

def routes_data(routes):
    d = {}
    for s, r in routes.items():
        d[str(s)] = {
            "coords": r["coords"],
            "dist_km": round(r["total_distance_m"] / 1000, 2),
            "serv_km": round(r["total_serviced_m"] / 1000, 2),
            "redund": round(r["redundancy"], 3),
        }
    return d

JS_ROUTES = json.dumps(routes_data(all_routes))
JS_COLORS = json.dumps({str(k): v for k, v in SECTOR_COLORS.items()})
JS_NAMES = json.dumps(SECTOR_NAMES)
JS_CIRCUIT = json.dumps(circuit_coords)
JS_RETURN = json.dumps(ret_coords)
RET_KM = round(ret_dist / 1000, 2)
S2_KM = round(all_routes[2]["total_distance_m"] / 1000, 2)
DEPOT_LAT, DEPOT_LON = _node_ll(G, depot)

# ── HTML template ─────────────────────────────────────────────

HTML_TPL = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Rutas DCPP - Chachapoyas</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:Segoe UI,sans-serif;background:#1a1a2e;color:#eee;display:flex;flex-direction:column;height:100vh}
#map{flex:1;width:100%}
#panel{background:#16213e;padding:12px 20px;display:flex;align-items:center;gap:16px;flex-wrap:wrap;border-top:2px solid #0f3460}
#panel button{background:#0f3460;color:#fff;border:none;padding:8px 18px;border-radius:6px;cursor:pointer;font-weight:bold;font-size:14px}
#panel button:hover{background:#1a4a8a}
#panel button:disabled{opacity:0.5;cursor:default}
#panel label{font-size:13px;display:flex;align-items:center;gap:6px}
#panel input[type=range]{width:80px;accent-color:#2ecc71}
#status{font-size:13px;color:#aaa;flex:1;text-align:right}
.legend{background:rgba(22,33,62,0.9);padding:10px 14px;border-radius:8px;font-size:12px;line-height:1.6;min-width:160px;color:#ddd}
.legend i{display:inline-block;width:12px;height:3px;border-radius:2px;margin-right:6px;vertical-align:middle}
.info-msg{background:rgba(22,33,62,0.9);padding:10px 14px;border-radius:8px;font-size:12px;margin-top:6px;color:#ddd}
</style>
</head>
<body>
<div id="map"></div>
<div id="panel">
  <button id="playBtn">&#9654; Play</button>
  <button id="resetBtn">&#8635; Reset</button>
  <label>Vel: <input type="range" id="speedSlider" min="1" max="20" value="5">
  <span id="speedLabel">5x</span></label>
  <div style="font-size:13px;color:#ccc">
    Progreso: <span id="progress">0</span>/<span id="total">TOT</span>
  </div>
  <div id="status">Listo</div>
</div>

<script>
// ── DATA ────────────────────────────────────────────────────
const ROUTES = JS_ROUTES_PLACEHOLDER;
const COLORS = JS_COLORS_PLACEHOLDER;
const NAMES = JS_NAMES_PLACEHOLDER;
const CIRCUIT = JS_CIRCUIT_PLACEHOLDER;
const RETURN_PATH = JS_RETURN_PLACEHOLDER;
const RET_KM = RET_KM_PLACEHOLDER;
const S2_KM = S2_KM_PLACEHOLDER;
const DEPOT = [DEPOT_LAT_PLACEHOLDER, DEPOT_LON_PLACEHOLDER];
document.getElementById("total").textContent = CIRCUIT.length;

// ── Map ──────────────────────────────────────────────────────
const map = L.map("map").setView([-6.23, -77.85], 13);
L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", {
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>',
  maxZoom: 19,
}).addTo(map);

// Sector routes
for (const [sk, r] of Object.entries(ROUTES)) {
  L.polyline(r.coords, {
    color: COLORS[sk], weight: 3, opacity: 0.5,
  }).addTo(map);
}

// Depot marker
const depotIcon = L.divIcon({
  html: '<div style="background:#fff;border:3px solid #000;border-radius:4px;width:16px;height:16px"></div>',
  iconSize: [16,16], iconAnchor: [8,8],
});
L.marker(DEPOT, {icon: depotIcon}).addTo(map)
  .bindTooltip("Deposito", {permanent:true, direction:"top", offset:[0,-12]});

// Cart marker
const cartIcon = L.divIcon({
  html: '<div style="background:#fff;border:2px solid #e67e22;border-radius:50%;width:14px;height:14px;box-shadow:0 0 8px #e67e22"></div>',
  iconSize: [14,14], iconAnchor: [7,7],
});
const cartMarker = L.marker(CIRCUIT[0], {icon: cartIcon, zIndexOffset:1000}).addTo(map);

// Trail polyline
const trailLine = L.polyline([], {
  color: "#e67e22", weight: 4, opacity: 0.9, dashArray: "6,4",
}).addTo(map);

const returnLine = L.polyline([], {
  color: "#e74c3c", weight: 5, opacity: 0.8, dashArray: "10,6",
}).addTo(map);

// ── Legend ──────────────────────────────────────────────────
const legend = L.control({position:"bottomright"});
legend.onAdd = function() {
  const div = L.DomUtil.create("div", "legend");
  let h = "<b>Rutas DCPP</b><br>";
  for (const [sk, nm] of Object.entries(NAMES)) {
    const r = ROUTES[sk];
    h += '<i style="background:' + COLORS[sk] + '"></i> ' + nm + ': ' + r.dist_km + 'km<br>';
  }
  h += '<hr style="border-color:#444;margin:4px 0">';
  h += '<i style="background:#e67e22"></i> Carrito (S2)<br>';
  h += '<i style="background:#e74c3c"></i> Retorno Dijkstra (' + RET_KM + 'km)';
  div.innerHTML = h;
  return div;
};
legend.addTo(map);

// ── Info box ────────────────────────────────────────────────
const info = L.control({position:"bottomleft"});
info.onAdd = function() {
  const div = L.DomUtil.create("div", "info-msg");
  div.id = "infoBox";
  div.innerHTML = "Presiona Play para iniciar animacion";
  return div;
};
info.addTo(map);

// ── Animation ───────────────────────────────────────────────
let playing = false;
let idx = 0;
let speed = 5;
let animTimer = null;

function updateProgress() {
  document.getElementById("progress").textContent = idx;
}

function updateCart() {
  if (idx < CIRCUIT.length) {
    cartMarker.setLatLng(CIRCUIT[idx]);
    trailLine.setLatLngs(CIRCUIT.slice(0, idx + 1));
  }
  updateProgress();
}

function doReturnPath() {
  playing = false;
  document.getElementById("playBtn").textContent = "\u25B6 Play";
  if (animTimer) { clearInterval(animTimer); animTimer = null; }
  document.getElementById("status").textContent = "Calculando retorno Dijkstra...";
  document.getElementById("infoBox").innerHTML = "Retorno al deposito via Dijkstra (scratch)...";

  returnLine.setLatLngs(RETURN_PATH);
  let ri = 0;
  const retTimer = setInterval(function() {
    if (ri < RETURN_PATH.length) {
      cartMarker.setLatLng(RETURN_PATH[ri]);
      trailLine.setLatLngs(CIRCUIT.concat(RETURN_PATH.slice(0, ri + 1)));
      ri++;
    } else {
      clearInterval(retTimer);
      document.getElementById("status").textContent = "Completado";
      document.getElementById("infoBox").innerHTML =
        "Ruta completada. Dist total: " + (S2_KM + RET_KM).toFixed(2) + " km";
    }
  }, Math.max(10, 80 / speed));
}

function stepAnimation() {
  if (idx < CIRCUIT.length - 1) {
    idx++;
    updateCart();
    document.getElementById("infoBox").innerHTML =
      "Recorriendo sector 2 ... paso " + idx + "/" + CIRCUIT.length;
  } else {
    document.getElementById("status").textContent = "Circuito completado";
    doReturnPath();
  }
}

function togglePlay() {
  const btn = document.getElementById("playBtn");
  if (playing) {
    playing = false;
    btn.textContent = "\u25B6 Play";
    if (animTimer) { clearInterval(animTimer); animTimer = null; }
  } else {
  if (idx >= CIRCUIT.length) {
    idx = 0;
    trailLine.setLatLngs([]);
    returnLine.setLatLngs([]);
    cartMarker.setLatLng(CIRCUIT[0]);
    updateProgress();
  }
    playing = true;
    btn.textContent = "\u23F8 Pause";
    const interval = Math.max(10, 80 / speed);
    animTimer = setInterval(stepAnimation, interval);
  }
}

function resetAnim() {
  if (animTimer) { clearInterval(animTimer); animTimer = null; }
  playing = false;
  document.getElementById("playBtn").textContent = "\u25B6 Play";
  idx = 0;
  trailLine.setLatLngs([]);
  returnLine.setLatLngs([]);
  cartMarker.setLatLng(CIRCUIT[0]);
  updateProgress();
  document.getElementById("status").textContent = "Reiniciado";
  document.getElementById("infoBox").innerHTML = "Presiona Play para iniciar animacion";
}

// ── Events ──────────────────────────────────────────────────
document.getElementById("playBtn").addEventListener("click", togglePlay);
document.getElementById("resetBtn").addEventListener("click", resetAnim);
document.getElementById("speedSlider").addEventListener("input", function() {
  speed = parseInt(this.value);
  document.getElementById("speedLabel").textContent = speed + "x";
  if (playing) {
    if (animTimer) { clearInterval(animTimer); }
    animTimer = setInterval(stepAnimation, Math.max(10, 80 / speed));
  }
});

updateCart();
</script>
</body>
</html>"""

# ── Inject JSON data ────────────────────────────────────────────

HTML = (HTML_TPL
    .replace("JS_ROUTES_PLACEHOLDER", JS_ROUTES)
    .replace("JS_COLORS_PLACEHOLDER", JS_COLORS)
    .replace("JS_NAMES_PLACEHOLDER", JS_NAMES)
    .replace("JS_CIRCUIT_PLACEHOLDER", JS_CIRCUIT)
    .replace("JS_RETURN_PLACEHOLDER", JS_RETURN)
    .replace("RET_KM_PLACEHOLDER", str(RET_KM))
    .replace("S2_KM_PLACEHOLDER", str(S2_KM))
    .replace("DEPOT_LAT_PLACEHOLDER", str(DEPOT_LAT))
    .replace("DEPOT_LON_PLACEHOLDER", str(DEPOT_LON))
    .replace("TOT", str(len(circuit_coords)))
)

# ── Save ─────────────────────────────────────────────────────────

out_path = os.path.join(os.path.dirname(__file__), "..", "outputs", "visor_rutas.html")
os.makedirs(os.path.dirname(out_path), exist_ok=True)
with open(out_path, "w", encoding="utf-8") as f:
    f.write(HTML)

print(f"\nVisor generado: {out_path}  ({len(HTML)} bytes)")
print("Abrelo en tu navegador para ver rutas y animacion.")
