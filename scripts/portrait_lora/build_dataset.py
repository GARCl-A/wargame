"""Packs the game's portraits plus one caption each into scratch/portrait_lora/gartok_style.zip."""
import os
import shutil
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "gartok", "assets", "portraits")
OUT = os.path.join(ROOT, "scratch", "portrait_lora", "gartok_style")
TRIGGER = "gartokstyle"

shutil.rmtree(OUT, ignore_errors=True)
os.makedirs(OUT)
n = 0
for folder in sorted(os.listdir(SRC)):
    path = os.path.join(SRC, folder)
    if not os.path.isdir(path):
        continue
    name = folder.replace("_", " ")
    subject = "" if folder == "npc" else f" of {'an' if name[0] in 'aeiou' else 'a'} {name}"
    for f in sorted(os.listdir(path)):
        if not f.lower().endswith(".png"):
            continue
        stem = f"{folder}_{os.path.splitext(f)[0]}"
        shutil.copy(os.path.join(path, f), os.path.join(OUT, stem + ".png"))
        with open(os.path.join(OUT, stem + ".txt"), "w", encoding="utf8") as fh:
            fh.write(f"{TRIGGER}, ink engraving circular medallion portrait{subject}, cross-hatching, parchment")
        n += 1

zpath = OUT + ".zip"
with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
    for f in os.listdir(OUT):
        z.write(os.path.join(OUT, f), f)
print(n, "images ->", zpath, round(os.path.getsize(zpath) / 1e6, 1), "MB")
