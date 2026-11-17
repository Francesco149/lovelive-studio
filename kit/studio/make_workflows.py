"""make_workflows.py: writes the ready-made ComfyUI editor workflows into kit/workflows/ (setup copies them into ComfyUI).

  kit\\py.cmd kit\\studio\\make_workflows.py            (ComfyUI running: reads node definitions from it)
  python3 kit/studio/make_workflows.py --object-info kit/workflows/object_info.json   (anywhere, from a saved copy)

Each workflow keeps the Love Live style in grey "don't change" boxes and gives the friend pink boxes to edit:
character, body tags, scene, things to avoid. Rebuild after changing presets.json's ll_tv template.
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ui_workflow  # noqa: E402

KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(KIT, "workflows")

HELP = """## Love Live Studio - ComfyUI version

Same recipe as the Studio page, laid out so you can see every piece.

**Edit only the pink boxes:**
- **Character**: who she is (hair, eyes, clothes, face details). Tags, separated by commas.
- **Body tags**: words for the body type. Keep them matching the body drawing.
- **Scene**: where she is, what she does, the framing (`full body`, `cowboy shot`, `upper body`).
- **Avoid**: things you don't want.

The grey boxes hold the Love Live style (`year 2016, anime screenshot, @murota yuuhei`). Leave them alone unless a guide recipe says otherwise.

**Body drawing** (yellow group): pick a grey picture in *Load Image* (`studio/...`). *strength* 0.6 is the tested value: higher copies the drawing more, lower gives the prompt more say. Select the group's three nodes and press **Ctrl+B** to switch the drawing off (tags only).

Press **Run** (or Ctrl+Enter). New seed each run: set *control after generate* on the sampler to *randomize*.
"""


def strbox(text, title):
    return {"class_type": "PrimitiveStringMultiline", "inputs": {"value": text}, "_meta": {"title": title}}


def concat(a, b, title="join"):
    return {"class_type": "StringConcatenate", "inputs": {"string_a": [a, 0], "string_b": [b, 0], "delimiter": ", "}, "_meta": {"title": title}}


def graph(presets, body=True, example=None):
    st = presets["styles"]["ll_tv"]["template"]
    head, rest = st.split("{character}")
    artist = rest.split("{body}")[0].strip(" ,")
    ex = example or presets["examples"][1]
    b = presets["bodies"].get(ex.get("body", "none"), presets["bodies"]["none"])
    q = presets["quality"]["final"]
    g = {
        "s1": strbox(head.strip(" ,"), "Style start (don't change)"),
        "s2": strbox(ex["character"], "Character  (edit me)"),
        "s3": strbox(artist, "Style artist (don't change)"),
        "s4": strbox(b.get("tags", ""), "Body tags  (edit me)"),
        "s5": strbox(ex["scene"], "Scene  (edit me)"),
        "neg": strbox(presets["negative"], "Avoid  (edit me)"),
        "c1": concat("s1", "s2"), "c2": concat("c1", "s3"), "c3": concat("c2", "s4"), "c4": concat("c3", "s5"),
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": q["model"], "weight_dtype": "default"}, "_meta": {"title": "Image model"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": presets["text_encoder"], "type": "stable_diffusion", "device": "default"}, "_meta": {"title": "Text encoder"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": presets["vae"]}, "_meta": {"title": "VAE"}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": ["c4", 0]}, "_meta": {"title": "Prompt"}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": ["neg", 0]}, "_meta": {"title": "Negative prompt"}},
        "6": {"class_type": "EmptyLatentImage", "inputs": {"width": 832, "height": 1248, "batch_size": 1}, "_meta": {"title": "Size (keep 832x1248 with a body drawing)"}},
        "7": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "positive": ["4", 0], "negative": ["5", 0], "latent_image": ["6", 0], "seed": 1,
              "steps": q["steps"], "cfg": q["cfg"], "sampler_name": q["sampler"], "scheduler": q["scheduler"], "denoise": 1.0}, "_meta": {"title": "Sampler"}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["3", 0]}},
        "9": {"class_type": "SaveImage", "inputs": {"images": ["8", 0], "filename_prefix": "comfyui/ll"}},
    }
    if body:
        ctrl = b.get("control") or "average_idol.png"
        g["21"] = {"class_type": "ModelPatchLoader", "inputs": {"name": presets["control"]["adapter"]}, "_meta": {"title": "Body drawing adapter"}}
        g["22"] = {"class_type": "LoadImage", "inputs": {"image": "studio/" + ctrl}, "_meta": {"title": "Body drawing (grey picture)"}}
        g["23"] = {"class_type": "AnimaLLLiteApply", "inputs": {"model": ["1", 0], "model_patch": ["21", 0], "image": ["22", 0],
                   "strength": presets["control"]["strength"], "start_percent": 0.0, "end_percent": presets["control"]["end"]}, "_meta": {"title": "Body drawing"}}
        g["7"]["inputs"]["model"] = ["23", 0]
    return g


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--object-info", help="saved object_info.json instead of asking the running ComfyUI")
    a = ap.parse_args()
    if a.object_info:
        ui_workflow.preload(a.object_info)
    P = json.load(open(os.path.join(KIT, "presets.json"), encoding="utf-8"))
    os.makedirs(OUT, exist_ok=True)
    note = [(-490, 0, 440, 980, HELP)]
    for name, body, ex in (("Love Live - body drawing", True, P["examples"][1]), ("Love Live - tags only", False, P["examples"][0])):
        g = graph(P, body, ex)
        wf = ui_workflow.to_ui(g, notes=note, title=name)
        with open(os.path.join(OUT, name + ".json"), "w", encoding="utf-8") as f:
            json.dump(wf, f, indent=1, ensure_ascii=False)
        with open(os.path.join(OUT, "api", name + ".api.json"), "w", encoding="utf-8") if os.path.isdir(os.path.join(OUT, "api")) else open(os.devnull, "w") as f:
            json.dump(g, f, indent=1, ensure_ascii=False)
        print("wrote", name)


if __name__ == "__main__":
    main()
