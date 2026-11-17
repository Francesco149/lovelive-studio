"""gen.py: the agent's command line for the Studio. Run with ComfyUI's embedded Python (kit\\py.cmd does that):

  kit\\py.cmd kit\\studio\\gen.py status
  kit\\py.cmd kit\\studio\\gen.py one --character "1girl, solo, ..." --body curvy --scene "..." [--style ll_tv] [--seed 5]
                                   [--quality final|draft] [--framing portrait|landscape|square] [--strength 0.6] [--round r01] [--name x]
  kit\\py.cmd kit\\studio\\gen.py round r01 jobs.jsonl --title "What we test" [--question "Which face do you like?"]
        jobs.jsonl: one job per line, e.g. {"label": "A: tags only", "name": "a_s1", "character": "...", "body": "none", "seed": 1}
        -> images in <data>\\outputs\\r01\\, a contact sheet r01\\_sheet.jpg, my\\rounds\\r01.json (shown in the Studio's Rounds tab)
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
    j = {k: getattr(a, k) for k in ("style", "character", "body", "scene", "seed", "quality", "framing", "strength", "round", "name", "extra_neg", "body_tags", "end", "note")}
    return {k: v for k, v in j.items() if v is not None}


def cmd_one(a):
    s = core.settings()
    need_engine(s)
    r = core.run(job_from_args(a), s)
    print(json.dumps(r, ensure_ascii=False))
    print("file:", core.output_path(r["file"], s))


def sheet(round_id, items, s=None):
    """Contact sheet: thumbnails with labels, saved as <data>/outputs/<round>/_sheet.jpg."""
    from PIL import Image, ImageDraw, ImageFont
    s = s or core.settings()
    thumbs = []
    for it in items:
        if not it.get("file"):
            continue
        try:
            im = Image.open(core.output_path(it["file"], s)).convert("RGB")
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
    o.add_argument("--strength", type=float)
    o.add_argument("--end", type=float)
    r = sp.add_parser("round")
    r.add_argument("round_id")
    r.add_argument("jobs")
    r.add_argument("--title")
    r.add_argument("--question")
    sh = sp.add_parser("sheet")
    sh.add_argument("round_id")
    fb = sp.add_parser("feedback")
    fb.add_argument("round_id", nargs="?")
    sp.add_parser("selftest")
    a = ap.parse_args()
    {"status": cmd_status, "one": cmd_one, "round": cmd_round, "sheet": cmd_sheet, "feedback": cmd_feedback, "selftest": cmd_selftest}[a.cmd](a)


if __name__ == "__main__":
    main()
