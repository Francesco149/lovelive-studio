"""ui_workflow.py: turns a ComfyUI API graph into an editor workflow (the format ComfyUI's page loads), with a tidy layout,
coloured groups and notes. Used (1) to embed an editable workflow in every Studio picture (drag the PNG into ComfyUI)
and (2) by make_workflows.py to write kit/workflows/*.json. Needs the node definitions: read from the running ComfyUI
(/object_info), cached in <data>/object_info.json; make_workflows.py can also pass a saved copy.
"""
import json, os, urllib.request

_OI = {}

# Where each node of a Studio graph goes (column x, row y) and its group. Unknown nodes are stacked on the right.
LAYOUT = {
    "s1": (0, 0), "s2": (0, 170), "s3": (0, 340), "s4": (0, 510), "s5": (0, 680), "neg": (0, 850),
    "c1": (470, 40), "c2": (470, 100), "c3": (470, 160), "c4": (470, 220),
    "1": (880, 0), "2": (880, 120), "3": (880, 260),
    "21": (880, 470), "22": (880, 590), "23": (1240, 470),
    "4": (1640, 0), "5": (1640, 180), "6": (1640, 360), "7": (2010, 0), "8": (2370, 0), "9": (2370, 110),
}
SIZE = {"PrimitiveStringMultiline": (420, 130), "CLIPTextEncode": (330, 140), "KSampler": (320, 270), "SaveImage": (520, 760),
        "LoadImage": (320, 400), "StringConcatenate": (300, 40), "MarkdownNote": (440, 640), "AnimaLLLiteApply": (300, 180),
        "EmptyLatentImage": (330, 110), "VAEDecode": (220, 50)}
COLLAPSED = {"c1", "c2", "c3", "c4", "8"}
GROUPS = [  # title, colour, member node ids
    ("1. YOUR PROMPT  (edit the pink boxes)", "#a1309b", ["s1", "s2", "s3", "s4", "s5", "neg"]),
    ("glue: joins the boxes into one prompt", "#444444", ["c1", "c2", "c3", "c4"]),
    ("2. MODELS  (leave as they are)", "#3f789e", ["1", "2", "3"]),
    ("3. BODY DRAWING  (bypass this group with Ctrl+B for tags only)", "#8A8A3a", ["21", "22", "23"]),
    ("4. DRAW", "#3f789e", ["4", "5", "6", "7", "8", "9"]),
]
PINK = {"s2", "s4", "s5", "neg"}
WIDGET_TYPES = {"INT", "FLOAT", "STRING", "BOOLEAN", "COMBO"}


def object_info(cls, s=None):
    if cls in _OI:
        return _OI[cls]
    url = (s or {}).get("comfy_url", "http://127.0.0.1:8188")
    with urllib.request.urlopen(url + "/object_info/" + cls, timeout=10) as r:
        _OI[cls] = json.loads(r.read().decode())[cls]
    return _OI[cls]


def preload(path):
    """Use a saved object_info.json (dict class -> info) instead of asking ComfyUI."""
    with open(path, encoding="utf-8") as f:
        _OI.update(json.load(f))


def _spec(info, name):
    for part in ("required", "optional"):
        if name in info["input"].get(part, {}):
            return info["input"][part][name]
    return None


def _is_widget(spec):
    if spec is None:
        return False
    t = spec[0]
    return isinstance(t, list) or t in WIDGET_TYPES


def _type(spec):
    return "COMBO" if isinstance(spec[0], list) else spec[0]


def to_ui(graph, s=None, notes=None, title=None):
    """API graph {id: {class_type, inputs, _meta}} -> editor workflow dict."""
    g = {k: v for k, v in graph.items() if not k.startswith("_")}
    ids = {k: i + 1 for i, k in enumerate(g)}
    # topological order (for the 'order' field)
    order, seen = [], set()

    def visit(k):
        if k in seen:
            return
        seen.add(k)
        for v in g[k]["inputs"].values():
            if isinstance(v, list) and len(v) == 2 and isinstance(v[0], str) and v[0] in g:
                visit(v[0])
        order.append(k)
    for k in g:
        visit(k)
    nodes, links = {}, []
    out_links = {}  # (node, slot) -> [link ids]
    extra_y = 0
    for k, n in g.items():
        info = object_info(n["class_type"], s)
        names = info["input_order"].get("required", []) + info["input_order"].get("optional", [])
        inputs, widgets = [], []
        for name in names:
            spec = _spec(info, name)
            val = n["inputs"].get(name)
            linked = isinstance(val, list) and len(val) == 2 and isinstance(val[0], str) and val[0] in g
            if _is_widget(spec):
                if linked:
                    inputs.append({"name": name, "type": _type(spec), "widget": {"name": name}, "link": None, "_src": val})
                    widgets.append(spec[1].get("default", "") if len(spec) > 1 and isinstance(spec[1], dict) else "")
                else:
                    widgets.append(val if val is not None else (spec[1].get("default") if len(spec) > 1 and isinstance(spec[1], dict) else None))
                opts = spec[1] if len(spec) > 1 and isinstance(spec[1], dict) else {}
                if opts.get("control_after_generate"):
                    widgets.append("fixed")
                if opts.get("image_upload"):
                    widgets.append("image")
            elif spec is not None:
                inputs.append({"name": name, "type": _type(spec), "link": None, "_src": val if linked else None})
        outs = [{"name": (info.get("output_name") or info["output"])[i], "type": t, "links": [], "slot_index": i} for i, t in enumerate(info["output"])]
        x, y = LAYOUT.get(k, (2400, extra_y))
        if k not in LAYOUT:
            extra_y += 200
        w, h = SIZE.get(n["class_type"], (320, 110))
        node = {"id": ids[k], "type": n["class_type"], "pos": [x, y], "size": [w, h], "flags": {"collapsed": True} if k in COLLAPSED else {}, "order": order.index(k), "mode": 0,
                "inputs": inputs, "outputs": outs, "properties": {"Node name for S&R": n["class_type"]}, "widgets_values": widgets}
        t = (n.get("_meta") or {}).get("title")
        if t:
            node["title"] = t
        if k in PINK:
            node["color"], node["bgcolor"] = "#a1309b", "#4a1f47"
        nodes[k] = node
    lid = 0
    for k, node in nodes.items():
        for slot, inp in enumerate(node["inputs"]):
            src = inp.pop("_src", None)
            if not src:
                continue
            lid += 1
            inp["link"] = lid
            nodes[src[0]]["outputs"][src[1]]["links"].append(lid)
            links.append([lid, ids[src[0]], src[1], node["id"], slot, inp["type"]])
    for node in nodes.values():
        for o in node["outputs"]:
            if not o["links"]:
                o["links"] = None
    allnodes = list(nodes.values())
    nid = len(allnodes)
    for (x, y, w, h, text) in notes or []:
        nid += 1
        allnodes.append({"id": nid, "type": "MarkdownNote", "pos": [x, y], "size": [w, h], "flags": {}, "order": nid, "mode": 0,
                         "inputs": [], "outputs": [], "properties": {}, "widgets_values": [text], "color": "#432", "bgcolor": "#653"})
    groups = []
    for gt, col, members in GROUPS:
        ms = [nodes[m] for m in members if m in nodes]
        if not ms:
            continue
        x0 = min(m["pos"][0] for m in ms) - 15
        y0 = min(m["pos"][1] for m in ms) - 50
        x1 = max(m["pos"][0] + m["size"][0] for m in ms) + 15
        y1 = max(m["pos"][1] + (30 if m["flags"].get("collapsed") else m["size"][1]) for m in ms) + 15
        groups.append({"title": gt, "bounding": [x0, y0, x1 - x0, y1 - y0], "color": col, "font_size": 22, "flags": {}})
    wf = {"last_node_id": nid, "last_link_id": lid, "nodes": allnodes, "links": links, "groups": groups, "config": {},
          "extra": {"ds": {"scale": 0.7, "offset": [600, 80]}}, "version": 0.4}
    if title:
        wf["extra"]["studio_title"] = title
    return wf
