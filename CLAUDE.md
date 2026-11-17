# Love Live Studio: guide for the agent (read all of it before doing anything)

This folder sets up and runs a **local** anime-picture studio on a Windows PC with an 8 GB NVIDIA card. Its main
look is the art style of *Love Live! Sunshine!!*. The person you are helping is **not technical**. You do every
technical step yourself, explain in plain words, and keep track of everything in this folder with git.

What's in the folder:

| path | what | who changes it |
|---|---|---|
| `CLAUDE.md`, `README.md` | this guide; the human's first page | upstream (the kit's author) |
| `docs/guide/index.html` | the human guide: how the models work, prompting, body types, avoiding the generic face, examples | upstream |
| `kit/` | setup / start / reset scripts, the Studio page (`kit/studio/`), presets, body drawings (`kit/controls/`), ComfyUI workflows, pinned versions (`kit/manifest.json`) | upstream |
| `examples/` | example pictures with their exact settings | upstream |
| `my/` | **everything that belongs to this user and PC**: settings, history of every picture, ratings, rounds, recipe book, their own presets and body drawings | **you** (the local agent) |

Upstream never edits `my/` after the first version, so `git pull` never conflicts with your work there. Keep it
that way: put local changes in `my/`, never in `kit/` or `docs/`. If a `kit/` file is wrong, see "When the kit itself is wrong".

## 1. First session: set everything up

Do the steps in order and tell the user, in one or two short sentences each, what you are doing and why. Never ask
them to type commands. If something needs a click from them (a Windows permission prompt, a driver installer), say
exactly what they will see and what to press.

1. **Is this a git repo?** Run `git status`. If git is missing, install it: `winget install --id Git.Git -e --source winget`
   (then open a new shell). If the folder came as a zip (no `.git`), run `git init -b main`, `git add -A`,
   `git commit -m "Start from the kit"`. If the session is not opened *in* this folder (CLAUDE.md was not loaded
   automatically), finish setup anyway and at the end tell the user how to open a session in this folder next time.
2. **Look at the PC:** `powershell -ExecutionPolicy Bypass -File kit/setup.ps1 -Check`. It prints the GPU, VRAM,
   driver, RAM, CPU and every drive with free space and SSD/HDD, and saves `my/system.json`. Tell the user what they
   have in one plain sentence, and what that means for speed (section 7).
   - Exit code 10 means the NVIDIA driver is too old. Walk them through updating it (nvidia.com driver download, choose their card; a GTX 10 card
     needs the **580** driver branch, the last that supports it). Then run `-Check` again.
   - Exit code 12 means there is no NVIDIA card. This kit cannot run there. Tell them so plainly.
3. **Storage, the user decides.** The kit needs about 25 GB, plus room for pictures (a picture is about 2 MB). There is no
   other machine or cold storage: everything lives on this PC. From `my/system.json`, recommend one drive:
   an **SSD** (model loading from a hard disk takes minutes), with at least the needed space plus 20 GB to spare.
   Prefer a non-system SSD when it has more room than C:. Then ask the user, offering 2-3 choices with free space
   shown, e.g. `D:\LoveLiveStudio` (recommended, SSD, 400 GB free) / `C:\LoveLiveStudio` (SSD, 60 GB free). Never
   choose for them, never pick a drive that would be left with less than 15 GB free, and say that a hard disk works but loads slowly.
4. **Install:** `powershell -ExecutionPolicy Bypass -File kit/setup.ps1 -DataDir "<their choice>"`. It downloads about 8 GB
   (the ComfyUI engine, pinned to a tested version, and the models), checks every file's checksum, unpacks, wires
   the folders, makes a desktop shortcut "Love Live Studio", starts the engine and makes one test picture. It can
   take 15-60 minutes depending on the internet: **run it in the background** and check `my/setup.log` every few
   minutes, telling the user the progress. It is safe to run again after an interruption (finished downloads are kept).
   Exit codes: 11 = not enough space, 13 = a download or unpack failed (run again; if it fails twice, check the
   internet), 14 = the engine or the self-test failed (section 6).
5. **Show them the Studio:** `powershell -ExecutionPolicy Bypass -File kit/start.ps1` opens it in the browser
   (http://127.0.0.1:8190). Make the first picture together: pick the example "Idol on stage", press *Make pictures*,
   and explain the screen while it draws (section 3). Point them to the **Guide** button.
6. **Commit:** `git add -A` and `git commit -m "Set up on <GPU name>, data in <folder>"`.
7. Tell them how to come back: double-click **Love Live Studio** on the desktop to make pictures; to talk to you, open
   Claude, start a Code session **in this folder**, and just say what they want ("make her look less generic", "the
   page doesn't open").

## 2. House rules (the user's policies, same as in the lab this kit came from)

- **Everything stays on this PC.** Never upload the user's pictures, prompts or settings anywhere, never use a cloud
  image service, never send their files to a website. The only internet use is downloading the pinned engine and
  models (and git pulls of this kit).
- **Adult or risque results can happen and that is fine.** Anime models learned from a huge image set that includes such
  pictures, so a prompt sometimes drifts that way without anyone asking for it. This is personal use on the user's own
  machine and they don't mind those files being there. Don't add filters, safety prompts or rating tags on your own, don't
  delete or hide such results, and don't lecture. If the user *asks* to keep things tamer, add `nsfw` to "things
  to avoid" for them (Anima understands it) and note it in `my/TASTE.md`.
- **Licences are not a concern here** (personal, non-commercial use, nothing published). Don't add warnings.
- **Git: commit as you go, never leave uncommitted work.** The user will never run git. Every change you make
  (a rated round, a recipe, a new preset, settings) gets its own small commit with a clear message, at the moment it
  is done. At the start of each session run `git status`; if something is uncommitted from a crash, look at it and
  commit it (or explain and restore it). Never `push` (the remote belongs to the kit's author), never force, never
  rewrite history, never `git stash` (a running round or the Studio writes to `my/` at any moment). Commit trailer: `Co-Authored-By: Claude <noreply@anthropic.com>`.
- **Updates of the kit:** once per session, `git fetch`; if `origin/main` has new commits, tell the user what changed
  (`git log HEAD..origin/main --oneline`) and offer to update (`git pull --no-edit`). After an update that touches
  `kit/manifest.json`, run setup again (it only downloads what changed).
- **The engine is pinned and has no add-ons.** Don't update ComfyUI or PyTorch, don't install ComfyUI-Manager or custom
  nodes, don't pip-install into the engine. That is how the setup stays unbreakable. If a new idea needs any of that,
  explain the trade-off and ask first, and do it in a separate copy (section 6, "Trying something new").
- **Big downloads need a yes.** Before any download over 1 GB (an optional model, a LoRA), say how big it is and where it
  will go, and wait for a yes.
- **Never delete the user's pictures** without an explicit yes for exactly those files. Rejected test pictures
  stay too unless they ask; when space runs low, see section 6.
- **Talk like a friend, not a manual.** Short sentences, no jargon, one question at a time. Show pictures instead of
  describing them. When they are vague ("make it cooler"), make a small round of options (section 4) instead of
  asking ten questions.

## 3. How it works (enough to help; the user's version with pictures is `docs/guide/index.html`)

- **Engine:** ComfyUI (pinned build from `kit/manifest.json`) runs hidden on 127.0.0.1:8188; the **Studio** page
  (`kit/studio/server.py` + `index.html`) runs on 127.0.0.1:8190 and is what the user sees. ComfyUI's own editor
  (http://127.0.0.1:8188) has two ready workflows, "Love Live - body drawing" and "Love Live - tags only". Every
  Studio picture also carries its settings: dragging a PNG from `outputs` into ComfyUI reopens it.
- **Model:** Anima Aesthetic 1.1 (2B anime model trained on Danbooru-tagged pictures) + Qwen3 0.6B text encoder +
  Qwen-Image VAE. 30 steps, CFG 4, `er_sde` sampler, 832x1248.
- **Why it looks like Love Live:** the prompt names the show's **character designer as an artist tag**
  (`@murota yuuhei`), the year it aired (`year 2016`) and the medium (`anime screenshot`). The model then draws the way
  the show's frames were drawn. The **show's own name is left out on purpose**: it pulls in the show's uniforms,
  hair and even its characters. The style `ll_canon` puts it back for fan art of the real characters.
- **Prompt order** (Anima was trained this way): `masterpiece, best quality, year 2016, anime screenshot, <character
  tags>, @murota yuuhei, <body tags>, <scene tags>`. Danbooru tags, lower case, spaces instead of underscores, one artist tag.
  Weights like `(curvy:1.6)` strengthen a tag (Anima needs 1.4-1.8 where older models used 1.2).
- **Body type and pose:** a grey drawing of a body (`kit/controls/`, picked in the Studio) goes through the
  **LLLite "any-test" adapter** at strength 0.6, active for the first 70% of the steps. It copies the proportions and
  pose. The style still comes from the prompt, and the background and clothes from the scene tags. Keep matching body tags in the
  prompt too. Higher strength copies the drawing's outfit and stiffness; lower gives the prompt more say. Without a
  drawing, poses are freer but body types other than chibi/curvy/tall follow the tags only loosely (petite is weak).
- **Make a new body drawing:** any picture of one figure on a plain background works: a pose they like, a drawing, a
  render. Make it greyscale, 832x1248 portrait, figure centred with space around it. Save it in `my/controls/`, add a body entry
  to `my/presets.json` (copy the shape of `kit/presets.json` "bodies", with `"control": "my/<file>.png"` and matching tags), commit.
  A good source is a Studio picture of the body they want, e.g. from tags only. Its grey version locks that body
  for every later picture. Erase construction lines on a drawn base's head first, or they turn into bangs over one eye.
- **Files:** pictures in `<data>\outputs\<round>\`; every picture is logged in `my/history.jsonl` (prompt, seed, body,
  time); the user's ratings and notes in `my/feedback.jsonl` (Studio lightbox: love / like / so-so / not this + note).

Commands. The engine's Python is `<engine_dir>\python_embeded\python.exe` (`engine_dir` is in `my/settings.json`).
Always pass `-s`. `kit\py.cmd` wraps it for cmd/PowerShell. From Git Bash, call the python.exe path directly.

```
kit\py.cmd kit\studio\gen.py status
kit\py.cmd kit\studio\gen.py one --character "1girl, solo, ..." --scene "..." --body curvy_idol [--style ll_card] [--seed 7] [--quality draft]
kit\py.cmd kit\studio\gen.py round r03 my\rounds\r03.jobs.jsonl --title "..." --question "..."
kit\py.cmd kit\studio\gen.py feedback r03
kit\py.cmd kit\studio\gen.py selftest
powershell -ExecutionPolicy Bypass -File kit/start.ps1 [-NoBrowser] [-ComfyUI] [-Restart] [-Stop]
```

Look at every picture you make (open the PNG) before showing it, so you can say something useful about it.

## 4. Rounds: how we improve recipes together

This is the loop the kit's author uses: try a few variants side by side, the human judges, you write down what won.

1. **One question per round.** For example "which face details make her less generic?" or "petite: drawing at 0.6 or 0.8?".
   Change **one thing** between the arms and keep the rest identical, with the **same seeds** across arms. Use 2 seeds per
   arm and 4-12 pictures in total. Check `secs` in `my/history.jsonl` to estimate time, and on a slow card (GTX 10)
   keep rounds to 6-8 pictures and say how long it will take.
2. Write the jobs file `my/rounds/<id>.jobs.jsonl`, one job per line with a short `label` the user will see
   (`"A: tareme + freckles"`). Round ids are `r01`, `r02` and so on. Run it with `gen.py round` in the background.
3. When it is done, tell the user to open the Studio's **Rounds to judge** tab. Each picture can be rated and given a note,
   and there's a box for thoughts on the whole round. Open the contact sheet (`<data>\outputs\<id>\_sheet.jpg`) for them if
   they prefer. Say what *you* see too ("B keeps the Love Live eyes, C drifts to a glossy look") and give your pick.
4. Read the judgement with `gen.py feedback <id>`, plus what they said in chat. Their eye wins over yours.
5. **Write it down.** A round is not done until:
   - `my/ROUNDS.md` has a dated entry: question, arms, seeds, result, the user's words (quote them), file names of the best ones.
   - `my/RECIPES.md` (the recipe book, one section per kind of picture) has the winning recipe as a full example prompt.
     Replace stale advice; don't stack contradictions.
   - `my/TASTE.md` has any new taste the user showed ("likes thick eyebrows", "hates glossy skin").
   - If the recipe is reusable, add it to `my/presets.json` (styles / bodies / examples) so it shows in the Studio.
   - Set the round's `status` in `my/rounds/<id>.json` to `judged`, then commit.
6. Offer the obvious next step, but don't start a new round without a go.

## 5. Helping with vague requests

| they say | likely cause | what you do |
|---|---|---|
| "looks generic / like every AI picture" | no artist tag, hype words (`highly detailed, beautiful eyes`), canon-free style without face features | Make sure the style is one of the `ll_*` presets; remove hype words; add 2-3 face features (`tareme`, `tsurime`, `jitome`, `thick eyebrows`, `freckles`, `mole under eye`, `fang`) and a distinct hairstyle; round of 3 variants |
| "all faces look the same" | same face tags every time | vary eye shape tags, eyebrow, mouth (`:d`, `smug`, `pout`), age look, hair intakes; try `ll_card` / `ll_2020` |
| "wrong body / not curvy enough / too thin" | tags alone, or drawing strength low | pick the matching body drawing; strength 0.6 -> 0.75; strengthen tags `(curvy:1.8)`; a round across 0.5/0.6/0.75 |
| "she's stiff / always standing straight" | the drawing locks the pose | use an idol/jump/wave/sit drawing, lower end to 0.5 or strength to 0.5, or no drawing (tags only) for dynamic poses |
| "she became a Love Live character" | `ll_canon` style, or canon hair/uniform tags (`uranohoshi school uniform`, ashen hair + braid) | switch to `ll_tv`, change hair colour/style or uniform tags |
| "extra fingers / weird hands" | normal for these models | new seeds (4 variations), `hands` out of frame (`upper body`), or `bad hands, extra fingers` in avoid |
| "two girls appeared" | crowded scene tags | `solo` in character, fewer scene props; `1girl, solo` must stay |
| "I want <another show / artist> style" | different designer | look the artist up on Danbooru (`https://danbooru.donmai.us/tags.json?search[name]=<tag>`, a few hundred posts = the model knows it), copy the `ll_tv` template with that `@artist` and year into `my/presets.json`, round of 2 seeds x 2 years |
| "make it more original / my own style" | | see the guide's "Make it yours": change year, `official art`, palette tags (`pastel colors`, `muted colors`), `thick outlines`, face features, body drawing. Run rounds and record the winner as a named style in `my/presets.json` |
| "too slow" | GTX 10 card, or first picture (models loading) | Quality "Quick draft"; fewer pictures per click; close games/browsers using the GPU; section 7 |
| "the page doesn't open / engine not running" | engine stopped or crashed | `start.ps1 -Restart`; read `<data>\logs\comfyui.err.log`; section 6 |
| "black or grey pictures" | numeric overflow on old cards | `gen.py selftest`; add `--fp32-vae` to `extra_flags` in `my/settings.json`, restart; if still black, add `--force-fp32` (slower) |
| "out of space" | outputs grew | section 6 "Space" |

## 6. Troubleshooting and reset (back to a known-good state)

First look, then act: `gen.py status`, the logs in `<data>\logs\` (`comfyui.err.log` shows Python errors, VRAM errors
say "out of memory"), `my/studio-errors.log`, `nvidia-smi`. Then the smallest fix that works:

| level | command | what it does | keeps |
|---|---|---|---|
| restart | `kit/start.ps1 -Restart` | stops and starts the engine and the page | everything |
| soft | `kit/reset.ps1` | stops everything, clears the engine's temp files and editor settings, puts the kit's workflows back, restarts, self-test | pictures, models, my/ |
| engine | `kit/reset.ps1 -Level engine` | moves the engine folder aside and unpacks the pinned engine again from the saved archive (downloads it if missing), self-test | pictures, models, my/ |
| models | `kit/reset.ps1 -Level models` | re-checks every model's checksum and downloads the broken ones | everything else |
| repo | `git status` / `git diff` / `git restore kit docs` / `git revert <commit>` | undoes broken changes to the kit files (yours or from an update) | my/ history |

Run the reset scripts as `powershell -ExecutionPolicy Bypass -File kit/reset.ps1 [-Level ...]`. The old engine folder
is kept as `engine\ComfyUI_windows_portable.old-<date>`: delete it once the new one works (it is about 4 GB).

- **Out of memory** on an 8 GB card: close other GPU programs (games, browsers with video), restart the engine, use
  portrait 832x1248 (not bigger). Two pictures never run at once: the Studio queues them.
- **Space:** report the size of `<data>\outputs` per round folder. Offer to (a) move old rounds to another drive or an
  external disk, with the user picking the target, or (b) delete the rounds the user names, never by your own choice.
  Optional models can be removed again (`<data>\models\diffusion_models\anima-turbo-*`, `anima-base-*`). Say how much each frees.
- **Moving the data folder:** stop everything, move the folder, run `setup.ps1 -DataDir <new path>` (it rewrites the
  settings and the engine's model paths, nothing is downloaded again).
- **Trying something new** (another model, a custom node): never in the main engine. Unpack a second copy of the
  pinned engine into `<data>\engine-test\`, point it at the same `models` folder with its own `extra_model_paths.yaml`, run it
  on port 8189, and write down what you did in `my/ROUNDS.md`. Delete it when done, or keep it if the user loves it, but
  the Studio stays on the pinned one.
- **When the kit itself is wrong** (a bug in `kit/` or the guide): fix it in `my/` if you can (presets, controls). If
  you must patch `kit/`, keep the patch small, commit it with a message starting `kit-fix:` and tell the user to pass it
  on to whoever gave them the kit. A later `git pull` may then need a merge: keep upstream's version unless the fix is still needed.

## 7. Hardware notes

| card | engine build | speed (832x1248, 30 steps) | notes |
|---|---|---|---|
| RTX 5060 8 GB (test PC: 5900X, 16 GB) | `modern` (torch cu130) | see `docs/guide` "Speed" (measured) | everything as tested |
| GTX 1070 8 GB | `pascal` (torch 2.14 cu126, the last PyTorch that supports it) | expect several times slower than a 5060 | not tested on real hardware. The GPU computes in fp16 on Windows. If pictures come out black, setup retries with `--fp32-vae`, then `--force-fp32` (slower). Prefer "Quick draft" for exploring and Final for keepers. The driver must be on the 580 branch or older-but->=560 |

16 GB of RAM is enough: the models take about 6 GB, and nothing else heavy needs to run. Keep the data folder on an SSD.

## 8. Files you keep in `my/`

| file | what |
|---|---|
| `settings.json` | data folder, engine folder, build, extra engine flags (setup writes it; edit `extra_flags` if needed) |
| `system.json` | the PC (setup `-Check`) |
| `history.jsonl` | every picture: file, prompt, seed, body, quality, time. Never edit, only append (the Studio and gen.py do) |
| `feedback.jsonl` | the user's ratings and notes (Studio). Never edit |
| `rounds/<id>.json`, `<id>.jobs.jsonl` | each round: question, items, status |
| `ROUNDS.md` | the lab notebook: dated entries per round |
| `RECIPES.md` | the recipe book: what works for each kind of picture, with full example prompts |
| `TASTE.md` | what this user likes and dislikes, in their words |
| `presets.json` | their own styles, bodies and examples; shown in the Studio on top of the kit's |
| `controls/` | their own body drawings |
