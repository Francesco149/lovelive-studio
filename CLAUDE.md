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
   On a **GTX 10 card** (setup says build `pascal`), also offer the 4 GB "Turbo sketch" model (`-Optional turbo`): it
   makes rough drafts about 6x faster than Final, which matters on a slow card. It needs a yes like any big download.
   On a newer card (build `modern`) with an SSD and 40+ GB to spare, also offer **H3-Image** (`-Optional h3`, 29 GB):
   plain-English pictures, edits of their pictures, and custom body drawings from a description. Not on a GTX 10 card:
   its 20B model streams from disk and the card has no fast 4-bit maths, so a picture would take far too long.
   On the same kind of PC, also offer **H3 video** (`-Optional video`, 32 GB alone; `-Optional h3,video` together is 46 GB
   because they share the 16 GB text encoder): 3-8 second clips with sound from a description, best started from one of
   their Love Live pictures. Same GTX 10 rule.
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
- **The user's own pictures are private** (section 3, "Private pictures"). What they make on the Studio page (pictures,
  H3 edits, videos, and pictures they paste in) is theirs: don't look at those pictures or their prompts, ratings or
  notes until they make them public in the Studio.
- **Never delete the user's pictures** without an explicit yes for exactly those files. Rejected test pictures
  stay too unless they ask; when space runs low, see section 6. The Studio has a **Trash** (soft delete): the user moves
  pictures there and deletes them for good from its Trash tab. Pictures in the trash are the user's decision: don't
  restore, empty or delete from it yourself; to free space, point them to it.
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
  the show's frames were drawn. The **show's own name** (`love live! sunshine!!`) adds the signature round eyes, eye
  highlights and blush, but over the whole picture it turns any girl into a canon character (silver hair becomes You,
  orange becomes Honoka/Chika, black hime cut becomes Dia; weights and negatives don't stop it, tested).
  So the default style **`ll_signature`** uses the plain prompt for the first 70% of the steps (hair, face shape, outfit
  and body are decided there) and the prompt with the show's name only for the last 30% (eyes, line work, blush). That
  keeps the user's own girl with the show's eyes. Eye colours are weighted up in the late prompt because they can drift
  toward pink. `ll_tv` is the plain look (smaller, more grown-up eyes); `ll_canon` uses the name throughout, for fan art
  of the real characters.
- **Prompt order** (Anima was trained this way): `masterpiece, best quality, year 2016, anime screenshot, <character
  tags>, @murota yuuhei, <body tags>, <scene tags>`. Danbooru tags, lower case, spaces instead of underscores, one artist tag.
  Weights like `(curvy:1.6)` strengthen a tag (Anima needs 1.4-1.8 where older models used 1.2).
- **Body type: words first.** The body menu starts with *words only* bodies (tags with weights, no drawing): the
  model's own idea of the body gives the best shapes (curvy, tall, soft, chibi) and natural poses; this matches the
  kit author's reference batch. Curvy comes young (signature style) or grown-up (`mature female` + the `ll_tv` style:
  older face, fuller figure). Athletic: `athletic, toned, slim, small waist` with `muscular, muscular female, biceps` in
  the body's negative (a `neg` field in presets) so no six-pack; never `abs` or `(toned:1.3)`. Use a **drawing** when
  the pose must be exact, the words don't reach the body (petite in words is gentle: `(petite:1.3), short, small breasts`; heavier weights or `skinny` look starved), or a character must keep the same
  body across pictures. The guide's section 5 shows both side by side with their limits.
- **Body drawing details:** a grey drawing of a body (`kit/controls/`, picked in the Studio) goes through the
  **LLLite "any-test" adapter** at strength 0.6, active for the first 70% of the steps. It copies the proportions and
  pose. The style still comes from the prompt, and the background and clothes from the scene tags. Keep matching body tags in the
  prompt too. Higher strength copies the drawing's outfit and stiffness; lower gives the prompt more say. Without a
  drawing, poses are freer but body types other than chibi/curvy/tall follow the tags only loosely (petite is weak).
  **Drawings have no head**: a drawn face pulls her face toward the drawing's face (narrower, its bangs and tilt), even
  with the drawing released at 40% of the steps (tested), so the head band is painted out in the background grey
  (`make-body` does it; `--head-cut`). Raised-arm poses (the jumps) keep their heads. Check every new drawing: no
  face may be left.
  **The figure must fill the drawing** (head near the top edge, feet near the bottom): a small figure with lots of
  white space makes a small face with small eyes, which loses the Love Live look. The `_cowboy` drawings (thighs up)
  give the biggest faces.
- **Make a new body drawing:** with H3 installed, `gen.py make-body <name> --describe "<body in plain English, height in
  heads>" --tags "<matching Anima tags>"` makes 3 candidates as a round; the user picks one; `--pick N` turns it grey
  and adds it to their body menu. Without H3: any picture of one figure filling a plain background works (a Studio
  picture of the body they like, a drawing, a render): greyscale, 832x1248, save in `my/controls/`, add a body entry to
  `my/presets.json` (shape of `kit/presets.json` "bodies", `"control": "my/<file>.png"`, matching tags), commit. Erase
  construction lines on a drawn base's head first, or they turn into bangs over one eye.
- **H3-Image (optional set `h3`, about 29 GB):** MiniMax's big model, 6 steps, plain-English prompts. Best at body
  proportions in words, poses, scenes with several things going on, and **edits**: "keep the girl from Picture 1 exactly
  as she is drawn ... change only ...", which keeps an Anima Love Live girl's style. On its own its style is generic
  anime, so for Love Live pictures make the girl with Anima first, then edit with H3. Studio: the *Describe (H3)* tab and
  *Edit with H3* in the picture viewer. Speed on 8 GB: section 7.
- **H3 video (optional set `video`, about 32 GB; shares H3-Image's text encoder):** MiniMax H3 FL2VA as Kijai's w4a8
  file + the Pika H3 Flex 6-step LoRA, Comfy Kitchen (int8) attention, 24 fps mp4 with sound. Plain-sentence prompts
  work: what she does, the camera, what we hear (spoken words in quotes with the language). **Start from a picture**
  (first frame) for the Love Live look: it keeps her exactly as drawn; from words alone it is generic anime and may cut
  between shots. Default 480p (shape from the picture), 5 s; 8 s and 720p work on 8 GB / 16 GB RAM (section 7). Offer
  720p (same prompt and seed: a close, sharper clip) only for clips they like. Studio: the *Video (H3)* tab, *Make a
  video from this picture* and *Make it in 720p* in the viewer. Clips are `.mp4` files in the outputs like pictures; the
  contact sheet of a round shows a clip's middle frame; look at a clip with `gen.py frames <clip>` (a strip of 6 frames,
  PyAV from the engine). You can't hear the sound: ask the user how it sounds.
- **Writing video prompts: a script, not a caption** (tested 2026-11-18, guide section 9 "Writing a clip"). H3 makes
  picture and sound together and invents whatever is missing. Talking without given words = **babbling** (fake
  Japanese). Every line written in quotes with its language = **said verbatim** (English and Japanese both checked by
  transcription). Write it in time order:
  1. Who is in it, each named by something visible ("the girl with long red hair", "on the left"); with a first frame
     start "The girl in the picture, in the same 2D anime style".
  2. What each does: one or two actions per 5 s.
  3. Every spoken line: `she says happily in Japanese: "..."`; one short sentence takes 2-3 s, so 5 s holds one or two.
     Several speakers: "First ... says ... Then ... says ...": the lines come out in that order, by the right girls.
  4. Who stays silent: `says nothing; her mouth stays closed` (it works: closed mouth for the whole clip). For a clip
     with no voices at all: `does not speak at all ... No voices.`
  5. Sounds (wind, crowd, footsteps, a bell) and music (`soft piano music`, `upbeat idol pop`) or `No music`: unasked
     music can appear.
  6. Timing when it matters: `0-2 seconds: ... At 2 seconds: ... Until the end: ...` (followed in order).
  Plain sentences work as well as MiniMax's tagged format (`(S1)`, `<d>[Japanese] ...</d>`, same lines and order in the
  test). When the user describes a moment in their words, write the script for them, show it, then make the clip.
  You can't hear the result: ask them whether the voices said the lines and nobody babbled.
- **Files:** pictures in `<data>\outputs\<round>\`; every picture *you* make is logged in `my/history.jsonl` (prompt,
  seed, body, time; `gen.py one` puts them in the round `claude` by default); ratings and notes on your pictures and
  rounds in `my/feedback.jsonl` (Studio lightbox: love / like / so-so / not this + note). `my/library.json` says which of
  the user's pictures are public and which pictures are in the trash (file names only).
- **Private pictures.** Everything the user makes on the Studio page (Create, H3 edits, videos, "Final quality" and
  "variations" buttons) and every picture they paste or drop into it is **private by default**: its record and ratings
  live in `my/private/` (not in git), the files in `<data>\outputs\studio\` and `<data>\outputs\uploads\`.
  You see one only after the user makes it public (*My pictures*: open it and press *Let Claude see it*, or *Select* several).
  - The only way you look at them: `gen.py studio`. It prints the public ones in full (file, path, prompt, rating, note)
    and the private ones as time + kind only ("picture", "H3 edit", "video", "pasted picture"). A public edit or clip made
    from a picture that is still private shows that input as "(a private picture ...)": it needs making public too.
  - Never open, list, search, copy or describe anything under `my/private/`, `<data>\outputs\studio\`,
    `<data>\outputs\uploads\` or `<data>\inputs\` (the engine's copies of edit inputs) except files `gen.py studio`
    printed as public. Not their metadata either (Studio PNGs carry their prompt), not the Studio's `/api/history` or
    `/api/jobs`, not ComfyUI's `/history` or `/queue`, and no `git log -p` / `git show` / `git diff` of `my/history.jsonl`
    or `my/feedback.jsonl` (older installs had the user's prompts there; the Studio moved them out). `gen.py` refuses
    private pictures (`final`, `--image`, `frames`); don't work around it.
  - **When the user talks about a picture you can't see** ("the one I just made", "fix her hands in my last one", "make
    a video of my girl"), check `gen.py studio`. If it is private, say so kindly and tell them how: "That one is private,
    so I can't see it. In the Studio open *My pictures*, click it and press **Let Claude see it** (or *Select* a few and
    press **Let Claude see**). Tell me when it's done." Don't guess what is in it, and don't ask them to paste the
    prompt as a workaround (they may; it's their choice). They can make it private again any time with the same button.
  - Ratings and notes on private pictures stay private too; `gen.py feedback` leaves them out. Errors from the page
    (`my/studio-errors.log`) list only the job's settings, never its prompt.

Commands. The engine's Python is `<engine_dir>\python_embeded\python.exe` (`engine_dir` is in `my/settings.json`).
Always pass `-s`. `kit\py.cmd` wraps it for cmd/PowerShell. From Git Bash, call the python.exe path directly.

```
kit\py.cmd kit\studio\gen.py status
kit\py.cmd kit\studio\gen.py one --character "1girl, solo, ..." --scene "..." --body curvy_idol [--style ll_card] [--seed 7] [--quality final]
kit\py.cmd kit\studio\gen.py grid r03 --example "Idol on stage" --vary body=curvy_idol,petite_idol --seeds 1,2 --open
kit\py.cmd kit\studio\gen.py round r03 my\rounds\r03.jobs.jsonl --title "..." --question "..."
kit\py.cmd kit\studio\gen.py one --engine h3 --prompt "..." [--image out:r03/x_00001_.png]
kit\py.cmd kit\studio\gen.py one --engine video --prompt "..." [--image out:r03/x_00001_.png] [--seconds 5] [--resolution 480p|720p]
kit\py.cmd kit\studio\gen.py final r03/x_s2_00001_.png     (the same picture in Final quality)
kit\py.cmd kit\studio\gen.py make-body soft_short --describe "..." --tags "..."   (then --pick N)
kit\py.cmd kit\studio\gen.py feedback r03
kit\py.cmd kit\studio\gen.py studio          (the user's own Studio pictures: public ones in full, private ones as time + kind)
kit\py.cmd kit\studio\gen.py selftest
powershell -ExecutionPolicy Bypass -File kit/start.ps1 [-NoBrowser] [-ComfyUI] [-Restart] [-Stop]
```

### "Can you make me some ...?" (the fast path)

Most requests are not experiments, just "make me a few X". Do this without asking first:
1. Turn the wish into a job: start from the closest ready-made example (`--example`) or `my/RECIPES.md`, write the
   character and scene tags yourself, pick the body drawing. Default style `ll_signature`, quality **Preview** (the default: detailed enough
   to judge and to keep, about 40% faster than Final).
2. `gen.py grid <id> ... --seeds 1,2,3,4 --open` (or `--vary` one thing if they were unsure, e.g. two bodies).
   Tell them roughly how long it takes (section 7) and that the pictures appear in the Studio's *Rounds* tab.
3. Look at every picture yourself (open the PNGs) before you talk about them, against the **quality bar** below.
   Re-run the ones that fail with new seeds instead of showing them.
4. Show them, say which you think is best and why in one line, ask what to change. When they like one, offer
   "4 variations", write it into `my/RECIPES.md`, or, if they want it as good as it gets (print, wallpaper, close-up
   detail), remake it in Final: `gen.py final <file>` (same seed and settings, same size, finer detail; it lands in the
   same round folder and in *My pictures*, not on the round page).

### Quality bar

`examples/bar/` holds pictures the kit's author approved as the Love Live standard, and `examples/examples.json` +
`docs/guide/img/ex*.jpg` the kit's examples. A picture meets the bar when:
- the eyes are **big and round with the show's highlight and pink blush**, not small or narrow. Small eyes usually mean the
  face is too small in the frame: use a `_cowboy` body drawing or `upper body` / `cowboy shot` framing, or make sure the
  body drawing fills its frame. Narrow, grown-up eyes mean the `ll_tv` style: use `ll_signature`.
- line work is crisp and colours clean, flat cel shading (no glossy airbrushed skin, which means hype words crept in);
- the body type is the one asked for (if not: body drawing + matching tags, strength 0.6-0.75);
- she is the user's own girl, not a canon character (hair colour and uniform kept), unless they asked for fan art;
- hands and props are plausible (re-roll seeds rather than show broken hands).
Say plainly when a batch misses the bar and what you change.

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
| "wrong body / not curvy enough / too thin" | words too weak for this seed/outfit, or a drawing whose shape is worse than the words | try the *words only* body first with a few seeds, strengthen `(curvy:1.8)`; if the words can't get it (petite) use the drawing, strength 0.6 -> 0.75; round across both |
| "she's stiff / always standing straight" | the drawing locks the pose | use an idol/jump/wave/sit drawing, lower end to 0.5 or strength to 0.5, or no drawing (tags only) for dynamic poses |
| "she became a Love Live character" | `ll_canon` style, or canon hair/uniform tags (`uranohoshi school uniform`, ashen hair + braid) | switch to `ll_tv`, change hair colour/style or uniform tags |
| "extra fingers / weird hands" | normal for these models | new seeds (4 variations), `hands` out of frame (`upper body`), or `bad hands, extra fingers` in avoid |
| "two girls appeared" | crowded scene tags | `solo` in character, fewer scene props; `1girl, solo` must stay |
| "I want <another show / artist> style" | different designer | look the artist up on Danbooru (`https://danbooru.donmai.us/tags.json?search[name]=<tag>`, a few hundred posts = the model knows it), copy the `ll_tv` template with that `@artist` and year into `my/presets.json`, round of 2 seeds x 2 years |
| "make it more original / my own style" | | Small style words (`pastel colors`, `flat color`, `thick lineart`, `watercolor (medium)`, `film grain`) barely move the Love Live look, even weighted (tested). What works: **a second artist tag** after `@murota yuuhei` (blends; see the experimental `ll_soft` / `ll_watercolor` styles), **a weaker designer** `(@murota yuuhei:0.6)` + another `year` + era tags (`ll_90s`), `year 2023` / `official art`, or Anima Base (optional download). Run a round of 4-6 artist blends on their character (Danbooru artists with 300+ posts), record the winner as a named style in `my/presets.json` |
| "too slow" | GTX 10 card, or first picture (models loading) | Turbo or Small sketch to explore, Preview to check, Final for keepers (section 7); fewer pictures per click; close games/browsers using the GPU; section 7 |
| "it got slow" after H3 pictures or videos | H3's 29 GB (video: 32 GB) crowd the 16 GB of RAM, so the Love Live model reloads from disk each time | `start.ps1 -Restart` when switching back from H3 to Love Live pictures for a while (measured on the test PC: ~75 s -> ~57 s); keep H3 work in one batch |
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

| card | engine build | Final 30 steps | Preview 18 | Small sketch | Turbo sketch | notes |
|---|---|---|---|---|---|---|
| RTX 5060 8 GB (test PC: Ryzen 5900X, 16 GB, measured 2026-11-17) | `modern` (torch cu130) | 56 s | 34 s | 18 s | 9 s | peak VRAM 7.3 GB with a body drawing |
| H3-Image (optional) on RTX 5060 + 16 GB RAM | `modern` | 17-25 s described, ~50 s an edit | | | | streams its 29 GB of weights from the SSD each picture; needs an SSD |
| H3 video (optional) on RTX 5060 + 16 GB RAM (measured 2026-11-18) | `modern` | 480p 5 s: 2.4 min, 8 s: 4.2 min; 720p 5 s: 6.3 min | | | | the same every clip (nothing stays loaded with 16 GB RAM); peak VRAM 7.6 GB, free RAM down to 1.2 GB: close other programs while it works |
| GTX 1070 8 GB | `pascal` (torch 2.14 cu126, the last PyTorch that supports it) | estimate 4-5 min | ~2.5 min | ~1.5 min | ~45 s | **not tested on real hardware**: estimates from compute throughput. Measure the first pictures and tell the user real numbers. On Windows ComfyUI runs this card in fp16; if pictures come out black, setup retries with `--fp32-vae`, then `--force-fp32` (slower). Driver: 580 branch (the last for GTX 10) |

What the qualities are for: **Preview** is nearly the same picture as Final with the same seed (use it to check an
idea, then Final with that seed). **Small sketch** looks as good but is a different picture. **Turbo** is fastest but
its Love Live look is weaker (more generic faces, stray text, extra props): use it to explore prompts and poses, never
to judge style. On a slow card: Turbo or Small to explore, Preview to pick, Final for keepers.
The Studio and `gen.py` both default to **Preview**; the picture viewer's *Make it in Final quality* button and
`gen.py final <file>` remake a Preview in Final with the same seed and settings (same size, finer detail). The
"Working on" list shows on the Create and H3 tabs. The H3 tab takes pictures from outside the Studio too (paste, drop,
or choose a file; saved in `<data>\outputs\uploads\`). After a `git pull`, double-clicking *Love Live Studio* restarts the
Studio page server when its code changed (not while it is drawing); the open page then offers a reload.

16 GB of RAM is enough: the models take about 6 GB, and nothing else heavy needs to run. Keep the data folder on an SSD.

## 8. Files you keep in `my/`

| file | what |
|---|---|
| `settings.json` | data folder, engine folder, build, extra engine flags (setup writes it; edit `extra_flags` if needed) |
| `system.json` | the PC (setup `-Check`) |
| `history.jsonl` | every picture you made: file, prompt, seed, body, quality, time. Never edit, only append (gen.py does) |
| `feedback.jsonl` | the user's ratings and notes on your pictures and rounds (Studio). Never edit |
| `library.json` | the user's pictures they made public, and the trash (file names and times; the Studio writes it) |
| `private/` | the user's own Studio pictures' records and ratings. **Private: never open** (section 3); not in git |
| `rounds/<id>.json`, `<id>.jobs.jsonl` | each round: question, items, status |
| `ROUNDS.md` | the lab notebook: dated entries per round |
| `RECIPES.md` | the recipe book: what works for each kind of picture, with full example prompts |
| `TASTE.md` | what this user likes and dislikes, in their words |
| `presets.json` | their own styles, bodies and examples; shown in the Studio on top of the kit's |
| `controls/` | their own body drawings |
