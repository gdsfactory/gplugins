from functools import lru_cache

import gdsfactory as gf
import gdstk
import numpy as np
import shapely.geometry as sg
from natsort import natsorted


def patch_netlist(netlist):
    if not netlist.get("nets") and not netlist["ports"] and not netlist["instances"]:
        netlist = wrap_component_in_netlist(netlist.get("name", ""))
    netlist = patch_netlist_with_port_info(netlist)
    netlist = patch_netlist_with_icon_info(netlist)
    netlist = patch_netlist_with_hierarchical_info(netlist)
    netlist = patch_netlist_with_connection_info(netlist)
    netlist = patch_netlist_with_placements_info(netlist, 400, 400)
    return netlist


def patch_netlist_with_port_info(netlist):
    i = netlist["info"] = netlist.get("info", {})
    s = i["schematic"] = i.get("schematic", {})
    c = s["component_ports"] = s.get("component_ports", {})
    components = {get_component_name(v) for v in netlist["instances"].values()}
    for component in c:
        components.remove(component)
    for name in natsorted(components):
        c[name] = get_ports(name)
    return netlist


def patch_netlist_with_icon_info(netlist):
    i = netlist["info"] = netlist.get("info", {})
    s = i["schematic"] = i.get("schematic", {})
    c = s["component_icons"] = s.get("component_icons", {})
    components = {get_component_name(v) for v in netlist["instances"].values()}
    for component in c:
        components.remove(component)
    for name in natsorted(components):
        try:
            _c = gf.get_component(name)
        except Exception:
            c[name] = []
            continue
        c[name] = get_icon_poly(_c)
    return netlist


def patch_netlist_with_connection_info(netlist):
    i = netlist["info"] = netlist.get("info", {})
    s = i["schematic"] = i.get("schematic", {})
    ic = s["implicit_connections"] = s.get("implicit_connections", {})
    for ip1, ip2 in netlist["nets"]:
        if _is_implicit_connection(ip1, ip2, netlist["instances"], netlist["nets"]):
            ic["ip1"] = ip2
    return netlist


def patch_netlist_with_hierarchical_info(netlist):
    netlist["info"]["schematic"]["hierarchical"] = natsorted(
        {
            get_component_name(inst)
            for inst in netlist["instances"].values()
            if _is_hierarchical_pic(get_component_name(inst))
        }
    )
    return netlist


def patch_netlist_with_placements_info(netlist, width, height):
    if "instances" not in netlist:
        return
    netlist["ports"] = netlist.get("ports", {})
    netlist["info"] = netlist.get("info", {})
    netlist["info"]["schematic"] = netlist["info"].get("schematic", {})
    netlist["placements"] = netlist.get("placements", {})
    positions = {
        i: netlist["placements"].get(i, {"x": 10, "y": 10})
        for i in netlist["instances"]
    }
    positions.update(
        {
            p: netlist["instances"].get(v.split(",")[0], {"x": 10, "y": 10})
            for p, v in netlist["ports"].items()
        }
    )
    positions = {
        k: {"x": v.get("x", 10), "y": -v.get("y", 10)} for k, v in positions.items()
    }
    min_x = min([p["x"] for p in positions.values()])
    min_y = min([p["y"] for p in positions.values()])
    positions = {
        k: {"x": p["x"] - min_x, "y": p["y"] - min_y} for k, p in positions.items()
    }
    max_x = max(max([p["x"] for p in positions.values()]), 10)
    max_y = max(max([p["y"] for p in positions.values()]), 10)
    positions = {
        k: {
            "x": 100 + round(p["x"] / max_x * width),
            "y": 100 + round(p["y"] / max_y * height),
        }
        for k, p in positions.items()
    }
    nports = [p for p in netlist["ports"] if _get_orientation(netlist, p) == "n"]
    eports = [p for p in netlist["ports"] if _get_orientation(netlist, p) == "e"]
    sports = [p for p in netlist["ports"] if _get_orientation(netlist, p) == "s"]
    wports = [p for p in netlist["ports"] if _get_orientation(netlist, p) not in ["n", "e", "s"]]  # fmt: skip
    dn = width / max(len(nports), 1)
    de = height / max(len(eports), 1)
    ds = width / max(len(sports), 1)
    dw = height / max(len(wports), 1)
    for i, p in enumerate(nports):
        positions[p] = {
            "x": round(dn / 2 + i * dn),
            "y": 50,
        }
    for i, p in enumerate(eports):
        positions[p] = {
            "x": width + 150,
            "y": round(de / 2 + i * de),
        }
    for i, p in enumerate(sports):
        positions[p] = {
            "x": round(ds / 2 + i * ds),
            "y": height + 150,
        }
    for i, p in enumerate(wports):
        positions[p] = {
            "x": 50,
            "y": round(dw / 2 + i * dw),
        }
    if len(netlist["instances"]) != 1:
        netlist["info"]["schematic"]["placements"] = {
            k: positions[k] for k in netlist["instances"]
        }
    else:
        netlist["info"]["schematic"]["placements"] = {
            list(netlist["instances"])[0]: {"x": width // 2, "y": height // 2}
        }

    netlist["info"]["schematic"]["port_placements"] = {
        k: positions[k] for k in netlist["ports"]
    }
    return netlist


def get_ports(child, parent=None):
    try:
        c = gf.get_component(child)
    except Exception:
        if parent is None:
            return {}
        p = gf.get_component(parent)
        c = [r.parent for r in p.references if r.parent.name.startswith(child)][0]

    ports1 = sort_ports(c.ports)

    try:
        netlist = get_netlist(c)
    except KeyError:
        netlist = {}

    if netlist:
        ports2 = natsorted(netlist["ports"])
        ports = ports1 if len(ports1) > len(ports2) else ports2
    else:
        ports = ports1

    x0 = c.xmin
    x1 = c.xmax
    y0 = c.ymin
    y1 = c.ymax
    x0, x1 = min(x0, x1), max(x0, x1)
    y0, y1 = min(y0, y1), max(y0, y1)

    n = sg.LineString(coordinates=[(x0, y1), (x1, y1)])
    e = sg.LineString(coordinates=[(x1, y0), (x1, y1)])
    s = sg.LineString(coordinates=[(x0, y0), (x1, y0)])
    w = sg.LineString(coordinates=[(x0, y0), (x0, y1)])

    def orientation(x, y):
        p = sg.Point((x, y))
        dn = n.distance(p)
        de = e.distance(p)
        ds = s.distance(p)
        dw = w.distance(p)
        i = np.argmin([dn, de, ds, dw])
        return ["n", "e", "s", "w"][i]

    ports = {port.name: orientation(*c.ports[port.name].center) for port in ports}
    return ports


def get_netlist(c: gf.Component, with_instance_info=False):
    try:
        netlist = c.get_netlist()
    except TypeError:
        netlist = c.get_netlist()
    netlist = replace_cross_sections_recursive(netlist)
    if not with_instance_info:
        netlist = remove_instance_info(netlist)
    return netlist


def get_icon_poly(name):
    default = [(0.25, 0.25), (0.75, 0.25), (0.75, 0.75), (0.25, 0.75)]
    straight = [(0.0, 0.40), (1.0, 0.40), (1.0, 0.60), (0.0, 0.60)]
    taper = [(0.0, 0.40), (1.0, 0.1), (1.0, 0.9), (0.0, 0.60)]
    if "straight" in name:
        return straight
    if "taper" in name or "trans" in name:
        return taper
    c = gf.get_component(name)
    layer_priority = {lay: i for i, lay in enumerate(most_common_layers())}
    polys = {}
    for layer, p in c.get_polygons_points().items():
        if layer not in polys:
            polys[layer] = []
        polys[layer].append(p)
    polys_priority = {layer_priority.get(lay, None): ps for lay, ps in polys.items()}
    polys_priority = {pr: ps for pr, ps in polys_priority.items() if pr is not None}
    if not polys_priority:
        return default
    polys = min(polys_priority.items(), key=lambda x: x[0])[1]
    if not polys:
        return default
    polys = gdstk.boolean(polys, [], operation="or")
    if not polys:
        return default
    poly = rdp(polys[0].points)
    if (poly.shape[0] < 3) or (poly.shape[0] > 100):
        return default
    poly = (poly - c.bbox_np()[0:1]) / (c.bbox_np()[1:2] - c.bbox_np()[0:1])
    poly = list(poly)
    if "coupler" in name:
        ymin = min(poly, key=lambda xy: xy[1])[1]
        poly = [
            *[(x, 0.5 + (y - ymin + 0.05) / 2) for x, y in poly],
            *[(x, 0.5 - (y - ymin + 0.05) / 2) for x, y in poly],
        ]
    return poly


def rdp(poly, eps=0.1):
    poly = np.asarray(poly)
    if not poly.shape:
        return np.array([])
    if poly.shape[0] < 3:
        return poly
    start, end = poly[0], poly[-1]
    dists = _line_dists(poly, start, end)

    index = np.argmax(dists)
    dmax = dists[index]

    if dmax <= eps:
        return np.array([start, end])

    result1 = rdp(poly[: index + 1], eps=eps)
    result2 = rdp(poly[index:], eps=eps)
    return np.vstack((result1[:-1], result2))


def _line_dists(points, start, end):
    if np.all(start == end):
        return np.linalg.norm(points - start, axis=1)
    vec = end - start
    cross = np.cross(vec, start - points)
    return np.divide(abs(cross), np.linalg.norm(vec))


def sort_ports(ports) -> list[gf.Port]:
    return natsorted(ports, key=lambda port: port.x)


def wrap_component_in_netlist(name):
    if not name:
        return {}
    c = gf.Component()
    _ = c << gf.get_component(name)
    c.name = name
    ports = {p: f"{name},{p}" for p in c.insts[0].ports}
    return {
        "instances": {
            f"{name}": {
                "component": name,
                "settings": {},
            },
        },
        "nets": [],
        "ports": {p: ports[p] for p in sort_ports(ports)},
    }


def _bad_instance(_) -> bool:
    return False


def _get_orientation(patched_netlist, port):
    ip = patched_netlist["ports"][port]
    i, p = ip.split(",")
    c = get_component_name(patched_netlist["instances"][i])
    component_ports = patched_netlist["info"]["schematic"]["component_ports"]
    return component_ports.get(c, {}).get(p, "e")


def get_component_name(component_dict: dict | str, default="") -> str:
    if isinstance(component_dict, str):
        return component_dict
    else:
        return component_dict.get("component", default)


def ensure_netlist_order(netlist):
    netlist = {**netlist}
    return {
        "pdk": netlist.pop("pdk", ""),
        "instances": netlist.pop("instances", {}),
        "nets": netlist.pop("nets", []),
        "routes": netlist.pop("routes", {}),
        "ports": netlist.pop("ports", {}),
        "placements": netlist.pop("placements", {}),
        "info": netlist.pop("info", {}),
        **netlist,
    }


def replace_cross_sections_recursive(obj):
    if isinstance(obj, dict):
        for k in list(obj.keys()):
            if k == "cross_section":
                obj[k] = check_cross_section(obj[k])
            else:
                obj[k] = replace_cross_sections_recursive(obj[k])
    return obj


def remove_instance_info(netlist):
    for inst in netlist["instances"].values():
        if "info" in inst:
            del inst["info"]
    return netlist


def check_cross_section(cross_section):
    pdk = gf.get_active_pdk()
    if isinstance(cross_section, str):
        if cross_section in pdk.cross_sections:
            return cross_section
        else:
            raise ValueError(f"Invalid cross section: {cross_section}")
    elif isinstance(cross_section, gf.CrossSection):
        pass
    elif isinstance(cross_section, dict):
        cross_section = gf.CrossSection(**cross_section)
    else:
        raise ValueError(f"Invalid cross section: {cross_section}")

    for k, v in pdk.cross_sections.items():
        if callable(v):
            v = v()
        if tuple(cross_section.sections) == tuple(v.sections):
            return k

    raise ValueError(f"Invalid cross section: {cross_section}")


@lru_cache
def most_common_layers():
    pdk = gf.get_active_pdk()
    layers = {}
    for cellfunc in list(pdk.cells.values()):
        try:
            cell = cellfunc()
        except Exception:
            continue
        for layer in cell.layers:
            if layer not in layers:
                layers[layer] = 0
            layers[layer] += 1
    return [lay for lay, _ in sorted(layers.items(), key=lambda x: -x[1])]


def _is_implicit_connection(ip1, ip2, instances, connections):
    i1, _ = ip1.split(",")
    i2, _ = ip2.split(",")
    if i1 not in instances:
        return False
    if i2 not in instances:
        return False
    return connections[ip1] != ip2 and connections[ip2] != ip1


def _is_hierarchical_pic(name):
    c = gf.get_component(name)
    return bool(c.insts)
