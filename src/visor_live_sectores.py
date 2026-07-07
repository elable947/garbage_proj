#!/usr/bin/env python
"""
Visor interactivo en vivo de los sectores de Chachapoyas.
Carga grafo_chachapoyas_sectorizado.graphml y muestra cada sector
con su color asignado, permitiendo explorar nodos, aristas y rutas.

Uso: python src/visor_live_sectores.py
Luego abre http://localhost:8000 en el navegador.
"""
import json
import os
import sys
import webbrowser
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

import networkx as nx
from shapely import wkt
from shapely.geometry import LineString

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")

SECTOR_COLORS = ["#e74c3c", "#3498db", "#2ecc71", "#f39c12", "#9b59b6"]
SECTOR_NAMES = ["S0 - NE", "S1 - S", "S2 - NW", "S3 - Centro", "S4 - SW"]

G = None


def load_graph():
    global G
    path = os.path.join(DATA_DIR, "grafo_chachapoyas_sectorizado.graphml")
    if not os.path.exists(path):
        path = os.path.join(DATA_DIR, "grafo_chachapoyas_corregido.graphml")
    print(f"Cargando: {path}")
    G = nx.read_graphml(path, node_type=str)
    if not G.is_multigraph():
        G = nx.MultiDiGraph(G)
    for n in G.nodes:
        for k in ("x", "y"):
            try:
                G.nodes[n][k] = float(G.nodes[n][k])
            except (ValueError, TypeError, KeyError):
                G.nodes[n][k] = 0.0
        try:
            G.nodes[n]["sector"] = int(G.nodes[n].get("sector", -1))
        except (ValueError, TypeError):
            G.nodes[n]["sector"] = -1
    for u, v, k in G.edges(keys=True):
        try:
            G.edges[u, v, k]["length"] = float(G.edges[u, v, k].get("length", 0))
        except (ValueError, TypeError):
            G.edges[u, v, k]["length"] = 0.0
    print(f"Grafo: {G.number_of_nodes()} nodos, {G.number_of_edges()} aristas")


def graph_to_geojson():
    features = []
    for nid in G.nodes:
        nd = G.nodes[nid]
        s = nd.get("sector", -1)
        props = {"id": str(nid), "type": "node", "sector": s}
        if s >= 0:
            props["color"] = SECTOR_COLORS[s % len(SECTOR_COLORS)]
            props["sector_name"] = SECTOR_NAMES[s % len(SECTOR_NAMES)]
        else:
            props["color"] = "#888888"
            props["sector_name"] = "Excluido"
        features.append({
            "type": "Feature",
            "id": str(nid),
            "geometry": {"type": "Point", "coordinates": [nd.get("x", 0), nd.get("y", 0)]},
            "properties": props,
        })

    for u, v, key, ed in G.edges(keys=True, data=True):
        geom = ed.get("geometry")
        coords = None
        if geom is not None:
            if isinstance(geom, str):
                try:
                    from shapely import wkt
                    geom = wkt.loads(geom)
                except Exception:
                    geom = None
            if geom is not None:
                coords = list(geom.coords)
        if coords is None:
            ux = G.nodes[u].get("x", 0)
            uy = G.nodes[u].get("y", 0)
            vx = G.nodes[v].get("x", 0)
            vy = G.nodes[v].get("y", 0)
            coords = [(ux, uy), (vx, vy)]

        s = G.nodes[u].get("sector", -1)
        props = {
            "id": ed.get("edge_id", f"{u}->{v}"),
            "type": "edge",
            "u": str(u), "v": str(v), "key": key,
            "length": ed.get("length", 0),
            "oneway": bool(ed.get("oneway", False)),
            "sector": s,
        }
        if s >= 0:
            props["color"] = SECTOR_COLORS[s % len(SECTOR_COLORS)]
            props["sector_name"] = SECTOR_NAMES[s % len(SECTOR_NAMES)]
        else:
            props["color"] = "#888888"
            props["sector_name"] = "Excluido"

        features.append({
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": coords},
            "properties": props,
        })

    return {"features": features}


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Sectores - Chachapoyas</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:system-ui,sans-serif;background:#1a1a2e;color:#eee;display:flex;flex-direction:column;height:100vh}
#map{flex:1;width:100%}
#panel{background:#16213e;padding:10px 18px;display:flex;align-items:center;gap:14px;flex-wrap:wrap;border-top:2px solid #0f3460;font-size:13px}
#panel .legend{display:flex;gap:12px;flex-wrap:wrap}
#panel .legend-item{display:flex;align-items:center;gap:4px;cursor:pointer;padding:3px 6px;border-radius:4px;transition:.15s}
#panel .legend-item:hover{background:#0f3460}
#panel .legend-item .dot{width:14px;height:14px;border-radius:4px;display:inline-block}
#panel .legend-item .count{color:#888;font-size:11px}
#stats{color:#888;font-size:12px}
#stats span{color:#ddd;font-weight:bold}
.info-panel{position:fixed;right:12px;top:70px;z-index:1000;background:rgba(22,33,62,.95);border-radius:10px;padding:12px 16px;min-width:220px;backdrop-filter:blur(8px);border:1px solid #333;font-size:13px;display:none}
.info-panel.visible{display:block}
.info-panel h4{color:#1a6bb0;margin-bottom:6px}
.info-panel .row{display:flex;justify-content:space-between;padding:3px 0;color:#aaa}
.info-panel .row .label{color:#888}
.copy-btn{background:none;border:1px solid #555;color:#aaa;border-radius:4px;padding:2px 8px;cursor:pointer;font-size:11px;margin-left:4px}
.copy-btn:hover{background:#555;color:#fff}
</style>
</head>
<body>
<div id="map"></div>
<div id="panel">
  <div class="legend" id="legend"></div>
  <div id="stats">Nodos: <span id="nodeCount">0</span> | Aristas: <span id="edgeCount">0</span></div>
  <div style="color:#555;font-size:12px;margin-left:auto">Click para info</div>
</div>
<div class="info-panel" id="info-panel">
  <h4 id="info-title">Seleccionado</h4>
  <div id="info-body"></div>
</div>
<script>
const COLORS = __COLORS__;
const SNAMES = __SNAMES__;

const map = L.map("map", {zoomControl: true}).setView([-6.23, -77.87], 14);
L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", {
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>',
  maxZoom: 19,
}).addTo(map);

let geoData = null;
const nodeLayers = {};
const edgeLayers = {};
const toggleState = {};

function getColor(sector) {
  return COLORS[sector] || "#888";
}

function copyText(text) {
  navigator.clipboard.writeText(text).catch(() => {
    const ta = document.createElement("textarea");
    ta.value = text; document.body.appendChild(ta); ta.select();
    document.execCommand("copy"); document.body.removeChild(ta);
  });
}

function showInfo(title, bodyHtml) {
  document.getElementById("info-title").textContent = title;
  document.getElementById("info-body").innerHTML = bodyHtml;
  document.getElementById("info-panel").classList.add("visible");
}

function hideInfo() {
  document.getElementById("info-panel").classList.remove("visible");
}

function showAll() {
  for (const [id, layer] of Object.entries(nodeLayers)) {
    if (toggleState[layer._sector] !== false) map.addLayer(layer);
  }
  for (const [id, layer] of Object.entries(edgeLayers)) {
    if (toggleState[layer._sector] !== false) map.addLayer(layer);
  }
}

function toggleSector(sector) {
  toggleState[sector] = toggleState[sector] === false ? true : false;
  document.getElementById("toggle-" + sector).classList.toggle("off", toggleState[sector] === false);
  for (const layer of Object.values(nodeLayers)) {
    if (layer._sector === sector) {
      if (toggleState[sector] === false) map.removeLayer(layer);
      else map.addLayer(layer);
    }
  }
  for (const layer of Object.values(edgeLayers)) {
    if (layer._sector === sector) {
      if (toggleState[sector] === false) map.removeLayer(layer);
      else map.addLayer(layer);
    }
  }
}

function buildLegend(nodeCounts, edgeCounts) {
  const legend = document.getElementById("legend");
  let html = "";
  for (let s = 0; s < 5; s++) {
    const off = toggleState[s] === false;
    html += `<div class="legend-item" id="toggle-${s}" onclick="toggleSector(${s})" style="${off ? 'opacity:0.4' : ''}">`;
    html += `<span class="dot" style="background:${COLORS[s]}"></span>`;
    html += ` ${SNAMES[s]} <span class="count">(${nodeCounts[s]}n / ${(edgeCounts[s]/1000).toFixed(1)}km)</span></div>`;
  }
  legend.innerHTML = html;
}

async function loadData() {
  const resp = await fetch("/api/sectors");
  geoData = await resp.json();
  renderGraph(geoData);
}

function renderGraph(data) {
  const nodeCounts = [0,0,0,0,0];
  const edgeCounts = [0,0,0,0,0];

  for (const f of data.features) {
    if (f.properties.type === "node") {
      const s = f.properties.sector;
      const latlng = [f.geometry.coordinates[1], f.geometry.coordinates[0]];
      if (s >= 0 && s < 5) nodeCounts[s]++;
      const m = L.circleMarker(latlng, {
        radius: s >= 0 && s < 5 ? 6 : 4,
        color: getColor(s),
        fillColor: getColor(s),
        fillOpacity: 0.7,
        weight: s >= 0 && s < 5 ? 2 : 1,
        opacity: 0.8,
      }).addTo(map);
      m._nodeId = f.id;
      m._sector = s;
      m.on("click", function(e) {
        L.DomEvent.stopPropagation(e);
        const p = f.properties;
        let h = `<div class="row"><span class="label">ID</span><span>${p.id.substring(0,10)}...</span><button class="copy-btn" onclick="copyText('${p.id}')">Copiar</button></div>`;
        h += `<div class="row"><span class="label">Sector</span><span>${p.sector_name}</span></div>`;
        h += `<div class="row"><span class="label">Lat</span><span>${latlng[0].toFixed(6)}</span></div>`;
        h += `<div class="row"><span class="label">Lng</span><span>${latlng[1].toFixed(6)}</span></div>`;
        showInfo("Nodo", h);
      });
      nodeLayers[f.id] = m;
    } else if (f.properties.type === "edge") {
      const s = f.properties.sector;
      if (s >= 0 && s < 5) edgeCounts[s] += f.properties.length;
      const coords = f.geometry.coordinates.map(c => [c[1], c[0]]);
      const pl = L.polyline(coords, {
        color: getColor(s),
        weight: s >= 0 && s < 5 ? 3 : 1.5,
        opacity: s >= 0 && s < 5 ? 0.85 : 0.4,
      }).addTo(map);
      pl._edgeId = f.properties.id;
      pl._sector = s;
      pl.on("click", function(e) {
        L.DomEvent.stopPropagation(e);
        const p = f.properties;
        let dir = p.oneway ? "Ida (u\u2192v)" : "Doble sentido";
        let h = `<div class="row"><span class="label">ID</span><span>${p.id.substring(0,10)}...</span><button class="copy-btn" onclick="copyText('${p.id}')">Copiar</button></div>`;
        h += `<div class="row"><span class="label">Sector</span><span>${p.sector_name}</span></div>`;
        h += `<div class="row"><span class="label">Longitud</span><span>${p.length.toFixed(1)} m</span></div>`;
        h += `<div class="row"><span class="label">Direcci\u00f3n</span><span>${dir}</span></div>`;
        h += `<div class="row"><span class="label">Origen (u)</span><span>${p.u.substring(0,10)}...</span><button class="copy-btn" onclick="copyText('${p.u}')">Copiar</button></div>`;
        h += `<div class="row"><span class="label">Destino (v)</span><span>${p.v.substring(0,10)}...</span><button class="copy-btn" onclick="copyText('${p.v}')">Copiar</button></div>`;
        showInfo("Arista", h);
      });
      edgeLayers[f.properties.id] = pl;
    }
  }

  document.getElementById("nodeCount").textContent = Object.keys(nodeLayers).length;
  document.getElementById("edgeCount").textContent = Object.keys(edgeLayers).length;
  buildLegend(nodeCounts, edgeCounts);
}

loadData();
map.on("click", hideInfo);
</script>
</body>
</html>"""


def _get_html():
    colors = json.dumps({str(i): SECTOR_COLORS[i] for i in range(5)})
    snames = json.dumps({str(i): SECTOR_NAMES[i] for i in range(5)})
    return (HTML_TEMPLATE
            .replace("__COLORS__", colors)
            .replace("__SNAMES__", snames))


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(_get_html().encode("utf-8"))
        elif path == "/api/sectors":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            gj = json.dumps(graph_to_geojson())
            self.wfile.write(gj.encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'{"error": "not found"}')

    def log_message(self, format, *args):
        print(f"  {args[0]} {args[1]} {args[2]}")


def main():
    load_graph()
    port = 8000
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    url = f"http://localhost:{port}"
    print(f"\n  Visor de sectores: {url}")
    print(f"  Presiona Ctrl+C para detener el servidor.\n")
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido.")
        server.server_close()


if __name__ == "__main__":
    main()
