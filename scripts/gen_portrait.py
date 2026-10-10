"""Generate GARTOK medallion portraits with a local Stable Diffusion (AUTOMATIC1111 API).

    python scripts/gen_portrait.py status
    python scripts/gen_portrait.py gen "a scarred orc warrior with tusks" orc_warrior -n 8
    python scripts/gen_portrait.py refine scratch/portrait_gen/orc_warrior/cand_1001.png --subject "a scarred orc warrior with tusks"
    python scripts/gen_portrait.py install scratch/portrait_gen/orc_warrior/refined_1001.png --race orc
    python scripts/gen_portrait.py install <png> --npc aurochs

Needs the webui running with --api, the base checkpoint and the style LoRA trained on the
game's own portraits (see scripts/portrait_lora/README.md). Env overrides: GARTOK_SD_URL,
GARTOK_LORA, GARTOK_SD_CHECKPOINT.
"""
import argparse
import base64
import io
import json
import os
import re
import time
import urllib.request

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORTRAITS = os.path.join(ROOT, "gartok", "assets", "portraits")
WORK = os.path.join(ROOT, "scratch", "portrait_gen")

URL = os.environ.get("GARTOK_SD_URL", "http://127.0.0.1:7860")
LORA = os.environ.get("GARTOK_LORA", "gartok_style-000006")
CHECKPOINT = os.environ.get("GARTOK_SD_CHECKPOINT", "v1-5-pruned-emaonly")

PROMPT = ("<lora:{lora}:1.0>, gartokstyle, ink engraving circular medallion portrait of {subject}, "
          "cross-hatching, parchment")
REFINE_PROMPT = PROMPT + ", fine detailed linework, sharp"
NEG = "color, photo, blurry, soft, text, watermark, 3d render, deformed, extra horns, harness"
PARCHMENT = (236, 224, 196)


def _post(path, body, timeout=3000):
    body = {**body, "override_settings": {"sd_model_checkpoint": CHECKPOINT}}
    req = urllib.request.Request(URL + path, json.dumps(body).encode(), {"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=timeout))["images"][0]


def _load(path, size=None):
    surf = pygame.image.load(path)
    return pygame.transform.smoothscale(surf, (size, size)) if size else surf


def _b64(surf):
    buf = io.BytesIO()
    pygame.image.save(surf, buf, "x.png")
    return base64.b64encode(buf.getvalue()).decode()


def _slug(name):
    return re.sub(r"[^a-z0-9_]+", "_", name.lower()).strip("_")


def _seed_of(path):
    return int(re.search(r"(\d+)\.png$", path).group(1))


def status(_):
    try:
        loras = json.load(urllib.request.urlopen(URL + "/sdapi/v1/loras", timeout=10))
    except OSError as e:
        raise SystemExit(f"webui not reachable at {URL} ({e}). Start it with --api first.")
    names = [item["name"] for item in loras]
    print("webui up; loras:", ", ".join(names))
    if LORA not in names:
        raise SystemExit(f"LoRA '{LORA}' is not installed in the webui's models/Lora folder.")


def gen(args):
    out = os.path.join(WORK, _slug(args.name))
    os.makedirs(out, exist_ok=True)
    paths = []
    for i in range(args.n):
        seed = args.seed + i
        t = time.time()
        img = _post("/sdapi/v1/txt2img", {
            "prompt": PROMPT.format(lora=LORA, subject=args.subject), "negative_prompt": NEG, "steps": 25,
            "width": 512, "height": 512, "cfg_scale": 7, "sampler_name": "Euler a", "seed": seed})
        path = os.path.join(out, f"cand_{seed}.png")
        with open(path, "wb") as f:
            f.write(base64.b64decode(img))
        paths.append(path)
        print(f"seed {seed}: {round(time.time() - t)} s -> {path}", flush=True)
        sheet(paths, os.path.join(out, "sheet.png"))
    print("contact sheet:", os.path.join(out, "sheet.png"))


def sheet(paths, dest, tile=256, cols=4):
    pygame.font.init()
    font = pygame.font.Font(None, 20)
    rows = (len(paths) + cols - 1) // cols
    s = pygame.Surface((cols * tile, rows * tile))
    s.fill(PARCHMENT)
    for i, p in enumerate(paths):
        x, y = (i % cols) * tile, (i // cols) * tile
        s.blit(_load(p, tile), (x, y))
        label = font.render(str(_seed_of(p)), True, (255, 255, 255), (0, 0, 0))
        s.blit(label, (x, y))
    pygame.image.save(s, dest)


def refine(args):
    src = os.path.abspath(args.image)
    t = time.time()
    img = _post("/sdapi/v1/img2img", {
        "init_images": [_b64(_load(src, 768))], "denoising_strength": 0.4, "steps": 30, "width": 768,
        "height": 768, "prompt": REFINE_PROMPT.format(lora=LORA, subject=args.subject), "negative_prompt": NEG,
        "cfg_scale": 7, "sampler_name": "Euler a", "seed": _seed_of(src)})
    dest = os.path.join(os.path.dirname(src), os.path.basename(src).replace("cand_", "refined_"))
    with open(dest, "wb") as f:
        f.write(base64.b64decode(img))
    print(f"refined in {round(time.time() - t)} s -> {dest}")


def medallion(src, dest, size=200, scale=4):
    img = pygame.Surface((size, size), pygame.SRCALPHA)
    img.blit(_load(src, size), (0, 0))
    mask = pygame.Surface((size * scale, size * scale), pygame.SRCALPHA)
    pygame.draw.circle(mask, (255, 255, 255, 255), (size * scale // 2, size * scale // 2), size * scale // 2)
    img.blit(pygame.transform.smoothscale(mask, (size, size)), (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    pygame.image.save(img, dest)


def install(args):
    if args.race:
        folder = os.path.join(PORTRAITS, args.race.lower().replace(" ", "_"))
        os.makedirs(folder, exist_ok=True)
        taken = [int(os.path.splitext(f)[0]) for f in os.listdir(folder) if os.path.splitext(f)[0].isdigit()]
        dest = os.path.join(folder, f"{max(taken, default=-1) + 1}.png")
    else:
        dest = os.path.join(PORTRAITS, "npc", f"{_slug(args.npc)}.png")
        os.makedirs(os.path.dirname(dest), exist_ok=True)
    medallion(args.image, dest)
    print("installed", dest)
    if args.npc:
        print(f'next: set "portrait_file": "{_slug(args.npc)}.png" in npcs/<id>.json and list it in '
              "tests/test_portraits.py::test_named_npcs_load_pinned_portraits")
    else:
        print("note: a bigger pool changes `portrait_id % len(files)`, so existing units of that race may swap face")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status").set_defaults(fn=status)
    g = sub.add_parser("gen")
    g.add_argument("subject", help="what to draw, in English (the style words are added for you)")
    g.add_argument("name", help="work folder name under scratch/portrait_gen/")
    g.add_argument("-n", type=int, default=8)
    g.add_argument("--seed", type=int, default=1001)
    g.set_defaults(fn=gen)
    r = sub.add_parser("refine")
    r.add_argument("image")
    r.add_argument("--subject", required=True, help="same subject text used in gen")
    r.set_defaults(fn=refine)
    i = sub.add_parser("install")
    i.add_argument("image")
    dest = i.add_mutually_exclusive_group(required=True)
    dest.add_argument("--race", help="add to that race's numbered pool")
    dest.add_argument("--npc", help="pinned portrait: portraits/npc/<name>.png")
    i.set_defaults(fn=install)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
