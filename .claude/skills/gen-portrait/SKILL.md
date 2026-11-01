---
name: gen-portrait
description: Generate a medallion portrait for a GARTOK NPC, creature or race with the local Stable Diffusion + the game's own style LoRA (the fallback: Gemini results are better), then install it in the portrait pool. Only when the user types /gen-portrait or asks you to generate a portrait with the local model.
---

The tool is `scripts/gen_portrait.py`; setup, measured times and why this recipe are in
`scripts/portrait_lora/README.md`. Gemini is the preferred generator and an agent does not generate art
on its own ([web_client.md](../../../docs/web_ui/web_client.md), *How the art is made*): this skill runs
only when the author asks for the local model. Work files go to `scratch/portrait_gen/<name>/` (gitignored).

## Steps

1. **Pin down the request.** Who/what, and where it lands: a pinned NPC portrait (`--npc <id>`,
   file `npcs/<id>.json`) or one more face in a race's numbered pool (`--race <race>`). Read the NPC's
   `bio`, race and `RULES.md`/`REFERENCE.md` entry for the look; ask only if it is genuinely unclear.
2. **Check the webui:** `python scripts/gen_portrait.py status`. If it is down, ask the user to start
   the webui (the README has the path) and wait. Never launch it yourself and never install anything new.
3. **Write the subject in English**, concrete and short, naming the head and framing. Creatures need
   "head close-up"; say how many horns/eyes/ears; no scars or torn parts (SD 1.5 deforms the face).
   Example: `a fierce wild aurochs bull head, two separate long horns curving forward and up, thick shaggy mane, angry glaring eyes, close-up`.
4. **Generate candidates in the background**: `python scripts/gen_portrait.py gen "<subject>" <name> -n 8`
   (a contact sheet is rewritten after every image). Tell the user the ETA from the README's
   measured times and wait for the completion notice; do not poll.
5. **Show the contact sheet only** (`scratch/portrait_gen/<name>/sheet.png`), one image read, and say which
   seeds look best and why. Do not open candidates one by one. Check for: wrong horn/ear count, props,
   a calm face on something meant to be menacing, a full body instead of a head. If none works, change
   the subject text or `--seed` and generate another batch.
6. **Refine the user's pick (or your top two):**
   `python scripts/gen_portrait.py refine scratch/portrait_gen/<name>/cand_<seed>.png --subject "<same text>"`
   (768 px, adds the hatching the 512 px version lacks). Show the result next to the candidate.
7. **After the user approves:** `python scripts/gen_portrait.py install <refined.png> --race <race>` or `--npc <id>`
   (crops a 200 px circle with transparent corners). For an NPC also set `"portrait_file": "<id>.png"` in its
   `npcs/<id>.json` (`test_every_pinned_npc_portrait_is_a_file` checks it).
   For a race, warn that the pool grows and `portrait_id % len(files)` shifts, so existing units of that
   race may swap faces. Run `python -m pytest tests/test_portraits.py -q`.
8. **Do not commit.** Hand over to the `pre-commit` skill; commits need the user's approval.

## Rules of thumb

- Never use the image-to-image path from an existing portrait to make a new subject: it inherits the old
  pose and props (a harnessed ox stays harnessed). New subjects start from text + the LoRA.
- A GPU job holds the webui: run one generation at a time.
