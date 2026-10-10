---
name: gen-portrait
description: Generate a medallion portrait for a GARTOK NPC, creature or race with the local Stable Diffusion + the game's own style LoRA, then install it in the portrait pool. Use when the user types /gen-portrait or asks for art / a portrait / a face for an NPC, creature, legendary beast, race or boss.
---

Reply in Portuguese. The tool is `scripts/gen_portrait.py` (setup, measured times and why this
recipe in `scripts/portrait_lora/README.md`). Work files go to `scratch/portrait_gen/<name>/` (gitignored).

## Steps

1. **Pin down the request.** Who/what, and where it lands: a pinned NPC portrait (`--npc <id>`,
   file `npcs/<id>.json`) or one more face in a race's numbered pool (`--race <race>`). Read the NPC's
   `bio`, race and `RULES.md`/`REFERENCE.md` entry for the look; ask only if it is genuinely unclear.
2. **Check the webui:** `python scripts/gen_portrait.py status`. If it is down, ask the user to start
   `C:\dev\sd\stable-diffusion-webui\webui-user.bat` and wait for them. Never launch it yourself
   (the permission classifier blocks it) and never install anything new.
3. **Write the subject in English**, concrete and short, naming the head and framing. Creatures need
   "head close-up"; say how many horns/eyes/ears; no scars or torn parts (SD 1.5 deforms the face).
   Example: `a fierce wild aurochs bull head, two separate long horns curving forward and up, thick shaggy mane, angry glaring eyes, close-up`.
4. **Generate candidates in the background**: `python scripts/gen_portrait.py gen "<subject>" <name> -n 8`
   (~2 min each, a contact sheet is rewritten after every image). Tell the user the ETA and wait for the
   completion notice; do not poll.
5. **Show the contact sheet only** (`scratch/portrait_gen/<name>/sheet.png`), one image read, and say which
   seeds look best and why. Do not open candidates one by one. Check for: wrong horn/ear count, props,
   a calm face on something meant to be menacing, a full body instead of a head. If none works, change
   the subject text or `--seed` and generate another batch.
6. **Refine the user's pick (or your top two):**
   `python scripts/gen_portrait.py refine scratch/portrait_gen/<name>/cand_<seed>.png --subject "<same text>"`
   (~4.5 min, 768 px, adds the hatching the 512 px version lacks). Show the result next to the candidate.
7. **After the user approves:** `python scripts/gen_portrait.py install <refined.png> --race <race>` or `--npc <id>`
   (crops a 200 px circle with transparent corners). For an NPC also set `"portrait_file": "<id>.png"` in its
   `npcs/<id>.json` and add the file to `test_named_npcs_load_pinned_portraits` in `tests/test_portraits.py`.
   For a race, warn that the pool grows and `portrait_id % len(files)` shifts, so existing units of that
   race may swap faces. Run `python -m pytest tests/test_portraits.py -q`.
8. **Do not commit.** Hand over to the `pre-commit` skill; commits need the user's approval.

## Rules of thumb

- Never use the image-to-image path from an existing portrait to make a new subject: it inherits the old
  pose and props (a harnessed ox stays harnessed). New subjects start from text + the LoRA.
- Look at images only through sheets and side-by-sides; each image read costs tokens.
- The LoRA only knows the pool's look, so if the pool grows by a lot, suggest retraining it
  (`scripts/portrait_lora/README.md`).
- A GPU job holds the webui: run one generation at a time.
