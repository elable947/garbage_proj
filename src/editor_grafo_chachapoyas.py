#!/usr/bin/env python
import json
import uuid
import os
import sys
import webbrowser
import traceback
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

import osmnx as ox
import networkx as nx
from shapely.geometry import LineString, Point
import pyproj

G = None
G_original = None
edge_id_map = {}
deleted_nodes = {}
deleted_edges = {}
geod = pyproj.Geod(ellps="WGS84")
modified = False


def _smart_id(val):
    try:
        return int(val)
    except (ValueError, TypeError):
        return str(val)


def load_graphs():
    global G, G_original
    original_path = "data/grafo_chachapoyas_original.graphml"
    corrected_path = "data/grafo_chachapoyas_corregido.graphml"

    if not os.path.exists(original_path):
        print(f"No se encuentra {original_path}. Ejecute grafo_chachapoyas.py primero")
        sys.exit(1)

    print("Cargando grafo original...")
    G_original = ox.load_graphml(original_path)

    if os.path.exists(corrected_path):
        try:
            sz = os.path.getsize(corrected_path)
            if sz == 0:
                raise ValueError("archivo vacio")
            print("Cargando grafo corregido...")
            G = nx.read_graphml(corrected_path, node_type=_smart_id)
            if not G.is_multigraph():
                G = nx.MultiDiGraph(G)
            # Make a safety backup of the corrected file
            import shutil
            os.makedirs("backups", exist_ok=True)
            shutil.copy2(corrected_path, "backups/grafo_chachapoyas_corregido.graphml.bak")
        except Exception as e:
            print(f"Error al cargar grafo corregido: {e}. Usando copia del original.")
            G = G_original.copy()
    else:
        print("Creando copia editable del grafo original...")
        G = G_original.copy()

    # Normalize all node IDs to strings for consistent handling
    mapping = {n: str(n) for n in G.nodes()}
    nx.relabel_nodes(G, mapping, copy=False)
    mapping2 = {n: str(n) for n in G_original.nodes()}
    nx.relabel_nodes(G_original, mapping2, copy=False)

    for n in G.nodes:
        _normalize_attrs(G.nodes[n])
    for n in G_original.nodes:
        _normalize_attrs(G_original.nodes[n])
    _ensure_edge_ids()
    _ensure_edge_geometries()
    print(f"Grafo listo: {G.number_of_nodes()} nodos, {G.number_of_edges()} aristas")


def _ensure_edge_ids():
    global edge_id_map
    edge_id_map = {}
    for u, v, key, data in G.edges(keys=True, data=True):
        if "edge_id" not in data:
            data["edge_id"] = str(uuid.uuid4())
        edge_id_map[data["edge_id"]] = (str(u), str(v), key)


def _recalculate_length(geom):
    if geom is None or len(geom.coords) < 2:
        return 0.0
    try:
        dist = geod.geometry_length(geom)
        return round(dist, 2)
    except Exception:
        try:
            coords = list(geom.coords)
            total = 0.0
            for i in range(len(coords) - 1):
                _, _, d = geod.inv(coords[i][0], coords[i][1], coords[i + 1][0], coords[i + 1][1])
                total += d
            return round(total, 2)
        except Exception:
            return 0.0


def _get_edge_geom(u, v, data):
    if "geometry" in data and data["geometry"] is not None:
        return data["geometry"]
    ux = G.nodes[u].get("x", 0)
    uy = G.nodes[u].get("y", 0)
    vx = G.nodes[v].get("x", 0)
    vy = G.nodes[v].get("y", 0)
    return LineString([(ux, uy), (vx, vy)])


def graph_to_geojson():
    features = []
    for node_id in G.nodes:
        nd = G.nodes[node_id]
        features.append({
            "type": "Feature",
            "id": str(node_id),
            "geometry": {"type": "Point", "coordinates": [nd.get("x", 0), nd.get("y", 0)]},
            "properties": {"id": str(node_id), "type": "node"},
        })

    for u, v, key, ed in G.edges(keys=True, data=True):
        geom = _get_edge_geom(u, v, ed)
        features.append({
            "type": "Feature",
            "id": ed.get("edge_id", ""),
            "geometry": {"type": "LineString", "coordinates": list(geom.coords)},
            "properties": {
                "id": ed.get("edge_id", ""),
                "u": str(u),
                "v": str(v),
                "key": key,
                "length": ed.get("length", _recalculate_length(geom)),
                "oneway": bool(ed.get("oneway", False)),
                "reversed": bool(ed.get("reversed", False)),
                "type": "edge",
            },
        })

    trash = []
    for nid, nd in deleted_nodes.items():
        trash.append({
            "type": "Feature",
            "id": str(nid),
            "geometry": {"type": "Point", "coordinates": [nd.get("x", 0), nd.get("y", 0)]},
            "properties": {"id": str(nid), "type": "deleted_node"},
        })
    for eid, ed in deleted_edges.items():
        geom = ed.get("geometry")
        if geom is None:
            continue
        trash.append({
            "type": "Feature",
            "id": eid,
            "geometry": {"type": "LineString", "coordinates": list(geom.coords)},
            "properties": {
                "id": eid,
                "type": "deleted_edge",
                "u": str(ed.get("u", "")),
                "v": str(ed.get("v", "")),
            },
        })

    return {"features": features, "trash": trash}


# ─── API Handlers ───────────────────────────────────────────────────────────

def _json_error(msg, status=400):
    return {"error": msg}, status


def api_get_graph():
    return graph_to_geojson(), 200


def api_get_edge_data(edge_id):
    if edge_id not in edge_id_map:
        return _json_error("arista no encontrada", 404)
    u, v, key = edge_id_map[edge_id]
    if not G.has_edge(u, v, key):
        del edge_id_map[edge_id]
        return _json_error("arista no encontrada", 404)
    ed = G.edges[u, v, key]
    geom = _get_edge_geom(u, v, ed)
    return {
        "id": edge_id,
        "u": str(u), "v": str(v), "key": key,
        "geometry": list(geom.coords),
        "length": ed.get("length", _recalculate_length(geom)),
        "oneway": bool(ed.get("oneway", False)),
        "reversed": bool(ed.get("reversed", False)),
    }, 200


def api_split_edge(data):
    global modified
    lat = data.get("lat")
    lng = data.get("lng")
    edge_id = data.get("edge_id")
    if lat is None or lng is None or edge_id is None:
        return _json_error("lat, lng y edge_id requeridos")
    if edge_id not in edge_id_map:
        return _json_error("arista no encontrada", 404)
    u, v, key = edge_id_map[edge_id]
    # Create new node
    nid = str(uuid.uuid4())
    G.add_node(nid, x=lng, y=lat, street_count=0)
    # Get original edge geometry
    geom = G.edges[u, v, key].get("geometry") or _get_edge_geom(u, v, G.edges[u, v, key])
    oneway = G.edges[u, v, key].get("oneway", True)
    coords = list(geom.coords)
    pt = Point(lng, lat)
    # Find closest point on line to click
    closest = geom.interpolate(geom.project(pt))
    # Find segment index to insert
    best_idx = 1
    best_dist = float("inf")
    for i in range(len(coords) - 1):
        seg = LineString([coords[i], coords[i + 1]])
        d = seg.distance(closest)
        if d < best_dist:
            best_dist = d
            best_idx = i + 1
    # Insert the split point
    coords.insert(best_idx, (closest.x, closest.y))
    # Split coordinates
    left_coords = coords[:best_idx + 1]
    right_coords = coords[best_idx:]
    # Create left edge (u -> new_node)
    left_geom = LineString(left_coords)
    left_length = _recalculate_length(left_geom)
    left_eid = str(uuid.uuid4())
    left_key = max([k for (nu, nv, k) in G.edges(keys=True) if str(nu) == u and str(nv) == nid] or [-1]) + 1
    G.add_edge(u, nid, key=left_key, edge_id=left_eid, length=left_length, oneway=oneway, geometry=left_geom)
    edge_id_map[left_eid] = (str(u), str(nid), left_key)
    # Create right edge (new_node -> v)
    right_geom = LineString(right_coords)
    right_length = _recalculate_length(right_geom)
    right_eid = str(uuid.uuid4())
    right_key = max([k for (nu, nv, k) in G.edges(keys=True) if str(nu) == nid and str(nv) == v] or [-1]) + 1
    G.add_edge(nid, v, key=right_key, edge_id=right_eid, length=right_length, oneway=oneway, geometry=right_geom)
    edge_id_map[right_eid] = (str(nid), str(v), right_key)
    # Remove original edge
    del edge_id_map[edge_id]
    G.remove_edge(u, v, key)
    modified = True
    return {
        "node": {"id": nid, "lat": lat, "lng": lng},
        "edges": [
            {"id": left_eid, "u": str(u), "v": str(nid), "key": left_key,
             "length": left_length, "oneway": oneway, "geometry": list(left_geom.coords)},
            {"id": right_eid, "u": str(nid), "v": str(v), "key": right_key,
             "length": right_length, "oneway": oneway, "geometry": list(right_geom.coords)},
        ],
    }, 200


def api_create_node(data):
    global modified
    lat = data.get("lat")
    lng = data.get("lng")
    if lat is None or lng is None:
        return _json_error("lat y lng requeridos")
    nid = str(uuid.uuid4())
    G.add_node(nid, x=lng, y=lat, street_count=0)
    modified = True
    return {"id": nid, "lat": lat, "lng": lng}, 200


def api_move_node(node_id, data):
    global modified
    lat = data.get("lat")
    lng = data.get("lng")
    if node_id not in G.nodes:
        return _json_error("nodo no encontrado", 404)
    G.nodes[node_id]["y"] = lat
    G.nodes[node_id]["x"] = lng
    for u, v, key, ed in G.edges(keys=True, data=True):
        su, sv = str(u), str(v)
        if su == node_id or sv == node_id:
            geom = ed.get("geometry")
            if geom and len(geom.coords) > 2:
                # Preserve control points, only update endpoint
                coords = list(geom.coords)
                if su == node_id:
                    coords[0] = (lng, lat)
                if sv == node_id:
                    coords[-1] = (lng, lat)
                ed["geometry"] = LineString(coords)
            else:
                ed["geometry"] = _get_edge_geom(u, v, ed)
            ed["length"] = _recalculate_length(ed["geometry"])
    modified = True
    return {"ok": True}, 200


def api_delete_node(node_id):
    global modified
    if node_id not in G.nodes:
        return _json_error("nodo no encontrado", 404)
    nd = dict(G.nodes[node_id])
    nd["_source"] = "original" if node_id in G_original.nodes else "user"
    deleted_nodes[node_id] = nd
    to_remove = []
    for u, v, key, ed in G.edges(keys=True, data=True):
        su, sv = str(u), str(v)
        if su == node_id or sv == node_id:
            eid = ed.get("edge_id", "")
            to_remove.append((u, v, key, eid, ed))
    for u, v, key, eid, ed in to_remove:
        ed2 = dict(ed)
        ed2["u"] = u
        ed2["v"] = v
        src = "original"
        try:
            if G_original.has_edge(u, v, key):
                src = "original"
            else:
                src = "user"
        except Exception:
            src = "user"
        ed2["_source"] = src
        deleted_edges[eid] = ed2
        if eid in edge_id_map:
            del edge_id_map[eid]
        G.remove_edge(u, v, key)
    G.remove_node(node_id)
    modified = True
    return {"ok": True}, 200


def api_create_edge(data):
    global modified
    u = data.get("u")
    v = data.get("v")
    if u not in G.nodes or v not in G.nodes:
        return _json_error("nodo origen o destino no encontrado")
    if u == v:
        return _json_error("no se permiten aristas de un nodo a sí mismo")
    existing = [k for (nu, nv, k) in G.edges(keys=True) if str(nu) == u and str(nv) == v]
    key = max(existing) + 1 if existing else 0
    geom = LineString([
        (G.nodes[u]["x"], G.nodes[u]["y"]),
        (G.nodes[v]["x"], G.nodes[v]["y"]),
    ])
    length = _recalculate_length(geom)
    eid = str(uuid.uuid4())
    G.add_edge(u, v, key=key, edge_id=eid, length=length, oneway=True, geometry=geom)
    edge_id_map[eid] = (u, v, key)
    modified = True
    return {
        "id": eid,
        "u": u,
        "v": v,
        "key": key,
        "length": length,
        "oneway": True,
        "geometry": list(geom.coords),
    }, 200


def api_update_edge_geometry(edge_id, data):
    global modified
    if edge_id not in edge_id_map:
        return _json_error("arista no encontrada", 404)
    u, v, key = edge_id_map[edge_id]
    coords = data.get("coordinates")
    if not coords or len(coords) < 2:
        return _json_error("coordenadas inválidas")
    geom = LineString([(c[0], c[1]) for c in coords])
    length = _recalculate_length(geom)
    G.edges[u, v, key]["geometry"] = geom
    G.edges[u, v, key]["length"] = length
    modified = True
    return {"length": length}, 200


def api_update_edge(edge_id, data):
    global modified
    if edge_id not in edge_id_map:
        return _json_error("arista no encontrada", 404)
    u, v, key = edge_id_map[edge_id]
    if "oneway" in data:
        G.edges[u, v, key]["oneway"] = bool(data["oneway"])
    if "length" in data:
        val = float(data["length"])
        if val < 0 or val != val:
            return _json_error("longitud inválida")
        G.edges[u, v, key]["length"] = val
    modified = True
    return {"ok": True}, 200


def api_add_control_point(edge_id, data):
    global modified
    if edge_id not in edge_id_map:
        return _json_error("arista no encontrada", 404)
    u, v, key = edge_id_map[edge_id]
    lat = data.get("lat")
    lng = data.get("lng")
    if lat is None or lng is None:
        return _json_error("lat y lng requeridos")
    geom = G.edges[u, v, key].get("geometry") or _get_edge_geom(u, v, G.edges[u, v, key])
    coords = list(geom.coords)
    pt = Point(lng, lat)
    best = 1
    best_dist = float("inf")
    for i in range(len(coords) - 1):
        seg = LineString([coords[i], coords[i + 1]])
        d = seg.distance(pt)
        if d < best_dist:
            best_dist = d
            best = i + 1
    coords.insert(best, (lng, lat))
    new_geom = LineString(coords)
    G.edges[u, v, key]["geometry"] = new_geom
    G.edges[u, v, key]["length"] = _recalculate_length(new_geom)
    modified = True
    return {"coordinates": coords, "length": G.edges[u, v, key]["length"]}, 200


def api_set_edge_direction(edge_id, data):
    global modified
    if edge_id not in edge_id_map:
        return _json_error("arista no encontrada", 404)
    direction = data.get("direction")
    if direction not in ("ida", "vuelta", "doble"):
        return _json_error("direcci\u00f3n inv\u00e1lida: use ida, vuelta o doble")
    u, v, key = edge_id_map[edge_id]
    ed = G.edges[u, v, key]
    if direction == "ida":
        ed["oneway"] = True
        ed["reversed"] = False
    elif direction == "doble":
        ed["oneway"] = False
        ed["reversed"] = False
    elif direction == "vuelta":
        edata = dict(ed)
        geom = edata.get("geometry") or _get_edge_geom(u, v, edata)
        rev_geom = LineString(list(geom.coords)[::-1]) if geom else None
        all_attrs = {k: v for k, v in edata.items()
                     if k not in ("oneway", "reversed", "edge_id")}
        G.remove_edge(u, v, key)
        del edge_id_map[edge_id]
        existing = [k for (nu, nv, k) in G.edges(keys=True) if str(nu) == v and str(nv) == u]
        nkey = max(existing) + 1 if existing else 0
        G.add_edge(v, u, key=nkey, edge_id=edge_id, **all_attrs)
        if rev_geom:
            G.edges[v, u, nkey]["geometry"] = rev_geom
        G.edges[v, u, nkey]["oneway"] = True
        G.edges[v, u, nkey]["reversed"] = True
        edge_id_map[edge_id] = (str(v), str(u), nkey)
    modified = True
    new_u, new_v, new_key = edge_id_map[edge_id]
    new_ed = G.edges[new_u, new_v, new_key]
    new_geom = _get_edge_geom(new_u, new_v, new_ed)
    return {
        "id": edge_id,
        "u": str(new_u), "v": str(new_v), "key": new_key,
        "oneway": bool(new_ed.get("oneway", True)),
        "reversed": bool(new_ed.get("reversed", False)),
        "length": new_ed.get("length", _recalculate_length(new_geom)),
        "geometry": list(new_geom.coords),
    }, 200


def api_delete_edge(edge_id):
    global modified
    if edge_id not in edge_id_map:
        return _json_error("arista no encontrada", 404)
    u, v, key = edge_id_map[edge_id]
    ed = dict(G.edges[u, v, key])
    ed["u"] = u
    ed["v"] = v
    is_orig = False
    try:
        is_orig = G_original.has_edge(u, v, key)
    except Exception:
        pass
    ed["_source"] = "original" if is_orig else "user"
    deleted_edges[edge_id] = ed
    G.remove_edge(u, v, key)
    del edge_id_map[edge_id]
    modified = True
    return {"ok": True}, 200


def api_restore(data):
    global modified
    nids = data.get("node_ids", [])
    eids = data.get("edge_ids", [])
    restored_nodes = []
    restored_edges = []
    for nid in nids:
        if nid in deleted_nodes:
            nd = {k: v for k, v in deleted_nodes[nid].items() if k != "_source"}
            if nid not in G.nodes:
                G.add_node(nid, **nd)
                restored_nodes.append(nid)
            del deleted_nodes[nid]
    for eid in eids:
        if eid in deleted_edges:
            ed = deleted_edges[eid]
            u, v = ed.get("u"), ed.get("v")
            if u in G.nodes and v in G.nodes:
                existing = [k for (nu, nv, k) in G.edges(keys=True) if str(nu) == u and str(nv) == v]
                nkey = max(existing) + 1 if existing else 0
                edata = {k: v for k, v in ed.items() if k not in ("_source", "u", "v")}
                G.add_edge(u, v, key=nkey, **edata)
                if "edge_id" in edata:
                    edge_id_map[edata["edge_id"]] = (u, v, nkey)
                restored_edges.append(eid)
                del deleted_edges[eid]
    modified = True
    return {"restored_nodes": restored_nodes, "restored_edges": restored_edges}, 200


def api_get_trash():
    features = []
    for nid, nd in deleted_nodes.items():
        features.append({
            "type": "Feature",
            "id": str(nid),
            "geometry": {"type": "Point", "coordinates": [nd.get("x", 0), nd.get("y", 0)]},
            "properties": {"id": str(nid), "type": "deleted_node"},
        })
    for eid, ed in deleted_edges.items():
        geom = ed.get("geometry")
        if geom is None:
            continue
        features.append({
            "type": "Feature",
            "id": eid,
            "geometry": {"type": "LineString", "coordinates": list(geom.coords)},
            "properties": {
                "id": eid,
                "type": "deleted_edge",
                "u": str(ed.get("u", "")),
                "v": str(ed.get("v", "")),
                "length": ed.get("length", 0),
            },
        })
    return {"features": features}, 200


EXCLUDED_SIMPLIFY = {
    "af3202cd-3a9f-4a98-bdd0-28e64cac4795",
    "ebde992d-a470-4566-a4b9-3830567e8f78",
}


def _find_simplify_candidates():
    candidates = []
    for n in G.nodes:
        if n in EXCLUDED_SIMPLIFY:
            continue
        preds = set(G.predecessors(n))
        succs = set(G.successors(n))
        neighbors = preds | succs
        if len(neighbors) != 2:
            continue
        if n in neighbors:
            continue
        a, b = list(neighbors)
        candidates.append({
            "id": n,
            "pred": a,
            "succ": b,
            "lat": G.nodes[n].get("y", 0),
            "lng": G.nodes[n].get("x", 0),
        })
    return candidates


def api_simplify_candidates():
    return {"candidates": _find_simplify_candidates()}, 200


def _merge_edge_dir(G, edge_id_map, src, nid, dst):
    """Merge edges src->nid and nid->dst into a single edge src->dst.
       Returns the new edge_id or None if merge fails."""
    if not G.has_edge(src, nid) or not G.has_edge(nid, dst):
        return None
    src_keys = list(G[src][nid].keys())
    dst_keys = list(G[nid][dst].keys())
    if not src_keys or not dst_keys:
        return None
    src_key = src_keys[0]
    dst_key = dst_keys[0]
    src_data = G.edges[src, nid, src_key]
    dst_data = G.edges[nid, dst, dst_key]
    src_eid = src_data.get("edge_id", "")
    dst_eid = dst_data.get("edge_id", "")
    src_geom = _get_edge_geom(src, nid, src_data)
    dst_geom = _get_edge_geom(nid, dst, dst_data)
    combined_coords = list(src_geom.coords) + list(dst_geom.coords)[1:]
    combined_geom = LineString(combined_coords)
    combined_length = _recalculate_length(combined_geom)
    G.remove_edge(src, nid, src_key)
    G.remove_edge(nid, dst, dst_key)
    for eid in (src_eid, dst_eid):
        if eid in edge_id_map:
            del edge_id_map[eid]
    new_key = max([k for (nu, nv, k) in G.edges(keys=True) if str(nu) == src and str(nv) == dst] or [-1]) + 1
    new_eid = str(uuid.uuid4())
    oneway = not G.has_edge(dst, src)
    G.add_edge(src, dst, key=new_key, edge_id=new_eid,
               length=combined_length, oneway=oneway, geometry=combined_geom)
    edge_id_map[new_eid] = (src, dst, new_key)
    return new_eid


def api_simplify(data):
    global modified
    node_ids = data.get("node_ids", [])
    mode = data.get("mode", "bypass")
    if not node_ids:
        return _json_error("node_ids requeridos")
    if mode not in ("bypass", "delete"):
        return _json_error("modo invalido: use bypass o delete")

    results = {"processed": [], "errors": []}
    for nid in node_ids:
        if nid not in G.nodes:
            results["errors"].append({"node": nid, "error": "no encontrado"})
            continue
        if mode == "bypass":
            preds = set(G.predecessors(nid))
            succs = set(G.successors(nid))
            neighbors = preds | succs
            if len(neighbors) != 2:
                results["errors"].append({"node": nid, "error": "no tiene exactamente 2 vecinos"})
                continue
            a, b = list(neighbors)
            merged = False
            if a in preds and b in succs:
                if _merge_edge_dir(G, edge_id_map, a, nid, b):
                    merged = True
            if b in preds and a in succs:
                if _merge_edge_dir(G, edge_id_map, b, nid, a):
                    merged = True
            G.remove_node(nid)
            if not merged:
                results["errors"].append({"node": nid, "error": "no se pudo fusionar ninguna direccion"})
                continue
        else:
            for u, v, key, ed in G.edges(keys=True, data=True):
                if str(u) == nid or str(v) == nid:
                    eid = ed.get("edge_id", "")
                    if eid in edge_id_map:
                        del edge_id_map[eid]
            G.remove_node(nid)
        results["processed"].append(nid)
    modified = True
    return results, 200


def api_save():
    errors = validate_graph()
    if errors:
        return {"error": "validaci\u00f3n fallida", "details": errors}, 400
    path = "data/grafo_chachapoyas_corregido.graphml"
    # Convert in-memory types to GraphML-safe types before saving
    for n in G.nodes:
        for k, v in list(G.nodes[n].items()):
            if isinstance(v, bool):
                G.nodes[n][k] = str(v).lower()
            elif isinstance(v, (int, float)):
                G.nodes[n][k] = str(v)
            elif isinstance(v, LineString):
                G.nodes[n][k] = v.wkt
    for u, v, k, d in G.edges(keys=True, data=True):
        for ek, ev in list(d.items()):
            if isinstance(ev, bool):
                d[ek] = str(ev).lower()
            elif isinstance(ev, (int, float)):
                d[ek] = str(ev)
            elif isinstance(ev, LineString):
                d[ek] = ev.wkt
    # Ensure graph-level defaults are proper dicts (networkx writer bug)
    G.graph["node_default"] = {}
    G.graph["edge_default"] = {}
    # Atomic save via networkx directly (bypass osmnx's wrapper)
    tmp_path = path + ".tmp"
    try:
        nx.write_graphml(G, tmp_path)
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise
    # Convert back to proper types for continued editing
    for n in G.nodes:
        _normalize_attrs(G.nodes[n])
    for u, v, k, d in G.edges(keys=True, data=True):
        _normalize_attrs(d)
    global modified
    modified = False
    nn = G.number_of_nodes()
    ne = G.number_of_edges()
    return {"ok": True, "path": path, "nodes": nn, "edges": ne}, 200


def api_validate():
    errors = validate_graph()
    return {"valid": len(errors) == 0, "errors": errors}, 200


def _normalize_attrs(d):
    for key in list(d.keys()):
        val = d[key]
        if isinstance(val, str):
            if key == "length":
                try:
                    d[key] = float(val)
                except (ValueError, TypeError):
                    pass
            elif key in ("oneway", "reversed"):
                d[key] = val.lower() in ("true", "1", "yes")
            elif key in ("x", "y"):
                try:
                    d[key] = float(val)
                except (ValueError, TypeError):
                    pass
            elif key == "street_count":
                try:
                    d[key] = int(val)
                except (ValueError, TypeError):
                    pass
            elif key == "geometry":
                try:
                    from shapely import wkt
                    d[key] = wkt.loads(val)
                except Exception:
                    pass


def _ensure_edge_geometries():
    for u, v, k, d in G.edges(keys=True, data=True):
        _normalize_attrs(d)
        if "geometry" not in d or d["geometry"] is None:
            d["geometry"] = _get_edge_geom(u, v, d)
        if "length" not in d or d.get("length", 0) <= 0:
            d["length"] = _recalculate_length(d["geometry"])


def validate_graph():
    _ensure_edge_geometries()
    errors = []
    for n in G.nodes:
        d = G.nodes[n]
        if "x" not in d or "y" not in d:
            errors.append(f"Nodo {n} sin coordenadas")
    for u, v, k, d in G.edges(keys=True, data=True):
        geom = d.get("geometry")
        if geom is None:
            errors.append(f"Arista ({u}->{v}, k={k}) sin geometría")
        elif not geom.is_valid:
            errors.append(f"Arista ({u}->{v}, k={k}) geometría inválida")
        if d.get("length", 0) < 0:
            errors.append(f"Arista ({u}->{v}, k={k}) longitud negativa")
    return errors


# ─── HTTP Server ────────────────────────────────────────────────────────────

HTML = r"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Editor de Grafo Vial - Chachapoyas</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:system-ui,sans-serif;overflow:hidden;background:#1a1a1a;color:#fff}
#toolbar{position:fixed;top:10px;left:50%;transform:translateX(-50%);z-index:1000;display:flex;gap:6px;padding:8px 12px;background:rgba(30,30,30,.92);border-radius:10px;box-shadow:0 2px 12px rgba(0,0,0,.5);align-items:center;flex-wrap:wrap;backdrop-filter:blur(8px)}
#toolbar .sep{width:1px;height:28px;background:#444;margin:0 4px}
.tbtn{padding:6px 14px;border:1px solid #555;border-radius:6px;background:#2a2a2a;color:#ccc;cursor:pointer;font-size:13px;white-space:nowrap;transition:.15s}
.tbtn:hover{background:#3a3a3a;color:#fff}
.tbtn.active{background:#1a6bb0;border-color:#1a6bb0;color:#fff}
.tbtn.danger{color:#e74c3c}
.tbtn.danger.active{background:#c0392b;border-color:#c0392b;color:#fff}
.tbtn.success{background:#27ae60;border-color:#27ae60;color:#fff}
.tbtn.success:hover{background:#2ecc71}
#map{position:fixed;top:0;left:0;width:100%;height:100%}
#status{position:fixed;bottom:20px;left:50%;transform:translateX(-50%);z-index:1000;padding:6px 16px;background:rgba(0,0,0,.75);border-radius:8px;font-size:13px;color:#aaa;pointer-events:none;transition:.3s;backdrop-filter:blur(4px)}
#restore-modal{display:none;position:fixed;top:0;left:0;width:100%;height:100%;z-index:2000;background:rgba(0,0,0,.6);justify-content:center;align-items:center}
#restore-modal.open{display:flex}

#restore-modal .box{background:#222;border-radius:12px;padding:24px;max-width:600px;width:90%;max-height:80vh;overflow-y:auto}
#restore-modal h3{margin-bottom:16px;color:#fff}
#restore-modal .item{display:flex;align-items:center;gap:10px;padding:8px;border-bottom:1px solid #333;font-size:14px}
.copy-btn{background:none;border:1px solid #555;color:#aaa;border-radius:4px;padding:2px 8px;cursor:pointer;font-size:11px;margin-left:6px;transition:.15s}
.copy-btn:hover{background:#555;color:#fff}
.id-full{font-size:10px;color:#666;word-break:break-all;margin-top:2px;font-family:monospace}
#restore-modal .item input[type=checkbox]{width:16px;height:16px}
#restore-modal .actions{display:flex;gap:8px;margin-top:16px;justify-content:flex-end}
.ctx-menu{display:none;position:fixed;z-index:3000;background:#2a2a2a;border:1px solid #444;border-radius:8px;padding:4px;min-width:180px;box-shadow:0 4px 16px rgba(0,0,0,.5)}
.ctx-menu .item{padding:8px 14px;cursor:pointer;border-radius:4px;font-size:13px;color:#ccc}
.ctx-menu .item:hover{background:#1a6bb0;color:#fff}
@media(max-width:768px){#toolbar{top:5px;padding:6px 10px;gap:4px;font-size:12px}.tbtn{padding:5px 10px;font-size:12px}}
.leaflet-container{background:#1a1a1a}
.info-panel{position:fixed;right:10px;top:70px;z-index:1000;background:rgba(30,30,30,.9);border-radius:10px;padding:12px 16px;min-width:200px;backdrop-filter:blur(8px);border:1px solid #333;font-size:13px;display:none}
.info-panel.visible{display:block}
.info-panel h4{color:#1a6bb0;margin-bottom:6px}
.info-panel .row{display:flex;justify-content:space-between;padding:3px 0;color:#aaa}
.info-panel .row .label{color:#888}
.node-marker{background:#4a90d9;border:2px solid #fff;border-radius:50%;opacity:.9}
.node-marker:hover{opacity:1;z-index:1000!important}
.node-marker.dragging{background:#e67e22}
.edge-line{stroke:#4a90d9;stroke-width:3;opacity:.8}
.edge-line:hover{opacity:1;stroke:#6ab0f9;stroke-width:4}
.edge-line.selected{stroke:#e67e22;stroke-width:4}
.edge-line.temp{stroke:#e74c3c;stroke-width:2;stroke-dasharray:8,8}
.cp-marker{background:#e74c3c;border:2px solid #fff;border-radius:50%;opacity:.85}
.cp-marker:hover{opacity:1}
.cp-marker.dragging{background:#f39c12}
.cp-marker-div{background:#e74c3c;border:2px solid #fff;border-radius:50%;width:12px!important;height:12px!important;cursor:grab}
.cp-marker-div:active{cursor:grabbing}
.dir-panel{display:none;position:fixed;bottom:80px;left:50%;transform:translateX(-50%);z-index:2000;background:rgba(30,30,30,.95);border-radius:10px;padding:14px 18px;backdrop-filter:blur(8px);border:1px solid #444;text-align:center;min-width:260px}
.dir-panel.visible{display:block}
.dir-panel h4{margin-bottom:8px;color:#1a6bb0;font-size:14px}
.dir-edge-info{font-size:12px;color:#aaa;margin-bottom:10px}
.dir-buttons{display:flex;gap:8px;justify-content:center}
.dir-btn{padding:8px 18px;font-size:13px}
.dir-btn.active-dir{background:#1a6bb0;border-color:#1a6bb0;color:#fff}
.edge-arrow-marker{background:none!important;border:none!important}
</style>
</head>
<body>
<div id="toolbar">
<button class="tbtn active" data-tool="select">Seleccionar</button>
<button class="tbtn" data-tool="create-node">Crear Nodo</button>
<button class="tbtn" data-tool="create-edge">Crear Arista</button>
<button class="tbtn danger" data-tool="delete">Eliminar</button>
<button class="tbtn" data-tool="restore">Restaurar</button>
<button class="tbtn" data-tool="simplify">Simplificar</button>
<button class="tbtn" data-tool="dir">Direcciones</button>
<div class="sep"></div>
<button class="tbtn" id="btn-validate">Validar</button>
<button class="tbtn success" id="btn-save">Guardar Cambios</button>
</div>
<div id="map"></div>
<div id="status">Listo</div>
<div id="restore-modal"><div class="box">
<h3>Restaurar Elementos Eliminados</h3>
<div id="restore-items"></div>
<div class="actions">
<button class="tbtn" id="restore-cancel">Cancelar</button>
<button class="tbtn success" id="restore-confirm">Restaurar Seleccionados</button>
</div>
</div></div>
<div class="ctx-menu" id="ctx-menu">
<div class="item" data-action="add-cp">Agregar Punto de Control</div>
<div class="item" data-action="toggle-oneway">Cambiar Sentido (one-way)</div>
</div>
<div class="info-panel" id="info-panel">
<h4 id="info-title">Seleccionado</h4>
<div id="info-body"></div>
</div>
<div class="dir-panel" id="dir-panel">
<h4>Cambiar Dirección</h4>
<div id="dir-edge-info" class="dir-edge-info"></div>
<div class="dir-buttons">
<button class="tbtn dir-btn" data-dir="ida">Ida</button>
<button class="tbtn dir-btn" data-dir="vuelta">Vuelta</button>
<button class="tbtn dir-btn" data-dir="doble">Doble Sentido</button>
</div>
</div>
<script>
const map = L.map('map', {zoomControl: true, attributionControl: false}).setView([-6.23, -77.87], 14);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
maxZoom: 19, attribution: '&copy; OpenStreetMap'
}).addTo(map);

let state = {
tool: 'select',
nodes: {},
edges: {},
nodeLayers: {},
edgeLayers: {},
cpLayers: {},
arrowLayers: {},
selectedEdgeId: null,
selectedNodeId: null,
edgeSource: null,
tempLine: null,
trash: [],
simplifyCandidates: []
};

function setStatus(msg, isError) {
document.getElementById('status').textContent = msg;
document.getElementById('status').style.color = isError ? '#e74c3c' : '#aaa';
}

async function api(method, path, body) {
const opts = {method, headers: {'Content-Type': 'application/json'}};
if (body) opts.body = JSON.stringify(body);
const r = await fetch(path, opts);
return r.json();
}

async function loadGraph() {
const data = await api('GET', '/api/graph');
renderGraph(data);
}

function renderGraph(data) {
// Clear existing
Object.values(state.nodeLayers).forEach(l => map.removeLayer(l));
Object.values(state.edgeLayers).forEach(l => map.removeLayer(l));
Object.values(state.cpLayers).forEach(l => map.removeLayer(l));
hideEdgeArrows();
state.nodeLayers = {};
state.edgeLayers = {};
state.cpLayers = {};
state.nodes = {};
state.edges = {};
state.trash = data.trash || [];

for (const f of data.features) {
if (f.properties.type === 'node') addNodeToMap(f);
else if (f.properties.type === 'edge') addEdgeToMap(f);
}
}

function addNodeToMap(f) {
const id = f.properties.id;
const coords = f.geometry.coordinates;
const latlng = [coords[1], coords[0]];
const m = L.circleMarker(latlng, {
radius: 7, color: '#4a90d9', fillColor: '#4a90d9', fillOpacity: 0.9,
weight: 2, opacity: 1
}).addTo(map);
m._nodeId = id;
m.on('click', e => onNodeClick(id, m, e));
m.on('dblclick', e => onNodeDblClick(id, m, e));
m.on('dragend', e => onNodeDragEnd(id, m));
state.nodes[id] = {id, lat: latlng[0], lng: latlng[1], marker: m};
state.nodeLayers[id] = m;
}

function addEdgeToMap(f) {
const id = f.properties.id;
const coords = f.geometry.coordinates.map(c => [c[1], c[0]]);
const oneway = f.properties.oneway;
const opts = {
color: oneway ? '#4a90d9' : '#6ab0f9',
weight: 3, opacity: 0.85
};
const pl = L.polyline(coords, opts).addTo(map);
pl._edgeId = id;
pl._edgeData = f.properties;
pl._realWeight = 3;
// Wider invisible layer for easier clicking
const hitOpts = {
color: oneway ? '#4a90d9' : '#6ab0f9',
weight: 10, opacity: 0, interactive: true
};
const hitPl = L.polyline(coords, hitOpts).addTo(map);
hitPl._edgeId = id;
hitPl._edgeData = f.properties;
hitPl._realWeight = 10;
hitPl.on('click', e => { L.DomEvent.stopPropagation(e); L.DomEvent.preventDefault(e); onEdgeClick(id, hitPl, e); });
hitPl.on('dblclick', e => { L.DomEvent.stopPropagation(e); L.DomEvent.preventDefault(e); onEdgeDblClick(id, hitPl, e); });
hitPl.on('contextmenu', e => onEdgeContextMenu(id, hitPl, e));
pl._hitPl = hitPl;
hitPl._visPl = pl;
state.edges[id] = {id, polyline: hitPl, visiblePolyline: pl, data: f.properties, oneway, reversed: f.properties.reversed === true};
state.edgeLayers[id] = hitPl;
}

function showControlPoints(edgeId) {
hideControlPoints();
const e = state.edges[edgeId];
if (!e) return;
const latlngs = e.polyline.getLatLngs();
const cps = [];
for (let i = 1; i < latlngs.length - 1; i++) {
const cp = L.marker(latlngs[i], {
draggable: true,
icon: L.divIcon({
className: 'cp-marker-div',
iconSize: [12, 12],
iconAnchor: [6, 6]
})
}).addTo(map);
cp._edgeId = edgeId;
cp._index = i;
cp.on('drag', e2 => onCpDrag(edgeId, i, cp, e2));
cp.on('dragend', e2 => onCpDragEnd(edgeId, cp));
cps.push(cp);
}
state.cpLayers[edgeId] = cps;
}

function hideControlPoints() {
for (const eid of Object.keys(state.cpLayers)) {
state.cpLayers[eid].forEach(cp => map.removeLayer(cp));
}
state.cpLayers = {};
}

function hideInfo() {
document.getElementById('info-panel').classList.remove('visible');
}

function showNodeInfo(nodeId) {
const n = state.nodes[nodeId];
if (!n) return;
document.getElementById('info-title').textContent = 'Nodo';
document.getElementById('info-body').innerHTML =
`<div class="row"><span class="label">ID</span><span>${nodeId.substring(0, 8)}...</span><button class="copy-btn" onclick="copyId('${nodeId}')">Copiar ID</button></div>
<div class="id-full">${nodeId}</div>
<div class="row"><span class="label">Lat</span><span>${n.lat.toFixed(6)}</span></div>
<div class="row"><span class="label">Lng</span><span>${n.lng.toFixed(6)}</span></div>`;
document.getElementById('info-panel').classList.add('visible');
}

function showEdgeInfo(edgeId) {
const e = state.edges[edgeId];
if (!e) return;
const d = e.data;
let dirLabel = 'Doble Sentido';
if (d.oneway) {
dirLabel = d.reversed ? 'Vuelta (v\u2192u)' : 'Ida (u\u2192v)';
}
document.getElementById('info-title').textContent = 'Arista';
document.getElementById('info-body').innerHTML =
`<div class="row"><span class="label">Arista ID</span><span>${edgeId.substring(0, 8)}...</span><button class="copy-btn" onclick="copyId('${edgeId}')">Copiar ID</button></div>
<div class="id-full">${edgeId}</div>
<div class="row"><span class="label">Origen (u)</span><span>${d.u.substring(0, 8)}...</span><button class="copy-btn" onclick="copyId('${d.u}')">Copiar</button></div>
<div class="id-full">${d.u}</div>
<div class="row"><span class="label">Destino (v)</span><span>${d.v.substring(0, 8)}...</span><button class="copy-btn" onclick="copyId('${d.v}')">Copiar</button></div>
<div class="id-full">${d.v}</div>
<div class="row"><span class="label">Longitud</span><span>${d.length.toFixed(2)} m</span></div>
<div class="row"><span class="label">Direcci\u00f3n</span><span>${dirLabel}</span></div>`;
document.getElementById('info-panel').classList.add('visible');
}

function copyId(text) {
navigator.clipboard.writeText(text).then(() => {
setStatus('ID copiado: ' + text.substring(0, 12) + '...');
}).catch(() => {
// Fallback for non-HTTPS
const ta = document.createElement('textarea');
ta.value = text;
document.body.appendChild(ta);
ta.select();
document.execCommand('copy');
document.body.removeChild(ta);
setStatus('ID copiado: ' + text.substring(0, 12) + '...');
});
}

function setTool(tool) {
if (tool === 'dir' && state.tool !== 'dir') {
showEdgeArrows();
} else if (state.tool === 'dir' && tool !== 'dir') {
hideEdgeArrows();
}
if (state.tool === 'simplify' && tool !== 'simplify') {
unhighlightSimplifyCandidates();
}
if (tool === 'simplify' && state.tool !== 'simplify') {
highlightSimplifyCandidates();
}
state.tool = tool;
document.querySelectorAll('.tbtn[data-tool]').forEach(b => {
b.classList.toggle('active', b.dataset.tool === tool);
});
hideControlPoints();
hideDirPanel();
if (state.selectedEdgeId) {
const old = state.edges[state.selectedEdgeId];
if (old) old.polyline._visPl.setStyle({color: old.data.oneway ? '#4a90d9' : '#6ab0f9', weight: 3});
            state.selectedEdgeId = null;
}
state.selectedNodeId = null;
state.edgeSource = null;
if (state.tempLine) { map.removeLayer(state.tempLine); state.tempLine = null; }
map.getContainer().style.cursor = tool === 'create-node' ? 'crosshair' : (tool === 'create-edge' ? 'pointer' : '');
Object.values(state.nodeLayers).forEach(m => {
if (tool === 'delete' || tool === 'simplify') m.dragging.disable();
else m.dragging.enable();
});
}

// ─── Direction Panel ────────────────────────────────────────────────────────

function hideDirPanel() {
document.getElementById('dir-panel').classList.remove('visible');
state._dirEdgeId = null;
}

function showDirPanel(edgeId) {
const e = state.edges[edgeId];
if (!e) return;
state._dirEdgeId = edgeId;
const d = e.data;
const oneway = d.oneway;
let dir = 'doble';
if (oneway) {
dir = d.reversed === true || d.reversed === 'true' ? 'vuelta' : 'ida';
}
 document.getElementById('dir-edge-info').innerHTML =
`<div style="font-size:11px;color:#666;margin-bottom:4px;word-break:break-all">ID: ${edgeId}</div>
<div>${d.u.substring(0, 8)}... \u2192 ${d.v.substring(0, 8)}... (${d.length.toFixed(1)}m)</div>
<div style="font-size:10px;color:#555;word-break:break-all;margin-top:2px">u: ${d.u}</div>
<div style="font-size:10px;color:#555;word-break:break-all">v: ${d.v}</div>`;
document.querySelectorAll('.dir-btn').forEach(btn => {
btn.classList.toggle('active-dir', btn.dataset.dir === dir);
});
document.getElementById('dir-panel').classList.add('visible');
}

async function onDirButtonClick(dir) {
const edgeId = state._dirEdgeId;
if (!edgeId) return;
const r = await api('POST', `/api/edge/${edgeId}/direction`, {direction: dir});
if (r.error) { setStatus(r.error, true); return; }
// Remove old edge from map, re-add with updated data
const e = state.edges[edgeId];
if (e) {
map.removeLayer(e.polyline);
if (e.visiblePolyline) map.removeLayer(e.visiblePolyline);
}
delete state.edgeLayers[edgeId];
delete state.edges[edgeId];
addEdgeToMap({
type: 'Feature',
geometry: {type: 'LineString', coordinates: r.geometry},
properties: {id: r.id, u: r.u, v: r.v, key: r.key, length: r.length, oneway: r.oneway, reversed: r.reversed, type: 'edge'}
});
// Refresh arrow for this edge
refreshEdgeArrow(edgeId);
// Re-show panel with updated info
showDirPanel(edgeId);
setStatus(`Dirección cambiada a: ${dir === 'ida' ? 'Ida' : dir === 'vuelta' ? 'Vuelta' : 'Doble Sentido'}`);
}

document.querySelectorAll('.dir-btn').forEach(btn => {
btn.addEventListener('click', () => onDirButtonClick(btn.dataset.dir));
});

// ─── Direction Arrows ─────────────────────────────────────────────────────

function getEdgeMidpoint(latlngs) {
let total = 0;
const segs = [];
for (let i = 0; i < latlngs.length - 1; i++) {
const d = latlngs[i].distanceTo(latlngs[i + 1]);
segs.push(d);
total += d;
}
const half = total / 2;
let acc = 0;
for (let i = 0; i < segs.length; i++) {
if (acc + segs[i] >= half) {
const f = (half - acc) / segs[i];
return {
pt: L.latLng(latlngs[i].lat + (latlngs[i + 1].lat - latlngs[i].lat) * f,
latlngs[i].lng + (latlngs[i + 1].lng - latlngs[i].lng) * f),
angle: Math.atan2(latlngs[i + 1].lng - latlngs[i].lng,
latlngs[i + 1].lat - latlngs[i].lat) * (180 / Math.PI)
};
}
acc += segs[i];
}
return {pt: latlngs[latlngs.length - 1], angle: 0};
}

function makeArrowIcon(angle) {
return L.divIcon({
className: 'edge-arrow-marker',
html: `<div style="color:#e67e22;font-size:13px;line-height:1;transform:rotate(${angle}deg);text-shadow:0 0 2px #000">▲</div>`,
iconSize: [13, 13],
iconAnchor: [6.5, 6.5]
});
}

function showEdgeArrows() {
hideEdgeArrows();
for (const eid of Object.keys(state.edges)) {
const e = state.edges[eid];
const latlngs = e.polyline.getLatLngs();
if (latlngs.length < 2) continue;
const d = e.data;
if (!d.oneway) continue;
const {pt, angle} = getEdgeMidpoint(latlngs);
const marker = L.marker(pt, {icon: makeArrowIcon(angle), interactive: false, keyboard: false}).addTo(map);
state.arrowLayers[eid] = marker;
}
}

function refreshEdgeArrow(eid) {
const e = state.edges[eid];
if (!e) return;
const latlngs = e.polyline.getLatLngs();
if (latlngs.length < 2) return;
const d = e.data;
if (!d.oneway) {
if (state.arrowLayers[eid]) {
map.removeLayer(state.arrowLayers[eid]);
delete state.arrowLayers[eid];
}
return;
}
const {pt, angle} = getEdgeMidpoint(latlngs);
if (state.arrowLayers[eid]) {
state.arrowLayers[eid].setLatLng(pt);
state.arrowLayers[eid].setIcon(makeArrowIcon(angle));
} else {
state.arrowLayers[eid] = L.marker(pt, {icon: makeArrowIcon(angle), interactive: false, keyboard: false}).addTo(map);
}
}

function hideEdgeArrows() {
for (const eid of Object.keys(state.arrowLayers)) {
map.removeLayer(state.arrowLayers[eid]);
}
state.arrowLayers = {};
}

// ─── Events ────────────────────────────────────────────────────────────────

function onNodeClick(id, marker, e) {
L.DomEvent.stopPropagation(e);
if (state.tool === 'create-node') {
return; // ignore clicks on existing nodes in create-node mode
}
if (state.tool === 'delete') {
deleteNode(id);
return;
}
if (state.tool === 'simplify') {
if (state.simplifyCandidates.includes(id)) {
simplifyNode(id);
} else {
setStatus('Este nodo no es candidato a simplificar', true);
}
return;
}
if (state.tool === 'create-edge') {
if (!state.edgeSource) {
state.edgeSource = id;
marker.setStyle({color: '#e67e22', fillColor: '#e67e22'});
state.tempLine = L.polyline([marker.getLatLng(), marker.getLatLng()], {
color: '#e74c3c', weight: 2, dashArray: '8,8', opacity: 0.7
}).addTo(map);
setStatus('Seleccione el nodo destino');
} else {
if (id === state.edgeSource) {
setStatus('Seleccione un nodo diferente como destino', true);
return;
}
createEdge(state.edgeSource, id);
state.edgeSource = null;
if (state.tempLine) { map.removeLayer(state.tempLine); state.tempLine = null; }
setStatus('Arista creada');
}
return;
}
// Select mode - select node
hideControlPoints();
if (state.selectedEdgeId) {
const old = state.edges[state.selectedEdgeId];
if (old) old.polyline._visPl.setStyle({color: old.data.oneway ? '#4a90d9' : '#6ab0f9', weight: 3});
            state.selectedEdgeId = null;
}
state.selectedNodeId = id;
showNodeInfo(id);
}

function onNodeDblClick(id, marker, e) {
L.DomEvent.stopPropagation(e);
// Enter node dragging mode
marker.dragging.enable();
setStatus('Arrastre el nodo para moverlo');
}

function onNodeDragEnd(id, marker) {
const pos = marker.getLatLng();
state.nodes[id].lat = pos.lat;
state.nodes[id].lng = pos.lng;
api('PUT', `/api/node/${id}/move`, {lat: pos.lat, lng: pos.lng}).then(r => {
// Update connected edges on map
for (const eid of Object.keys(state.edges)) {
const e = state.edges[eid];
const d = e.data;
if (d.u === id || d.v === id) {
// Reload edge geometry from server
refreshEdgeGeometry(eid);
}
}
setStatus('Nodo movido');
}).catch(() => setStatus('Error al mover nodo', true));
}

async function refreshEdgeGeometry(edgeId) {
const r = await api('GET', `/api/edge/${edgeId}/geometry`);
if (r.error) return;
const e = state.edges[edgeId];
if (e) {
const coords = r.geometry.map(c => [c[1], c[0]]);
e.polyline.setLatLngs(coords);
if (e.visiblePolyline) e.visiblePolyline.setLatLngs(coords);
e.data.u = r.u;
e.data.v = r.v;
e.data.length = r.length;
e.data.oneway = r.oneway;
e.data.reversed = r.reversed;
}
}

async function onEdgeClick(id, polyline, e) {
L.DomEvent.stopPropagation(e);
L.DomEvent.preventDefault(e);
if (state.tool === 'create-node') {
// Split edge at click position
const edgeId = id;
hideControlPoints();
hideInfo();
const r = await api('POST', '/api/node/split', {lat: e.latlng.lat, lng: e.latlng.lng, edge_id: edgeId});
if (r.error) { setStatus(r.error, true); return; }
// Remove original edge from map
deleteEdgeFromMap(edgeId);
// Add new node
addNodeToMap({
type: 'Feature',
geometry: {type: 'Point', coordinates: [r.node.lng, r.node.lat]},
properties: {id: r.node.id, type: 'node'}
});
// Add both new edges
for (const ed of r.edges) {
addEdgeToMap({
type: 'Feature',
geometry: {type: 'LineString', coordinates: ed.geometry},
properties: {id: ed.id, u: ed.u, v: ed.v, key: ed.key, length: ed.length, oneway: ed.oneway, type: 'edge'}
});
}
setStatus('Arista dividida por nuevo nodo');
return;
}
if (state.tool === 'delete') {
deleteEdge(id);
return;
}
if (state.tool === 'dir') {
hideControlPoints();
hideInfo();
if (state.selectedEdgeId === id) {
hideDirPanel();
if (state.selectedEdgeId) {
const old = state.edges[state.selectedEdgeId];
if (old) old.polyline._visPl.setStyle({color: old.data.oneway ? '#4a90d9' : '#6ab0f9', weight: 3});
}
state.selectedEdgeId = null;
return;
}
if (state.selectedEdgeId) {
const old = state.edges[state.selectedEdgeId];
if (old) old.polyline._visPl.setStyle({color: old.data.oneway ? '#4a90d9' : '#6ab0f9', weight: 3});
}
state.selectedEdgeId = id;
polyline._visPl.setStyle({color: '#e67e22', weight: 5});
showDirPanel(id);
return;
}
if (state.tool === 'select') {
hideControlPoints();
if (state.selectedNodeId) { state.selectedNodeId = null; }
if (state.selectedEdgeId === id) {
polyline._visPl.setStyle({color: polyline._edgeData.oneway ? '#4a90d9' : '#6ab0f9', weight: 3});
state.selectedEdgeId = null;
hideInfo();
return;
}
if (state.selectedEdgeId) {
const old = state.edges[state.selectedEdgeId];
if (old) old.polyline._visPl.setStyle({color: old.data.oneway ? '#4a90d9' : '#6ab0f9', weight: 3});
}
state.selectedEdgeId = id;
polyline._visPl.setStyle({color: '#e67e22', weight: 5});
showControlPoints(id);
showEdgeInfo(id);
}
}

function onEdgeDblClick(id, polyline, e) {
L.DomEvent.stopPropagation(e);
if (state.tool === 'dir') return;
// Toggle oneway
const d = state.edges[id].data;
const newOneway = !d.oneway;
api('PUT', `/api/edge/${id}`, {oneway: newOneway}).then(r => {
d.oneway = newOneway;
polyline._visPl.setStyle({color: newOneway ? '#4a90d9' : '#6ab0f9'});
showEdgeInfo(id);
setStatus(`Sentido único: ${newOneway ? 'Sí' : 'No'}`);
});
}

function onEdgeContextMenu(id, polyline, e) {
L.DomEvent.stopPropagation(e);
L.DomEvent.preventDefault(e);
state._ctxEdgeId = id;
state._ctxLatLng = e.latlng;
const menu = document.getElementById('ctx-menu');
menu.style.left = e.originalEvent.clientX + 'px';
menu.style.top = e.originalEvent.clientY + 'px';
menu.style.display = 'block';
}

function onCpDrag(edgeId, idx, cp, e) {
const newLatLng = cp.getLatLng();
const eState = state.edges[edgeId];
if (!eState) return;
const latlngs = eState.polyline.getLatLngs();
latlngs[idx] = newLatLng;
eState.polyline.setLatLngs(latlngs);
if (eState.visiblePolyline) eState.visiblePolyline.setLatLngs(latlngs);
}

function onCpDragEnd(edgeId, cp) {
const pl = state.edges[edgeId].polyline;
const coords = pl.getLatLngs().map(ll => [ll.lng, ll.lat]);
api('PUT', `/api/edge/${edgeId}/geometry`, {coordinates: coords}).then(r => {
state.edges[edgeId].data.length = r.length;
showEdgeInfo(edgeId);
setStatus('Geometría actualizada');
});
}

// ─── Edge Creation ──────────────────────────────────────────────────────────

async function createEdge(u, v) {
const r = await api('POST', '/api/edge', {u, v});
if (r.error) { setStatus(r.error, true); return; }
r.geometry = r.geometry || [[state.nodes[u].lng, state.nodes[u].lat], [state.nodes[v].lng, state.nodes[v].lat]];
addEdgeToMap({
type: 'Feature',
geometry: {type: 'LineString', coordinates: r.geometry},
properties: {
id: r.id, u, v, key: r.key,
length: r.length, oneway: r.oneway, type: 'edge'
}
});
setStatus('Arista creada');
}

// ─── Delete ─────────────────────────────────────────────────────────────────

async function deleteNode(id) {
const r = await api('DELETE', `/api/node/${id}`);
if (r.error) { setStatus(r.error, true); return; }
// Remove from map
const m = state.nodes[id].marker;
map.removeLayer(m);
delete state.nodeLayers[id];
delete state.nodes[id];
// Remove connected edges from map
const toRemove = [];
for (const eid of Object.keys(state.edges)) {
const e = state.edges[eid];
if (e.data.u === id || e.data.v === id) toRemove.push(eid);
}
for (const eid of toRemove) {
const e = state.edges[eid];
if (e) {
map.removeLayer(e.polyline);
if (e.visiblePolyline) map.removeLayer(e.visiblePolyline);
}
delete state.edgeLayers[eid];
delete state.edges[eid];
}
hideInfo();
setStatus('Nodo eliminado');
}

function deleteEdgeFromMap(id) {
const e = state.edges[id];
if (e) {
map.removeLayer(e.polyline);
if (e.visiblePolyline) map.removeLayer(e.visiblePolyline);
}
delete state.edgeLayers[id];
delete state.edges[id];
}

async function deleteEdge(id) {
const r = await api('DELETE', `/api/edge/${id}`);
if (r.error) { setStatus(r.error, true); return; }
deleteEdgeFromMap(id);
hideInfo();
hideControlPoints();
setStatus('Arista eliminada');
}

// ─── Map Click (for create-node) ────────────────────────────────────────────

map.on('click', async function(e) {
if (state.tool === 'create-node') {
const r = await api('POST', '/api/node', {lat: e.latlng.lat, lng: e.latlng.lng});
if (r.error) { setStatus(r.error, true); return; }
addNodeToMap({
type: 'Feature',
geometry: {type: 'Point', coordinates: [r.lng, r.lat]},
properties: {id: r.id, type: 'node'}
});
setStatus('Nodo creado');
}
if (state.tool === 'select') {
hideControlPoints();
if (state.selectedEdgeId) {
const old = state.edges[state.selectedEdgeId];
if (old) old.polyline._visPl.setStyle({color: old.data.oneway ? '#4a90d9' : '#6ab0f9', weight: 3});
            state.selectedEdgeId = null;
}
state.selectedNodeId = null;
hideInfo();
}
if (state.tool === 'simplify') {
setStatus('Click en un nodo naranja para simplificarlo');
}
if (state.tool === 'dir') {
hideDirPanel();
if (state.selectedEdgeId) {
const old = state.edges[state.selectedEdgeId];
if (old) old.polyline._visPl.setStyle({color: old.data.oneway ? '#4a90d9' : '#6ab0f9', weight: 3});
            state.selectedEdgeId = null;
}
}
});

// Track mouse for temp line
map.on('mousemove', function(e) {
if (state.tempLine && state.edgeSource) {
const src = state.nodes[state.edgeSource];
if (src) {
state.tempLine.setLatLngs([src.marker.getLatLng(), e.latlng]);
}
}
});

// ─── Tool Buttons ───────────────────────────────────────────────────────────

document.querySelectorAll('.tbtn[data-tool]').forEach(btn => {
btn.addEventListener('click', () => setTool(btn.dataset.tool));
});

// ─── Context Menu ───────────────────────────────────────────────────────────

document.addEventListener('click', function() {
document.getElementById('ctx-menu').style.display = 'none';
});

document.querySelectorAll('#ctx-menu .item').forEach(item => {
item.addEventListener('click', async function() {
const edgeId = state._ctxEdgeId;
if (!edgeId) return;
const action = this.dataset.action;
if (action === 'add-cp') {
const e = state.edges[edgeId];
if (!e) return;
const ll = state._ctxLatLng || e.polyline.getCenter();
const r = await api('POST', `/api/edge/${edgeId}/control`, {lat: ll.lat, lng: ll.lng});
if (r.error) { setStatus(r.error, true); return; }
// Refresh edge display
const coords = r.coordinates.map(c => [c[1], c[0]]);
e.polyline.setLatLngs(coords);
if (e.visiblePolyline) e.visiblePolyline.setLatLngs(coords);
state.edges[edgeId].data.length = r.length;
showControlPoints(edgeId);
showEdgeInfo(edgeId);
setStatus('Punto de control agregado');
} else if (action === 'toggle-oneway') {
const d = state.edges[edgeId].data;
const newOneway = !d.oneway;
await api('PUT', `/api/edge/${edgeId}`, {oneway: newOneway});
d.oneway = newOneway;
const vis = state.edges[edgeId].polyline._visPl;
if (vis) vis.setStyle({color: newOneway ? '#4a90d9' : '#6ab0f9'});
state.edges[edgeId].polyline.setStyle({color: newOneway ? '#4a90d9' : '#6ab0f9', weight: 10, opacity: 0});
showEdgeInfo(edgeId);
setStatus(`Sentido único: ${newOneway ? 'Sí' : 'No'}`);
}
document.getElementById('ctx-menu').style.display = 'none';
});
});

// ─── Restore ────────────────────────────────────────────────────────────────

let restoreCheckboxes = {};

document.querySelector('.tbtn[data-tool="restore"]').addEventListener('click', openRestore);

async function openRestore() {
const data = await api('GET', '/api/trash');
const items = data.features || [];
const container = document.getElementById('restore-items');
container.innerHTML = '';
restoreCheckboxes = {};
if (items.length === 0) {
container.innerHTML = '<p style="color:#888;padding:8px;">No hay elementos eliminados</p>';
} else {
for (const f of items) {
const id = f.properties.id;
const type = f.properties.type;
const geom = f.geometry;
let label = '';
if (type === 'deleted_node') {
const lat = geom.coordinates[1].toFixed(5);
const lng = geom.coordinates[0].toFixed(5);
label = `Nodo [${lat}, ${lng}]`;
} else {
const u = f.properties.u || '';
const v = f.properties.v || '';
const len = f.properties.length !== undefined ? `${parseFloat(f.properties.length).toFixed(1)}m` : '';
label = `Arista ${u.substring(0,6)}...→${v.substring(0,6)}... ${len}`;
}
const div = document.createElement('div');
div.className = 'item';
const cb = document.createElement('input');
cb.type = 'checkbox';
cb.value = id;
cb.dataset.type = type;
div.appendChild(cb);
div.appendChild(document.createTextNode(label));
container.appendChild(div);
}
}
document.getElementById('restore-modal').classList.add('open');
}

document.getElementById('restore-cancel').addEventListener('click', () => {
document.getElementById('restore-modal').classList.remove('open');
});

document.getElementById('restore-confirm').addEventListener('click', async () => {
const cbs = document.querySelectorAll('#restore-items input[type=checkbox]:checked');
const nodeIds = [];
const edgeIds = [];
cbs.forEach(cb => {
if (cb.dataset.type === 'deleted_node') nodeIds.push(cb.value);
else edgeIds.push(cb.value);
});
if (nodeIds.length === 0 && edgeIds.length === 0) {
setStatus('Seleccione elementos para restaurar', true);
return;
}
const r = await api('POST', '/api/restore', {node_ids: nodeIds, edge_ids: edgeIds});
if (r.error) { setStatus(r.error, true); return; }
document.getElementById('restore-modal').classList.remove('open');
// Reload graph
await loadGraph();
setStatus(`Restaurados: ${r.restored_nodes.length} nodos, ${r.restored_edges.length} aristas`);
});

// ─── Simplify (interactive tool) ─────────────────────────────────────────

async function highlightSimplifyCandidates() {
const data = await api('GET', '/api/simplify/candidates');
state.simplifyCandidates = data.candidates.map(c => c.id);
for (const nid of state.simplifyCandidates) {
const m = state.nodes[nid]?.marker;
if (m) m.setStyle({color: '#e67e22', fillColor: '#e67e22', radius: 9, weight: 3});
}
if (state.simplifyCandidates.length === 0) {
setStatus('No hay nodos intermedios para simplificar');
} else {
setStatus(`${state.simplifyCandidates.length} nodos candidatos. Click en nodo naranja para simplificar (bypass).`);
}
}

function unhighlightSimplifyCandidates() {
for (const nid of state.simplifyCandidates) {
const m = state.nodes[nid]?.marker;
if (m) m.setStyle({color: '#4a90d9', fillColor: '#4a90d9', radius: 7, weight: 2});
}
state.simplifyCandidates = [];
}

async function simplifyNode(id) {
const r = await api('POST', '/api/simplify', {node_ids: [id], mode: 'bypass'});
if (r.error) { setStatus(r.error, true); return; }
await loadGraph();
highlightSimplifyCandidates();
setStatus('Nodo simplificado');
}

// ─── Save & Validate ───────────────────────────────────────────────────────

document.getElementById('btn-save').addEventListener('click', async () => {
const btn = document.getElementById('btn-save');
btn.textContent = 'Guardando...';
btn.disabled = true;
const r = await api('POST', '/api/save');
btn.textContent = 'Guardar Cambios';
btn.disabled = false;
if (r.error) {
setStatus('Error: ' + r.error + (r.details ? ' - ' + r.details.join(', ') : ''), true);
return;
}
setStatus(`Grafo guardado: ${r.nodes} nodos, ${r.edges} aristas`);
btn.style.background = '#27ae60';
setTimeout(() => { btn.style.background = ''; }, 800);
});

document.getElementById('btn-validate').addEventListener('click', async () => {
const r = await api('POST', '/api/validate');
if (r.valid) {
setStatus('Grafo válido');
} else {
setStatus('Errores: ' + r.errors.join(', '), true);
}
});

// ─── Keyboard Shortcuts ────────────────────────────────────────────────────

document.addEventListener('keydown', function(e) {
if (e.key === 's' && (e.ctrlKey || e.metaKey)) {
e.preventDefault();
document.getElementById('btn-save').click();
}
if (e.key === 'Escape') {
document.getElementById('restore-modal').classList.remove('open');
document.getElementById('ctx-menu').style.display = 'none';
hideDirPanel();
if (state.tempLine) { map.removeLayer(state.tempLine); state.tempLine = null; }
if (state.edgeSource) {
const src = state.nodes[state.edgeSource];
if (src) src.marker.setStyle({color: '#4a90d9', fillColor: '#4a90d9'});
state.edgeSource = null;
}
}
});

// ─── Init ───────────────────────────────────────────────────────────────────

loadGraph().then(() => setStatus('Grafo cargado')).catch(e => setStatus('Error al cargar grafo', true));
</script>
</body>
</html>"""


class GraphHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        parts = [p for p in path.split("/") if p]
        if path == "/":
            self._html(HTML)
        elif path == "/api/graph":
            d, s = api_get_graph()
            self._json(d, s)
        elif path == "/api/trash":
            d, s = api_get_trash()
            self._json(d, s)
        elif path == "/api/simplify/candidates":
            d, s = api_simplify_candidates()
            self._json(d, s)
        elif len(parts) >= 4 and parts[1] == "edge" and parts[3] == "geometry":
            d, s = api_get_edge_data(parts[2])
            self._json(d, s)
        else:
            self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        data = self._body()
        parts = [p for p in path.split("/") if p]
        if path == "/api/node":
            d, s = api_create_node(data)
            self._json(d, s)
        elif path == "/api/node/split":
            d, s = api_split_edge(data)
            self._json(d, s)
        elif path == "/api/edge":
            d, s = api_create_edge(data)
            self._json(d, s)
        elif path == "/api/save":
            try:
                d, s = api_save()
                self._json(d, s)
            except Exception as ex:
                import traceback
                traceback.print_exc()
                self._json({"error": str(ex)}, 500)
        elif path == "/api/validate":
            try:
                d, s = api_validate()
                self._json(d, s)
            except Exception as ex:
                import traceback
                traceback.print_exc()
                self._json({"error": str(ex)}, 500)
        elif path == "/api/restore":
            d, s = api_restore(data)
            self._json(d, s)
        elif path == "/api/simplify":
            d, s = api_simplify(data)
            self._json(d, s)
        elif len(parts) >= 4 and parts[1] == "edge" and parts[3] == "control":
            d, s = api_add_control_point(parts[2], data)
            self._json(d, s)
        elif len(parts) >= 4 and parts[1] == "edge" and parts[3] == "direction":
            d, s = api_set_edge_direction(parts[2], data)
            self._json(d, s)
        else:
            self._json({"error": "not found"}, 404)

    def do_PUT(self):
        parsed = urlparse(self.path)
        path = parsed.path
        data = self._body()
        parts = [p for p in path.split("/") if p]
        if len(parts) >= 3 and parts[1] == "node" and parts[3] == "move":
            d, s = api_move_node(parts[2], data)
            self._json(d, s)
        elif len(parts) >= 4 and parts[1] == "edge" and parts[3] == "geometry":
            d, s = api_update_edge_geometry(parts[2], data)
            self._json(d, s)
        elif len(parts) >= 3 and parts[1] == "edge":
            d, s = api_update_edge(parts[2], data)
            self._json(d, s)
        else:
            self._json({"error": "not found"}, 404)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path
        parts = [p for p in path.split("/") if p]
        if len(parts) >= 3 and parts[1] == "node":
            d, s = api_delete_node(parts[2])
            self._json(d, s)
        elif len(parts) >= 3 and parts[1] == "edge":
            d, s = api_delete_edge(parts[2])
            self._json(d, s)
        else:
            self._json({"error": "not found"}, 404)

    def _body(self):
        cl = int(self.headers.get("Content-Length", 0))
        if cl > 0:
            return json.loads(self.rfile.read(cl))
        return {}

    def _json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False, default=str).encode("utf-8"))

    def _html(self, content, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(content.encode("utf-8") if isinstance(content, str) else content)


def main():
    load_graphs()
    port = 5000
    srv = ThreadingHTTPServer(("", port), GraphHandler)
    url = f"http://localhost:{port}"
    print(f"\nServidor iniciado en {url}")
    print("Presione Ctrl+C para detener.\n")
    webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nDeteniendo servidor...")
        srv.server_close()


if __name__ == "__main__":
    main()
