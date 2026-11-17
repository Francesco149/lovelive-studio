"""server.py: the Studio web page (http://127.0.0.1:8190). Started by kit\\start.ps1 with ComfyUI's embedded Python.

Talks only to the local ComfyUI (127.0.0.1:8188) and to files in this repo / the data folder. Nothing leaves the PC.
Endpoints (JSON):
  GET  /api/state       presets, settings summary, ComfyUI up?, queue
  POST /api/generate    {job..., count}  -> queues `count` images (seed, seed+1, ...)
  GET  /api/jobs        jobs started from this page (queued / running / done / error)
  GET  /api/history     every image (newest first) with its latest rating/note
  POST /api/rate        {file, rating, note}
  GET  /api/rounds      rounds the agent made (folders + my/rounds/*.json)
  GET  /img/<path>      an output image;   /control/<file>  a body control picture;   /guide/...  the guide
"""
import json, mimetypes, os, queue, sys, threading, time, traceback, urllib.parse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
GUIDE = os.path.join(core.ROOT, "docs", "guide")
PORT = int(os.environ.get("STUDIO_PORT", "8190"))

JOBS = []           # dicts: id, job, status, record, error, queued_at
LOCK = threading.Lock()
Q = queue.Queue()   # one image at a time, in the order they were asked for


def worker():
    while True:
        entry = Q.get()
        run_one(entry)


def run_one(entry):
    if True:
        entry["status"] = "running"
        entry["started_at"] = time.time()
        try:
            entry["record"] = core.run(entry["job"])
            entry["status"] = "done"
        except Exception as e:  # shown on the page; the agent reads my/studio-errors.log
            entry["status"] = "error"
            entry["error"] = str(e)
            with open(os.path.join(core.MY, "studio-errors.log"), "a", encoding="utf-8") as f:
                f.write("%s %s\n%s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), json.dumps(entry["job"]), traceback.format_exc()))
        entry["finished_at"] = time.time()


def safe_join(base, rel):
    p = os.path.normpath(os.path.join(base, rel.replace("/", os.sep)))
    if not p.startswith(os.path.normpath(base)):
        raise PermissionError(rel)
    return p


def typical_secs(quality, body):
    """Median time of the last few images of this kind, so the page can say how long to wait."""
    xs = [r["secs"] for r in core.read_jsonl(os.path.join(core.MY, "history.jsonl"))
          if r.get("quality") == quality and (r.get("body") != "none") == (body != "none") and r.get("secs")][-7:]
    return sorted(xs)[len(xs) // 2] if xs else None


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, body, ctype="application/json"):
        if not isinstance(body, (bytes, bytearray)):
            body = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def file(self, path):
        if not os.path.isfile(path):
            return self.send(404, {"error": "not found"})
        with open(path, "rb") as f:
            data = f.read()
        self.send(200, data, mimetypes.guess_type(path)[0] or "application/octet-stream")

    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n).decode() or "{}") if n else {}

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        p = urllib.parse.unquote(u.path)
        try:
            if p in ("/", "/index.html"):
                return self.file(os.path.join(HERE, "index.html"))
            if p == "/api/state":
                s = core.settings()
                P = core.presets()
                mdir = os.path.join(s.get("data_dir", ""), "models", "diffusion_models")
                P["quality"] = {k: v for k, v in P["quality"].items() if os.path.exists(os.path.join(mdir, v["model"]))} or P["quality"]
                return self.send(200, {"presets": P, "comfy_up": core.comfy_up(s),
                                       "machine": {k: s.get(k) for k in ("gpu", "vram_gb", "engine_build", "data_dir")},
                                       "typical": {q: {b: typical_secs(q, b) for b in ("none", "body")} for q in P["quality"]}})
            if p == "/api/jobs":
                with LOCK:
                    out = [{k: v for k, v in e.items()} for e in JOBS[-60:]]
                return self.send(200, out)
            if p == "/api/history":
                fb = core.latest_feedback()
                recs = core.read_jsonl(os.path.join(core.MY, "history.jsonl"))
                for r in recs:
                    r.update(fb.get(r.get("file"), {}))
                return self.send(200, list(reversed(recs)))
            if p == "/api/rounds":
                rounds = []
                d = os.path.join(core.MY, "rounds")
                for fn in sorted(os.listdir(d)) if os.path.isdir(d) else []:
                    if fn.endswith(".json"):
                        r = core.load_json(os.path.join(d, fn), {})
                        r["id"] = fn[:-5]
                        rounds.append(r)
                return self.send(200, list(reversed(rounds)))
            if p.startswith("/img/"):
                return self.file(safe_join(os.path.join(core.settings()["data_dir"], "outputs"), p[5:]))
            if p.startswith("/control/my/"):
                return self.file(safe_join(os.path.join(core.MY, "controls"), p[12:]))
            if p.startswith("/control/"):
                return self.file(safe_join(core.CONTROLS, p[9:]))
            if p == "/guide" or p == "/guide/":
                return self.file(os.path.join(GUIDE, "index.html"))
            if p.startswith("/guide/"):
                return self.file(safe_join(GUIDE, p[7:]))
            if p.startswith("/examples/"):
                return self.file(safe_join(os.path.join(core.ROOT, "examples"), p[10:]))
            return self.send(404, {"error": "not found"})
        except PermissionError:
            return self.send(403, {"error": "forbidden"})
        except Exception as e:
            return self.send(500, {"error": str(e)})

    def do_POST(self):
        p = urllib.parse.urlparse(self.path).path
        try:
            b = self.body()
            if p == "/api/generate":
                if not core.comfy_up():
                    return self.send(503, {"error": "The image engine is not running. Close this page and double-click 'Love Live Studio' again."})
                n = max(1, min(int(b.pop("count", 1) or 1), 12))
                seed = b.get("seed")
                base = int(seed) if seed not in (None, "", -1, "-1") else core.random.randint(1, 2**31 - 1 - n)
                made = []
                for i in range(n):
                    job = dict(b, seed=base + i)
                    e = {"id": "%d-%d" % (int(time.time() * 1000), i), "job": job, "status": "queued", "queued_at": time.time()}
                    with LOCK:
                        JOBS.append(e)
                    Q.put(e)
                    made.append(e["id"])
                return self.send(200, {"queued": made})
            if p == "/api/rate":
                return self.send(200, core.feedback(b["file"], b.get("rating"), b.get("note")))
            if p == "/api/preview":
                return self.send(200, {"prompt": core.build_prompt(b), "negative": core.build_negative(b)})
            return self.send(404, {"error": "not found"})
        except Exception as e:
            return self.send(500, {"error": str(e)})


def main():
    threading.Thread(target=worker, daemon=True).start()
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    print("Love Live Studio on http://127.0.0.1:%d" % PORT, flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
