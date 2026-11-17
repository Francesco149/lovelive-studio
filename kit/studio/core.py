"""core.py: shared by the Studio web page (server.py) and the agent's command line (gen.py).

Builds the ComfyUI graph for a Studio job, sends it to the local ComfyUI, waits, and records every image in
my/history.jsonl. Standard library only (runs on ComfyUI's embedded Python).

A job is a dict:
  style      preset id from kit/presets.json "styles" (e.g. "ll_tv")
  character  who: tags such as "1girl, solo, short silver hair, single braid, purple eyes, white cardigan"
  body       body preset id ("none" = no body control) or "custom:<path to a picture>"
  scene      where / what: "seaside railing, ocean, smile, holding paper cup"
  extra_neg  extra negative tags (optional)
  quality    "final" | "draft"            framing  "portrait" | "landscape" | "square"
  seed       int (random when missing)     strength body control strength (default from the body preset)
  round      folder name for the output (default "studio")   name  file name stem (default: time stamp)
"""
import json, os, random, re, shutil, time, urllib.parse, urllib.request, uuid

KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(KIT)
MY = os.path.join(ROOT, "my")
CONTROLS = os.path.join(KIT, "controls")


def load_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def settings():
    s = load_json(os.path.join(MY, "settings.json"), {}) or {}
    s.setdefault("comfy_url", "http://127.0.0.1:8188")
    return s


def presets():
    """kit/presets.json with the friend's own my/presets.json merged on top (their styles, bodies and examples).
    A body picture of their own lives in my/controls/ and is named "my/<file>" in my/presets.json."""
    P = load_json(os.path.join(KIT, "presets.json"))
    mine = load_json(os.path.join(MY, "presets.json"), {}) or {}
    for key in ("styles", "bodies", "quality"):
        P[key].update(mine.get(key, {}))
    P["examples"] = mine.get("examples", []) + P["examples"]
    return P


def append_jsonl(path, rec):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def read_jsonl(path):
    out = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        out.append(json.loads(line))
                    except ValueError:
                        pass
    except OSError:
        pass
    return out


def clean(t):
    """Tidy a tag list typed by a human: newlines -> commas, no doubled commas or spaces."""
    # Danbooru writes tags with underscores, Anima was trained with spaces; score_N tags keep theirs.
    t = re.sub(r"(?<!score)_", " ", (t or "").replace("\n", ", "))
    parts = [p.strip() for p in t.split(",")]
    return ", ".join(p for p in parts if p)


def build_prompt(job, P=None):
    P = P or presets()
    st = P["styles"][job.get("style") or P["default_style"]]
    body = P["bodies"].get(job.get("body") or "none", P["bodies"]["none"]) if not str(job.get("body", "")).startswith("custom:") else {"tags": job.get("body_tags", "")}
    tags = job.get("body_tags") if job.get("body_tags") is not None else body.get("tags", "")
    fields = {"character": clean(job.get("character")), "body": clean(tags), "scene": clean(job.get("scene"))}
    text = st["template"].format(**fields)
    return clean(text)


def build_negative(job, P=None):
    P = P or presets()
    st = P["styles"][job.get("style") or P["default_style"]]
    return clean(st.get("negative", P["negative"]) + ", " + (job.get("extra_neg") or ""))


def control_file(job, P=None):
    """Path of the body control picture for this job, or None."""
    P = P or presets()
    b = str(job.get("body") or "none")
    if b.startswith("custom:"):
        return b[len("custom:"):]
    c = P["bodies"].get(b, {}).get("control")
    if not c:
        return None
    if c.startswith("my/"):
        return os.path.join(MY, "controls", c[3:])
    return os.path.join(CONTROLS, c)


def stage_input(path, s=None):
    """Copy a picture into ComfyUI's input folder (data_dir/inputs/studio/) and return the name LoadImage wants."""
    s = s or settings()
    dst_dir = os.path.join(s["data_dir"], "inputs", "studio")
    os.makedirs(dst_dir, exist_ok=True)
    name = os.path.basename(path)
    if os.path.abspath(path).startswith(os.path.abspath(MY)):
        name = "my_" + name
    dst = os.path.join(dst_dir, name)
    if not os.path.exists(dst) or os.path.getmtime(dst) < os.path.getmtime(path):
        shutil.copy2(path, dst)
    return "studio/" + name


def build_graph(job, P=None, s=None):
    P = P or presets()
    s = s or settings()
    q = P["quality"][job.get("quality") or "final"]
    ctrl = control_file(job, P)
    w, h = P["framing"][job.get("framing") or "portrait"] if not ctrl else P["framing"]["portrait"]
    g = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": q["model"], "weight_dtype": "default"}, "_meta": {"title": "Image model"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": P["text_encoder"], "type": "stable_diffusion", "device": "default"}, "_meta": {"title": "Text encoder"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": P["vae"]}, "_meta": {"title": "VAE"}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": build_prompt(job, P)}, "_meta": {"title": "Prompt"}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": build_negative(job, P)}, "_meta": {"title": "Negative prompt"}},
        "6": {"class_type": "EmptyLatentImage", "inputs": {"width": w, "height": h, "batch_size": 1}, "_meta": {"title": "Size"}},
        "7": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "positive": ["4", 0], "negative": ["5", 0], "latent_image": ["6", 0],
              "seed": int(job["seed"]), "steps": q["steps"], "cfg": q["cfg"], "sampler_name": q["sampler"], "scheduler": q["scheduler"], "denoise": 1.0}, "_meta": {"title": "Sampler"}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["3", 0]}},
        "9": {"class_type": "SaveImage", "inputs": {"images": ["8", 0], "filename_prefix": "%s/%s" % (job["round"], job["name"])}},
    }
    if ctrl:
        body = P["bodies"].get(job.get("body"), {})
        strength = float(job.get("strength") if job.get("strength") is not None else body.get("strength", P["control"]["strength"]))
        g["21"] = {"class_type": "ModelPatchLoader", "inputs": {"name": P["control"]["adapter"]}, "_meta": {"title": "Body control adapter"}}
        g["22"] = {"class_type": "LoadImage", "inputs": {"image": stage_input(ctrl, s)}, "_meta": {"title": "Body picture (grey)"}}
        g["23"] = {"class_type": "AnimaLLLiteApply", "inputs": {"model": ["1", 0], "model_patch": ["21", 0], "image": ["22", 0],
                   "strength": strength, "start_percent": 0.0, "end_percent": float(job.get("end", P["control"]["end"]))}, "_meta": {"title": "Body control"}}
        g["7"]["inputs"]["model"] = ["23", 0]
    return g


def http(url, data=None, timeout=30):
    req = urllib.request.Request(url, data=json.dumps(data).encode() if data is not None else None,
                                 headers={"Content-Type": "application/json"} if data is not None else {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode() or "null")


def comfy_up(s=None):
    s = s or settings()
    try:
        http(s["comfy_url"] + "/system_stats", timeout=3)
        return True
    except Exception:
        return False


def submit(graph, s=None, workflow_ui=None):
    s = s or settings()
    body = {"prompt": graph, "client_id": "studio-" + uuid.uuid4().hex[:8]}
    if workflow_ui:
        body["extra_data"] = {"extra_pnginfo": {"workflow": workflow_ui}}
    r = http(s["comfy_url"] + "/prompt", body)
    if r.get("node_errors"):
        raise RuntimeError("ComfyUI refused the job: %s" % json.dumps(r["node_errors"])[:800])
    return r["prompt_id"]


def wait(prompt_id, s=None, timeout=3600):
    """Wait for a queued job; returns the list of output images [{filename, subfolder, type}]."""
    s = s or settings()
    t0 = time.time()
    while time.time() - t0 < timeout:
        h = http(s["comfy_url"] + "/history/" + prompt_id)
        if h and prompt_id in h:
            e = h[prompt_id]
            st = e.get("status", {})
            if st.get("status_str") == "error":
                msgs = [m for m in st.get("messages", []) if m[0] == "execution_error"]
                raise RuntimeError("generation failed: %s" % (msgs[-1][1].get("exception_message", "") if msgs else "unknown"))
            imgs = []
            for o in e.get("outputs", {}).values():
                imgs += o.get("images", [])
            if imgs or st.get("completed"):
                return imgs
        time.sleep(1.0)
    raise TimeoutError("still not finished after %d s" % timeout)


def new_job(job):
    j = dict(job)
    j.setdefault("style", presets()["default_style"])
    j.setdefault("quality", "final")
    j.setdefault("framing", "portrait")
    j.setdefault("body", "none")
    if j.get("seed") in (None, "", -1, "-1"):
        j["seed"] = random.randint(1, 2**31 - 1)
    j["seed"] = int(j["seed"])
    j.setdefault("round", "studio")
    j["round"] = "".join(c for c in str(j["round"]) if c.isalnum() or c in "-_") or "studio"
    if not j.get("name"):
        j["name"] = time.strftime("%Y%m%d-%H%M%S") + "_s%d" % j["seed"]
    j["name"] = "".join(c for c in str(j["name"]) if c.isalnum() or c in "-_.") or "img"
    return j


def run(job, s=None, on_queued=None):
    """Generate one image. Returns the history record (also appended to my/history.jsonl)."""
    s = s or settings()
    P = presets()
    j = new_job(job)
    g = build_graph(j, P, s)
    ui = None
    try:
        import ui_workflow
        ui = ui_workflow.to_ui(g, s)
    except Exception:
        ui = None
    t0 = time.time()
    pid = submit(g, s, ui)
    if on_queued:
        on_queued(pid)
    imgs = wait(pid, s)
    secs = round(time.time() - t0, 1)
    files = [("%s/%s" % (i["subfolder"], i["filename"])).lstrip("/") for i in imgs if i.get("type") == "output"]
    rec = {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "file": files[0] if files else None, "round": j["round"], "name": j["name"],
           "style": j["style"], "character": j.get("character", ""), "body": j["body"], "body_tags": j.get("body_tags"),
           "scene": j.get("scene", ""), "extra_neg": j.get("extra_neg", ""), "quality": j["quality"], "framing": j["framing"],
           "seed": j["seed"], "strength": j.get("strength"), "prompt": build_prompt(j, P), "negative": build_negative(j, P), "secs": secs,
           "note": j.get("note", "")}
    append_jsonl(os.path.join(MY, "history.jsonl"), rec)
    return rec


def output_path(rel, s=None):
    s = s or settings()
    return os.path.join(s["data_dir"], "outputs", rel.replace("/", os.sep))


def feedback(file, rating=None, note=None, who="friend"):
    rec = {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "file": file, "rating": rating, "note": note or "", "by": who}
    append_jsonl(os.path.join(MY, "feedback.jsonl"), rec)
    return rec


def latest_feedback():
    """file -> latest {rating, note}."""
    out = {}
    for r in read_jsonl(os.path.join(MY, "feedback.jsonl")):
        cur = out.setdefault(r["file"], {"rating": None, "note": ""})
        if r.get("rating") is not None:
            cur["rating"] = None if r["rating"] == "none" else r["rating"]
        if r.get("note"):
            cur["note"] = r["note"]
    return out
