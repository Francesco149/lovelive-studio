"""gen.py: the agent's command line for the Studio. Run with ComfyUI's embedded Python (kit\\py.cmd does that):

  kit\\py.cmd kit\\studio\\gen.py status
  kit\\py.cmd kit\\studio\\gen.py one --character "1girl, solo, ..." --body curvy --scene "..." [--style ll_tv] [--seed 5]
                                   [--quality draft|final] (default draft = Preview) [--framing portrait|landscape|square] [--strength 0.6] [--round r01] [--name x]
  kit\\py.cmd kit\\studio\\gen.py round r01 jobs.jsonl --title "What we test" [--question "Which face do you like?"]
        jobs.jsonl: one job per line, e.g. {"label": "A: tags only", "name": "a_s1", "character": "...", "body": "none", "seed": 1}
        -> images in <data>\\outputs\\r01\\, a contact sheet r01\\_sheet.jpg, my\\rounds\\r01.json (shown in the Studio's Rounds tab)
  kit\\py.cmd kit\\studio\\gen.py grid r02 --example "Idol on stage" --vary body=curvy_idol,petite_idol,soft_idol --seeds 1,2 --open
  kit\\py.cmd kit\\studio\\gen.py grid r03 --character "1girl, solo, ..." --scene "..." --vary style=ll_tv,ll_soft,ll_90s --vary strength=0.5,0.6
        every combination of the --vary values x seeds, labelled automatically, as a round (same output as "round").
        Start from --example "<title>" (a ready-made prompt) and/or --character/--scene/--body/--style/...; --open shows
        the Rounds tab in the user's browser when it is done. Use this for "try a few for me" requests.
  kit\\py.cmd kit\\studio\\gen.py one --engine h3 --prompt "plain English ..." [--image out:r03/x_00001_.png] [--framing square]
        H3-Image (optional model set "h3"): describe the picture in sentences; --image (up to 2) = Picture 1 / Picture 2 to edit
  kit\\py.cmd kit\\studio\\gen.py one --engine video --prompt "what happens, camera, sound" [--image out:studio/x.png] [--seconds 5]
        [--resolution 480p|720p] [--framing auto|portrait|landscape|square|phone]: H3 video (optional set "video"), an mp4 with
        sound; --image = the first frame (keeps her look; "auto" framing = the picture's shape)
  kit\\py.cmd kit\\studio\\gen.py make-body soft_short --describe "short and soft, round face, about 6 heads tall" --tags "(plump:1.4), (short:1.3)"
        [--pose "..."] [--shot full|cowboy] [--seeds 1,2,3] [--pick N]: H3 draws the body filling the frame, then the pick is turned
        grey, saved as my/controls/<name>.png and added to the body menu (my/presets.json). Without --pick it only makes the
        candidates (round "body-<name>") so the user can choose; run again with --pick N.
  kit\\py.cmd kit\\studio\\gen.py final r03/a_s1_00001_.png [more files] [--round keep]
        remake pictures in Final quality: same seed and settings (Preview is the default; offer this for the ones the user likes)
  kit\\py.cmd kit\\studio\\gen.py frames out:studio/x_00001_.mp4 [--n 6]
        a strip of frames from a clip (<clip>_frames.jpg next to it), to look at a video
  kit\\py.cmd kit\\studio\\gen.py sheet r01           (re)make the contact sheet of a round
  kit\\py.cmd kit\\studio\\gen.py feedback [r01]      the friend's ratings and notes (all, or one round)
  kit\\py.cmd kit\\studio\\gen.py selftest            one small image; checks it is not black / blank (setup and after a reset)
"""
import argparse, json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core  # noqa: E402


def need_engine(s):
    if not core.comfy_up(s):
        sys.exit("ComfyUI is not answering at %s. Start it: powershell -ExecutionPolicy Bypass -File kit\\start.ps1 -NoBrowser" % s["comfy_url"])


def cmd_status(a):
    s = core.settings()
    print(json.dumps({k: s.get(k) for k in sorted(s)}, indent=1, ensure_ascii=False))
    print("ComfyUI up:", core.comfy_up(s))
    h = core.read_jsonl(os.path.join(core.MY, "history.jsonl"))
    print("images made:", len(h), "| last:", h[-1]["file"] if h else "-")


def job_from_args(a):
    j = {k: getattr(a, k, None) for k in ("style", "character", "body", "scene", "seed", "quality", "framing", "strength", "round", "name", "extra_neg", "body_tags", "end", "note", "engine", "prompt", "seconds", "resolution")}
    if getattr(a, "image", None):
        j["images"] = a.image
    return {k: v for k, v in j.items() if v is not None}


def cmd_one(a):
    s = core.settings()
    need_engine(s)
    r = core.run(job_from_args(a), s)
    print(json.dumps(r, ensure_ascii=False))
    print("file:", core.output_path(r["file"], s))


def video_frames(path, n=6):
    """n evenly spaced frames of a clip as PIL images (PyAV ships with the engine; no ffmpeg needed)."""
    import av
    with av.open(path) as c:
        frames = [f.to_image() for f in c.decode(video=0)]
    if not frames:
        return []
    idx = sorted({round(i * (len(frames) - 1) / max(1, n - 1)) for i in range(n)})
    return [frames[i] for i in idx]


def open_picture(path):
    """A picture, or the middle frame of a clip."""
    from PIL import Image
    if path.lower().endswith((".mp4", ".webm", ".mov")):
        fr = video_frames(path, 3)
        if not fr:
            raise OSError("no frames in " + path)
        return fr[len(fr) // 2]
    return Image.open(path)


def cmd_frames(a):
    from PIL import Image
    s = core.settings()
    path = a.file if os.path.isabs(a.file) else core.output_path(a.file[4:] if a.file.startswith("out:") else a.file, s)
    fr = video_frames(path, a.n)
    for im in fr:
        im.thumbnail((480, 480))
    out = Image.new("RGB", (sum(im.width for im in fr) + 4 * (len(fr) - 1), max(im.height for im in fr)), "white")
    x = 0
    for im in fr:
        out.paste(im, (x, 0))
        x += im.width + 4
    dst = os.path.splitext(path)[0] + "_frames.jpg"
    out.save(dst, quality=88)
    print(dst)


def sheet(round_id, items, s=None):
    """Contact sheet: thumbnails with labels, saved as <data>/outputs/<round>/_sheet.jpg."""
    from PIL import Image, ImageDraw, ImageFont
    s = s or core.settings()
    thumbs = []
    for it in items:
        if not it.get("file"):
            continue
        try:
            im = open_picture(core.output_path(it["file"], s)).convert("RGB")
        except OSError:
            continue
        im.thumbnail((360, 540))
        thumbs.append((im, it.get("label") or it.get("name") or ""))
    if not thumbs:
        return None
    cols = min(5, len(thumbs))
    rows = (len(thumbs) + cols - 1) // cols
    cw, ch, lab = 364, 544, 34
    out = Image.new("RGB", (cols * cw, rows * (ch + lab)), "white")
    d = ImageDraw.Draw(out)
    try:
        font = ImageFont.truetype("arial.ttf", 18)
    except OSError:
        font = ImageFont.load_default()
    for i, (im, label) in enumerate(thumbs):
        x, y = (i % cols) * cw, (i // cols) * (ch + lab)
        out.paste(im, (x + (cw - im.width) // 2, y + 2))
        d.text((x + 6, y + ch + 6), "%d. %s" % (i + 1, label[:38]), fill="black", font=font)
    path = core.output_path("%s/_sheet.jpg" % round_id, s)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    out.save(path, quality=88)
    return path


def cmd_round(a):
    s = core.settings()
    need_engine(s)
    rid = "".join(c for c in a.round_id if c.isalnum() or c in "-_")
    meta_path = os.path.join(core.MY, "rounds", rid + ".json")
    meta = core.load_json(meta_path, None) or {"title": a.title or rid, "question": a.question or "", "created": time.strftime("%Y-%m-%d %H:%M"), "items": []}
    if a.title:
        meta["title"] = a.title
    if a.question:
        meta["question"] = a.question
    done = {it["name"] for it in meta["items"]}
    jobs = [json.loads(l) for l in open(a.jobs, encoding="utf-8") if l.strip()]
    for i, j in enumerate(jobs):
        j.setdefault("name", "%02d" % (i + 1))
        if j["name"] in done:
            continue
        j["round"] = rid
        label = j.pop("label", j["name"])
        t0 = time.time()
        try:
            r = core.run(j, s)
        except Exception as e:
            print("FAILED %s: %s" % (j["name"], e), flush=True)
            continue
        meta["items"].append({"name": j["name"], "label": label, "file": r["file"], "job": j, "prompt": r["prompt"], "secs": r["secs"]})
        os.makedirs(os.path.dirname(meta_path), exist_ok=True)
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=1, ensure_ascii=False)
        print("%d/%d %s %.0fs %s" % (i + 1, len(jobs), label, time.time() - t0, r["file"]), flush=True)
    meta["sheet"] = "%s/_sheet.jpg" % rid if sheet(rid, meta["items"], s) else None
    meta["status"] = "waiting for feedback"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=1, ensure_ascii=False)
    print("sheet:", core.output_path(meta["sheet"], s) if meta["sheet"] else "-")
    print("round file:", meta_path)


def cmd_grid(a):
    import itertools
    P = core.presets()
    base = {}
    if a.example:
        ex = [e for e in P["examples"] if e["title"].lower() == a.example.lower()]
        if not ex:
            sys.exit("no example called %r; titles: %s" % (a.example, ", ".join(e["title"] for e in P["examples"])))
        base = {k: v for k, v in ex[0].items() if k not in ("title", "seed")}
    base.update(job_from_args(a))
    base.pop("seed", None)
    axes = []
    for v in a.vary or []:
        k, _, vals = v.partition("=")
        conv = (lambda x: float(x)) if k in ("strength", "end") else (lambda x: x)
        axes.append((k, [conv(x.strip()) for x in vals.split(",") if x.strip()]))
    seeds = [int(x) for x in (a.seeds or "1,2").split(",")]
    jobs = []
    for combo in itertools.product(*[vals for _, vals in axes]) if axes else [()]:
        for sd in seeds:
            j = dict(base, seed=sd)
            parts = []
            for (k, _), val in zip(axes, combo):
                j[k] = val
                parts.append("%s %s" % (k, val) if k in ("strength", "end") else str(val))
            name = "_".join(str(x).replace(" ", "-").replace(".", "") for x in combo) or "base"
            j["name"] = "%s_s%d" % (name[:60], sd)
            j["label"] = "%s s%d" % (", ".join(parts) or "base", sd)
            jobs.append(j)
    rid = "".join(c for c in a.round_id if c.isalnum() or c in "-_")
    jp = os.path.join(core.MY, "rounds", rid + ".jobs.jsonl")
    os.makedirs(os.path.dirname(jp), exist_ok=True)
    with open(jp, "w", encoding="utf-8") as f:
        for j in jobs:
            f.write(json.dumps(j, ensure_ascii=False) + "\n")
    print("%d pictures -> %s" % (len(jobs), jp), flush=True)
    a.jobs = jp
    cmd_round(a)
    if a.open:
        import webbrowser
        webbrowser.open(core.settings().get("studio_url", "http://127.0.0.1:8190") + "/#rounds")


BODY_PROMPT = ("An anime illustration of one girl alone on a plain light grey background. {frame} {body} {pose} She wears a fitted "
               "short-sleeved T-shirt and a pleated skirt, shoulder-length hair. Cel-shaded anime colouring with clear shadows, large "
               "expressive anime eyes. No other people, no objects, no text.")
FRAME = {"full": "She fills the whole picture: the top of her head is near the top edge and her feet are near the bottom edge.",
         "cowboy": "A cowboy shot from the top of her head down to her mid-thighs; she fills the picture."}


def cmd_make_body(a):
    from PIL import Image
    s = core.settings()
    name = "".join(c for c in a.name if c.isalnum() or c in "_-")
    rid = "body-" + name
    seeds = [int(x) for x in (a.seeds or "1,2,3").split(",")]
    pose = a.pose or "A natural relaxed pose in a three-quarter view: weight on one leg, one hand held near her chest, head slightly tilted, looking at the viewer."
    meta = core.load_json(os.path.join(core.MY, "rounds", rid + ".json"), None)
    if a.pick is None:
        need_engine(s)
        jp = os.path.join(core.MY, "rounds", rid + ".jobs.jsonl")
        os.makedirs(os.path.dirname(jp), exist_ok=True)
        with open(jp, "w", encoding="utf-8") as f:
            for sd in seeds:
                f.write(json.dumps({"engine": "h3", "prompt": BODY_PROMPT.format(frame=FRAME[a.shot], body=a.describe, pose=pose),
                                    "seed": sd, "name": "%s_s%d" % (name, sd), "label": "%s, seed %d" % (name, sd)}) + "\n")
        a.round_id, a.jobs, a.title = rid, jp, "Body drawing: " + a.describe[:60]
        a.question = "Which body is right? Tell Claude the number."
        cmd_round(a)
        print("then: gen.py make-body %s --describe ... --tags ... --pick <number>" % name)
        return
    if not meta:
        sys.exit("no candidates yet: run without --pick first")
    it = meta["items"][a.pick - 1]
    im = Image.open(core.output_path(it["file"], s)).convert("L").resize((832, 1248), Image.LANCZOS)
    # remove the head: a drawn face steers the girl's face toward the drawing's face style; with the head band
    # painted in the background grey the face and hair come only from the Love Live prompt (lab round kt11)
    cut = a.head_cut if a.head_cut is not None else (0.16 if a.shot == "full" else 0.32)
    if cut > 0:
        bgc = int(sum(im.crop((0, 0, 20, 20)).getdata()) / 400)
        im.paste(bgc, (0, 0, 832, int(1248 * cut)))
    os.makedirs(os.path.join(core.MY, "controls"), exist_ok=True)
    dst = os.path.join(core.MY, "controls", name + ".png")
    im.save(dst)
    mp = os.path.join(core.MY, "presets.json")
    mine = core.load_json(mp, {}) or {}
    mine.setdefault("bodies", {})[name] = {"label": a.label or name.replace("_", " ").capitalize(),
                                           "tags": core.clean((a.tags or "") + ", " + ("full body" if a.shot == "full" else "cowboy shot")),
                                           "control": "my/" + name + ".png", "made_from": a.describe}
    with open(mp, "w", encoding="utf-8") as f:
        json.dump(mine, f, indent=1, ensure_ascii=False)
    print("body drawing saved:", dst, "| in the Studio's body menu as", mine["bodies"][name]["label"], "(reload the page)")


def cmd_final(a):
    s = core.settings()
    need_engine(s)
    hist = {r["file"]: r for r in core.read_jsonl(os.path.join(core.MY, "history.jsonl")) if r.get("file")}
    for f in a.files:
        f = f.replace("\\", "/")
        f = f[4:] if f.startswith("out:") else f
        r = hist.get(f) or next((v for k, v in hist.items() if k.endswith("/" + f) or k.endswith(f)), None)
        if not r:
            print("not in history:", f)
            continue
        if r.get("engine") in ("h3", "video"):
            print("only Anima pictures have a Final quality (for a sharper clip: gen.py one --engine video --resolution 720p, same seed):", f)
            continue
        j = {k: r[k] for k in ("style", "character", "body", "body_tags", "scene", "extra_neg", "framing", "seed", "strength") if r.get(k) is not None}
        j.update(quality="final", round=a.round or r.get("round") or "studio", name=(r.get("name") or "pic") + "_final")
        out = core.run(j, s)
        print("%s -> %s (%.0f s)" % (r["file"], out["file"], out["secs"]), flush=True)


def cmd_sheet(a):
    meta = core.load_json(os.path.join(core.MY, "rounds", a.round_id + ".json"), None)
    items = meta["items"] if meta else [{"file": r["file"], "label": r["name"]} for r in core.read_jsonl(os.path.join(core.MY, "history.jsonl")) if r.get("round") == a.round_id]
    print(sheet(a.round_id, items))


def cmd_feedback(a):
    fb = core.latest_feedback()
    hist = {r["file"]: r for r in core.read_jsonl(os.path.join(core.MY, "history.jsonl"))}
    labels = {}
    if a.round_id:
        meta = core.load_json(os.path.join(core.MY, "rounds", a.round_id + ".json"), {}) or {}
        labels = {it["file"]: it.get("label") for it in meta.get("items", [])}
    for f, v in fb.items():
        if a.round_id and not f.startswith(a.round_id + "/"):
            continue
        h = hist.get(f, {})
        print(json.dumps({"file": f, "label": labels.get(f), "rating": v["rating"], "note": v["note"], "prompt": h.get("prompt"), "seed": h.get("seed"), "body": h.get("body")}, ensure_ascii=False))


def cmd_selftest(a):
    from PIL import Image, ImageStat
    s = core.settings()
    need_engine(s)
    P = core.presets()
    r = core.run({"character": "1girl, solo, short brown hair, school uniform", "scene": "smile, classroom", "seed": 1, "quality": "final",
                  "framing": "square", "round": "_selftest", "name": "selftest", "note": "selftest"}, s)
    im = Image.open(core.output_path(r["file"], s)).convert("L")
    st = ImageStat.Stat(im)
    mean, sd = st.mean[0], st.stddev[0]
    ok = sd > 12 and 15 < mean < 245
    print(json.dumps({"ok": ok, "secs": r["secs"], "mean": round(mean, 1), "stddev": round(sd, 1), "file": core.output_path(r["file"], s)}))
    sys.exit(0 if ok else 3)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("status")
    o = sp.add_parser("one")
    for k in ("style", "character", "body", "scene", "quality", "framing", "round", "name", "extra_neg", "body_tags", "note"):
        o.add_argument("--" + k.replace("_", "-"), dest=k)
    o.add_argument("--seed", type=int)
    o.add_argument("--engine", choices=["anima", "h3", "video"])
    o.add_argument("--seconds", type=float, help="video: clip length (default 5, max 8)")
    o.add_argument("--resolution", help="video: 480p (default) or 720p")
    o.add_argument("--prompt", help="H3: the picture in plain English")
    o.add_argument("--image", action="append", help="H3: picture to edit / Picture N (a path or out:<round>/<file>)")
    o.add_argument("--strength", type=float)
    o.add_argument("--end", type=float)
    r = sp.add_parser("round")
    r.add_argument("round_id")
    r.add_argument("jobs")
    r.add_argument("--title")
    r.add_argument("--question")
    g = sp.add_parser("grid")
    g.add_argument("round_id")
    g.add_argument("--example")
    for k in ("style", "character", "body", "scene", "quality", "framing", "extra_neg", "body_tags", "note"):
        g.add_argument("--" + k.replace("_", "-"), dest=k)
    g.add_argument("--strength", type=float)
    g.add_argument("--end", type=float)
    g.add_argument("--seed", type=int, help=argparse.SUPPRESS)
    g.add_argument("--round", dest="round", help=argparse.SUPPRESS)
    g.add_argument("--name", dest="name", help=argparse.SUPPRESS)
    g.add_argument("--vary", action="append", help="field=value1,value2 (repeatable)")
    g.add_argument("--seeds", help="comma list, default 1,2")
    g.add_argument("--title")
    g.add_argument("--question")
    g.add_argument("--open", action="store_true")
    mb = sp.add_parser("make-body")
    mb.add_argument("name")
    mb.add_argument("--describe", required=True, help="the body in plain English (proportions in heads work best)")
    mb.add_argument("--tags", help="matching Anima body tags, e.g. (plump:1.4)")
    mb.add_argument("--pose")
    mb.add_argument("--shot", choices=["full", "cowboy"], default="full")
    mb.add_argument("--seeds")
    mb.add_argument("--pick", type=int)
    mb.add_argument("--label")
    mb.add_argument("--head-cut", dest="head_cut", type=float, help="fraction of the height painted out from the top (default 0.16 full, 0.32 cowboy; ~0.42 for a chibi; 0 keeps the head). Check the saved drawing: no face may be left, raised arms should stay")
    mb.add_argument("--open", action="store_true")
    fr = sp.add_parser("frames")
    fr.add_argument("file", help="a clip: out:<round>/<file>.mp4 or a path")
    fr.add_argument("--n", type=int, default=6)
    fi = sp.add_parser("final")
    fi.add_argument("files", nargs="+")
    fi.add_argument("--round", help="put the Final pictures in this round (default: the same round as the Preview)")
    sh = sp.add_parser("sheet")
    sh.add_argument("round_id")
    fb = sp.add_parser("feedback")
    fb.add_argument("round_id", nargs="?")
    sp.add_parser("selftest")
    a = ap.parse_args()
    {"status": cmd_status, "one": cmd_one, "round": cmd_round, "grid": cmd_grid, "make-body": cmd_make_body, "final": cmd_final, "frames": cmd_frames, "sheet": cmd_sheet, "feedback": cmd_feedback, "selftest": cmd_selftest}[a.cmd](a)


if __name__ == "__main__":
    main()
