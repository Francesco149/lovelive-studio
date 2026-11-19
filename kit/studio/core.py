"""core.py: shared by the Studio web page (server.py) and the agent's command line (gen.py).

Builds the ComfyUI graph for a Studio job, sends it to the local ComfyUI, waits, and records every image in
my/history.jsonl. Standard library only (runs on ComfyUI's embedded Python).

A job is a dict:
  style      preset id from kit/presets.json "styles" (e.g. "ll_tv")
  character  who: tags such as "1girl, solo, short silver hair, single braid, purple eyes, white cardigan"
  body       body preset id ("none" = no body control) or "custom:<path to a picture>"
  scene      where / what: "seaside railing, ocean, smile, holding paper cup"
  extra_neg  extra negative tags (optional)
  quality    "draft" (Preview, default) | "final"            framing  "portrait" | "landscape" | "square"
  seed       int (random when missing)     strength body control strength (default from the body preset)
  round      folder name for the output (default "studio" from the page, "claude" from gen.py)   name  file name stem

Privacy: pictures made on the Studio page (and pictures pasted into it) belong to the user. Their records live in
my/private/ (not in git), and the agent sees one only after the user makes it public (my/library.json "public").
my/history.jsonl holds only the agent's own pictures. my/library.json also holds the trash (soft-deleted files).
"""
import json, os, random, re, shutil, threading, time, urllib.parse, urllib.request, uuid

KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(KIT)
MY = os.path.join(ROOT, "my")
CONTROLS = os.path.join(KIT, "controls")
PRIVATE = os.path.join(MY, "private")
HIST = os.path.join(MY, "history.jsonl")            # the agent's pictures
FEED = os.path.join(MY, "feedback.jsonl")           # ratings / notes on the agent's pictures and rounds
PHIST = os.path.join(PRIVATE, "history.jsonl")      # the user's own Studio pictures (private unless made public)
PFEED = os.path.join(PRIVATE, "feedback.jsonl")     # ratings / notes on those
LIB = os.path.join(MY, "library.json")              # {"public": {file: time}, "trash": {file: time}, "deleted": {file: time}}
WLOCK = threading.RLock()                           # the page server writes these files from several threads


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
    with WLOCK, open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def write_jsonl(path, recs):
    """Replace a jsonl file atomically (only the page server does this: moving, deleting records)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


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
    if job.get("engine") in ("h3", "video"):
        return (job.get("prompt") or "").strip()
    st = P["styles"][job.get("style") or P["default_style"]]
    body = P["bodies"].get(job.get("body") or "none", P["bodies"]["none"]) if not str(job.get("body", "")).startswith("custom:") else {"tags": job.get("body_tags", "")}
    tags = job.get("body_tags") if job.get("body_tags") is not None else body.get("tags", "")
    fields = {"character": clean(job.get("character")), "body": clean(tags), "scene": clean(job.get("scene"))}
    text = st["template"].format(**fields)
    return clean(text)


def build_late_prompt(job, P=None):
    """The style's late prompt (used for the last steps only), or None. Eye colours are weighted up in it so the show's
    name does not recolour them toward a canon character's."""
    P = P or presets()
    if job.get("engine") in ("h3", "video"):
        return None
    st = P["styles"][job.get("style") or P["default_style"]]
    late = st.get("late")
    if not late:
        return None
    j = dict(job)
    j["character"] = re.sub(r"(?<![(\w])([a-z]+ eyes)(?![:\w])", r"(\1:1.3)", clean(job.get("character")))
    return build_prompt(dict(j, style="__late__"), dict(P, styles=dict(P["styles"], __late__={"template": late["template"]})))


def build_negative(job, P=None):
    P = P or presets()
    if job.get("engine") in ("h3", "video"):
        return ""
    st = P["styles"][job.get("style") or P["default_style"]]
    body = P["bodies"].get(str(job.get("body") or "none"), {})
    return clean(st.get("negative", P["negative"]) + ", " + body.get("neg", "") + ", " + (job.get("extra_neg") or ""))


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


def resolve_picture(ref, s=None):
    """A picture given as a file path, or as "out:<round>/<file>" (a Studio output)."""
    s = s or settings()
    if str(ref).startswith("out:"):
        return output_path(ref[4:], s)
    return ref


def build_graph_h3(job, P, s):
    """MiniMax H3-Image: plain-English prompt, 6 steps, CFG 1. With "images" (1-2 pictures) it edits / uses them as
    Picture 1, Picture 2 in the prompt; the output size is explicit."""
    H = P["h3"]
    w, h = H["sizes"][job.get("framing") or "portrait"]
    if job.get("width") and job.get("height"):
        w, h = int(job["width"]), int(job["height"])
    g = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": H["model"], "weight_dtype": "default"}, "_meta": {"title": "H3-Image model"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": H["text_encoder"], "type": "minimax", "device": "default"}, "_meta": {"title": "H3 text encoder"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": H["vae"]}, "_meta": {"title": "H3 VAE"}},
        "6": {"class_type": "MiniMaxH3ImageConditioning", "inputs": {"clip": ["2", 0], "prompt": build_prompt(job, P), "width": w, "height": h, "vae": ["3", 0]}, "_meta": {"title": "Prompt"}},
        "7": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["6", 0]}},
        "8": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "positive": ["6", 0], "negative": ["7", 0], "latent_image": ["6", 1], "seed": int(job["seed"]),
              "steps": H["steps"], "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0}, "_meta": {"title": "Sampler"}},
        "9": {"class_type": "VAEDecode", "inputs": {"samples": ["8", 0], "vae": ["3", 0]}},
        "10": {"class_type": "SaveImage", "inputs": {"images": ["9", 0], "filename_prefix": "%s/%s" % (job["round"], job["name"])}},
    }
    for i, ref in enumerate((job.get("images") or [])[:2]):
        li, sc = "4%d" % i, "5%d" % i
        g[li] = {"class_type": "LoadImage", "inputs": {"image": stage_input(resolve_picture(ref, s), s)}, "_meta": {"title": "Picture %d" % (i + 1)}}
        g[sc] = {"class_type": "ImageScaleToTotalPixels", "inputs": {"image": [li, 0], "upscale_method": "lanczos", "megapixels": H["ref_megapixels"], "resolution_steps": 32}}
        g["6"]["inputs"]["images.image_%d" % (i + 1)] = [sc, 0]
    return g


VIDEO_ASPECT = {"portrait": 2 / 3, "landscape": 16 / 9, "square": 1.0, "phone": 9 / 16}


def video_size(job, V, s):
    """Width x height for a clip: the resolution's pixel count at the shape's aspect ("auto" = the first frame's), in
    multiples of 32 (H3 needs them)."""
    area = V["resolutions"][job.get("resolution") or V["default_resolution"]]
    ar = VIDEO_ASPECT.get(job.get("framing") or "auto")
    if ar is None:
        ar = 2 / 3
        if job.get("images"):
            try:
                from PIL import Image
                with Image.open(resolve_picture(job["images"][0], s)) as im:
                    ar = im.width / im.height
            except Exception:
                pass
    w = max(256, int(round((area * ar) ** 0.5 / 32)) * 32)
    h = max(256, int(round((area / ar) ** 0.5 / 32)) * 32)
    return w, h


def video_length(job, V):
    secs = min(float(job.get("seconds") or V["default_seconds"]), V["max_seconds"])
    return int(round(secs * V["fps"])) + 4  # 5 s -> 124 frames, as in MiniMax's examples


def build_graph_video(job, P, s):
    """MiniMax H3 video (FL2VA w4a8 + Pika Flex 6-step): a clip with sound from a description, optionally starting
    from a picture (first frame). 480p 5 s takes about 2.5 minutes on an RTX 5060 8 GB with 16 GB RAM (720p: 6 min)."""
    V = P["video"]
    w, h = video_size(job, V, s)
    g = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": V["model"], "weight_dtype": "default"}, "_meta": {"title": "H3 video model"}},
        "3": {"class_type": "CLIPLoader", "inputs": {"clip_name": V["text_encoder"], "type": "minimax", "device": "default"}, "_meta": {"title": "H3 text encoder"}},
        "4": {"class_type": "VAELoader", "inputs": {"vae_name": V["vae"]}, "_meta": {"title": "Video VAE"}},
        "5": {"class_type": "VAELoader", "inputs": {"vae_name": V["audio_vae"]}, "_meta": {"title": "Audio VAE"}},
        "6": {"class_type": "MiniMaxH3ImageToVideo", "inputs": {"clip": ["3", 0], "vae": ["4", 0], "prompt": build_prompt(job, P), "width": w, "height": h,
              "length": video_length(job, V)}, "_meta": {"title": "Prompt"}},
        "7": {"class_type": "BasicGuider", "inputs": {"model": ["1", 0], "conditioning": ["6", 0]}},
        "8": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": V["sampler"]}},
        "9": {"class_type": "ManualSigmas", "inputs": {"sigmas": V["sigmas"]}},
        "10": {"class_type": "RandomNoise", "inputs": {"noise_seed": int(job["seed"])}},
        "11": {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": ["10", 0], "guider": ["7", 0], "sampler": ["8", 0], "sigmas": ["9", 0], "latent_image": ["6", 1]}, "_meta": {"title": "Sampler"}},
        "12": {"class_type": "VAEDecode", "inputs": {"samples": ["11", 0], "vae": ["4", 0]}},
        "13": {"class_type": "VAEDecodeAudio", "inputs": {"samples": ["11", 0], "vae": ["5", 0]}},
        "14": {"class_type": "CreateVideo", "inputs": {"images": ["12", 0], "fps": float(V["fps"]), "audio": ["13", 0]}},
        "15": {"class_type": "SaveVideo", "inputs": {"video": ["14", 0], "filename_prefix": "%s/%s" % (job["round"], job["name"]), "format": "mp4", "codec": "h264"}},
    }
    model = ["1", 0]
    if V.get("lora"):
        g["2"] = {"class_type": "LoraLoaderModelOnly", "inputs": {"model": model, "lora_name": V["lora"], "strength_model": 1.0}, "_meta": {"title": "6-step LoRA"}}
        model = ["2", 0]
    if V.get("attention"):
        g["20"] = {"class_type": "ModelAttentionBackend", "inputs": {"model": model, "attention": V["attention"]}}
        model = ["20", 0]
    g["7"]["inputs"]["model"] = model
    if job.get("images"):
        g["16"] = {"class_type": "LoadImage", "inputs": {"image": stage_input(resolve_picture(job["images"][0], s), s)}, "_meta": {"title": "First frame"}}
        g["17"] = {"class_type": "ImageScale", "inputs": {"image": ["16", 0], "upscale_method": "lanczos", "width": w, "height": h, "crop": "center"}}
        g["6"]["inputs"]["first_frame"] = ["17", 0]
    return g


def build_graph(job, P=None, s=None):
    P = P or presets()
    s = s or settings()
    if job.get("engine") == "h3":
        return build_graph_h3(job, P, s)
    if job.get("engine") == "video":
        return build_graph_video(job, P, s)
    q = P["quality"][job.get("quality") or "final"]
    ctrl = control_file(job, P)
    w, h = P["framing"][job.get("framing") or "portrait"] if not ctrl else P["framing"]["portrait"]
    if q.get("scale"):  # smaller drafts for slow cards; multiples of 16
        w, h = int(round(w * q["scale"] / 16) * 16), int(round(h * q["scale"] / 16) * 16)
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
    late = build_late_prompt(job, P)
    if late:
        frm = float(P["styles"][job.get("style") or P["default_style"]]["late"]["from"])
        g["44"] = {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": late}, "_meta": {"title": "Prompt for the last steps"}}
        g["45"] = {"class_type": "ConditioningSetTimestepRange", "inputs": {"conditioning": ["4", 0], "start": 0.0, "end": frm}}
        g["46"] = {"class_type": "ConditioningSetTimestepRange", "inputs": {"conditioning": ["44", 0], "start": frm, "end": 1.0}}
        g["47"] = {"class_type": "ConditioningCombine", "inputs": {"conditioning_1": ["45", 0], "conditioning_2": ["46", 0]}}
        g["7"]["inputs"]["positive"] = ["47", 0]
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
                for k in ("images", "videos", "gifs"):
                    imgs += o.get(k, [])
            if imgs or st.get("completed"):
                return imgs
        time.sleep(1.0)
    raise TimeoutError("still not finished after %d s" % timeout)


def new_job(job):
    j = dict(job)
    j.setdefault("style", presets()["default_style"])
    j.setdefault("quality", "draft")  # Preview: detailed enough to judge; remake keepers with gen.py final
    j.setdefault("framing", "auto" if j.get("engine") == "video" else "portrait")
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


def run(job, s=None, on_queued=None, by="claude"):
    """Generate one image. Returns the history record, appended to my/history.jsonl (by="claude", the agent) or to
    my/private/history.jsonl (by="me", the Studio page: private until the user makes it public)."""
    s = s or settings()
    P = presets()
    job = dict(job)
    if by == "claude" and not job.get("round"):
        job["round"] = "claude"
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
           "engine": j.get("engine", "anima"), "images": j.get("images"),
           "style": j.get("engine") if j.get("engine") in ("h3", "video") else j["style"], "character": j.get("character", ""), "body": j["body"], "body_tags": j.get("body_tags"),
           "scene": j.get("scene", ""), "extra_neg": j.get("extra_neg", ""), "quality": j["quality"], "framing": j["framing"],
           "seed": j["seed"], "strength": j.get("strength"), "prompt": build_prompt(j, P), "prompt_late": build_late_prompt(j, P), "negative": build_negative(j, P), "secs": secs,
           "note": j.get("note", ""), "by": by}
    if j.get("engine") == "video":
        V = P["video"]
        rec.update(seconds=round((video_length(j, V) - 4) / V["fps"], 1), resolution=j.get("resolution") or V["default_resolution"],
                   size="%dx%d" % video_size(j, V, s))
    append_jsonl(PHIST if by == "me" else HIST, rec)
    return rec


def output_path(rel, s=None):
    s = s or settings()
    return os.path.join(s["data_dir"], "outputs", rel.replace("/", os.sep))


def feedback(file, rating=None, note=None, who="friend"):
    """A rating / note. On one of the user's own Studio pictures it goes to my/private/ like the picture."""
    rec = {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "file": file, "rating": rating, "note": note or "", "by": who}
    append_jsonl(PFEED if file in studio_files() else FEED, rec)
    return rec


def latest_feedback(private=True):
    """file -> latest {rating, note}. private=False leaves out the ratings on private Studio pictures (for the agent)."""
    out = {}
    recs = read_jsonl(FEED)
    if private:
        recs += read_jsonl(PFEED)
    else:
        pub = library()["public"]
        recs += [r for r in read_jsonl(PFEED) if r.get("file") in pub]
    for r in recs:
        cur = out.setdefault(r["file"], {"rating": None, "note": ""})
        if r.get("rating") is not None:
            cur["rating"] = None if r["rating"] == "none" else r["rating"]
        if r.get("note"):
            cur["note"] = r["note"]
    return out


# ---- privacy and trash -------------------------------------------------------------------------------------------

def norm(rel):
    rel = str(rel or "").replace("\\", "/")
    return rel[4:] if rel.startswith("out:") else rel


def library():
    d = load_json(LIB, {}) or {}
    for k in ("public", "trash", "deleted"):
        d.setdefault(k, {})
    return d


def save_library(d):
    with WLOCK:
        tmp = LIB + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=1, ensure_ascii=False, sort_keys=True)
        os.replace(tmp, LIB)


def studio_files():
    return {r["file"] for r in read_jsonl(PHIST) if r.get("file")}


def is_studio_record(r):
    """Made on the Studio page (or pasted into it). Records from before the privacy split have no "by": the page always
    used the round "studio" (gen.py one did too then; those count as the user's, the safe side)."""
    if r.get("by"):
        return r["by"] == "me"
    f = r.get("file") or ""
    return r.get("round") == "studio" or f.startswith(("studio/", "uploads/"))


def visibility(rel, lib=None, sfiles=None):
    """"claude" (the agent made it), "public" (the user's, shared with the agent) or "private" (the user's)."""
    rel = norm(rel)
    lib = lib or library()
    if rel in lib["public"]:
        return "public"
    sfiles = studio_files() if sfiles is None else sfiles
    if rel in sfiles:
        return "private"
    if rel.startswith(("uploads/", "studio/")) and rel not in {r.get("file") for r in read_jsonl(HIST)}:
        return "private"  # a Studio file without a record (the safe side)
    return "claude"


def is_private(ref, s=None):
    """True for a private Studio picture, given as out:<rel>, <rel> or a path inside the outputs folder."""
    ref = str(ref)
    if os.path.isabs(ref) or re.match(r"^[A-Za-z]:", ref):
        data = (s or settings()).get("data_dir", "")
        out = os.path.normcase(os.path.abspath(os.path.join(data, "outputs")))
        p = os.path.normcase(os.path.abspath(ref))
        if p.startswith(os.path.normcase(os.path.abspath(os.path.join(data, "inputs"))) + os.sep):
            return True  # the engine's staged copies of edit / video inputs (pasted pictures among them)
        if not p.startswith(out + os.sep):
            return False
        ref = p[len(out) + 1:]
    return visibility(ref) == "private"


def split_private():
    """Move the user's Studio records (and their ratings) out of my/history.jsonl and my/feedback.jsonl into my/private/.
    Runs when the page server starts; prints nothing about them. Returns how many records moved."""
    with WLOCK:
        hist = read_jsonl(HIST)
        mine = [r for r in hist if is_studio_record(r)]
        up = os.path.join(settings().get("data_dir", ""), "outputs", "uploads")
        known = studio_files() | {r.get("file") for r in mine}
        for fn in sorted(os.listdir(up)) if os.path.isdir(up) else []:  # pasted before they were recorded
            if "uploads/" + fn not in known and os.path.splitext(fn)[1].lower() in (".png", ".jpg", ".jpeg", ".webp"):
                t = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(os.path.getmtime(os.path.join(up, fn))))
                mine.append({"time": t, "file": "uploads/" + fn, "round": "uploads", "name": fn, "engine": "upload", "by": "me"})
        if not mine:
            return 0
        for r in mine:
            r.setdefault("by", "me")
        moved = {r.get("file") for r in mine}
        fb = read_jsonl(FEED)
        os.makedirs(PRIVATE, exist_ok=True)
        write_jsonl(PHIST, read_jsonl(PHIST) + mine)
        write_jsonl(PFEED, read_jsonl(PFEED) + [r for r in fb if r.get("file") in moved])
        write_jsonl(HIST, [r for r in read_jsonl(HIST) if not is_studio_record(r)])  # re-read: gen.py may have appended
        write_jsonl(FEED, [r for r in read_jsonl(FEED) if r.get("file") not in moved])
        return len(mine)


def add_upload(rel):
    """A picture pasted / dropped into the page: the user's, private like their Studio pictures."""
    append_jsonl(PHIST, {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "file": rel, "round": "uploads", "name": os.path.basename(rel),
                         "engine": "upload", "by": "me"})


def set_public(files, public):
    """Share the user's pictures with the agent, or take them back. The agent's own pictures are always known to it."""
    with WLOCK:
        lib, sf, n = library(), studio_files(), 0
        for f in map(norm, files):
            if f not in sf:
                continue
            if public and f not in lib["public"]:
                lib["public"][f] = time.strftime("%Y-%m-%d %H:%M:%S")
                n += 1
            elif not public and lib["public"].pop(f, None):
                n += 1
        save_library(lib)
        return n


def trash(files, restore=False):
    with WLOCK:
        lib, n = library(), 0
        for f in map(norm, files):
            if restore:
                n += bool(lib["trash"].pop(f, None))
            elif f not in lib["trash"]:
                lib["trash"][f] = time.strftime("%Y-%m-%d %H:%M:%S")
                n += 1
        save_library(lib)
        return n


def delete_forever(files, s=None):
    """Delete pictures that are in the trash: the file (and its frame strip / staged copy) is removed from the PC.
    The user's own records and ratings go too; the agent's record stays in its notebook, marked deleted."""
    s = s or settings()
    with WLOCK:
        lib = library()
        files = [f for f in map(norm, files) if f in lib["trash"]]
        if not files:
            return 0
        sf = studio_files()
        for f in files:
            p = output_path(f, s)
            extra = [os.path.splitext(p)[0] + "_frames.jpg"]
            staged = os.path.join(s["data_dir"], "inputs", "studio", os.path.basename(p))
            if os.path.isfile(p) and os.path.isfile(staged) and os.path.getsize(staged) == os.path.getsize(p):
                extra.append(staged)
            for x in [p] + extra:
                try:
                    os.remove(x)
                except OSError:
                    pass
            lib["trash"].pop(f, None)
            lib["public"].pop(f, None)
            if f not in sf:
                lib["deleted"][f] = time.strftime("%Y-%m-%d %H:%M:%S")
        gone = set(files)
        if gone & sf:
            write_jsonl(PHIST, [r for r in read_jsonl(PHIST) if r.get("file") not in gone])
            write_jsonl(PFEED, [r for r in read_jsonl(PFEED) if r.get("file") not in gone])
        save_library(lib)
        return len(files)


def all_records():
    """Every picture for the page (the user's browser): agent's and user's, newest first, with rating, note, who made
    it, public and trashed flags. Never for the agent: it would show private prompts."""
    lib = library()
    fb = latest_feedback()
    recs = [dict(r, by="claude") for r in read_jsonl(HIST)] + [dict(r, by="me") for r in read_jsonl(PHIST)]
    recs.sort(key=lambda r: r.get("time", ""))
    out = []
    for r in recs:
        f = r.get("file")
        if not f or f in lib["deleted"]:
            continue
        r.update(fb.get(f, {}))
        r["public"] = r["by"] == "claude" or f in lib["public"]
        r["trashed"] = f in lib["trash"]
        out.append(r)
    return list(reversed(out))


KINDS = {"anima": "picture", "upload": "pasted picture"}


def kind(r):
    e = r.get("engine", "anima")
    if e == "h3":
        return "H3 edit" if r.get("images") else "H3 picture"
    if e == "video":
        return "video from a picture" if r.get("images") else "video"
    return KINDS.get(e, e)
