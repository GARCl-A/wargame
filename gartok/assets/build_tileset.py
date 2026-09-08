"""Quebra o promo sheet 16x16dungeon.png em um tileset pronto pra uso.

Gera:
  assets/tiles/<nome>.png        - cada tile isolado (fundo transparente)
  assets/dungeon_tileset.png     - atlas empacotado, grade de 16px
  assets/dungeon_tileset.json    - manifesto nome -> {x, y, w, h}

Rode:  python gartok/assets/build_tileset.py
"""
import json
import os
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "16x16dungeon.png")
TILES_DIR = os.path.join(HERE, "tiles")
ATLAS_PNG = os.path.join(HERE, "dungeon_tileset.png")
ATLAS_JSON = os.path.join(HERE, "dungeon_tileset.json")

TS = 16  # tamanho da celula


def crop(im, box):
    return im.crop(box)


def canvas(w, h):
    return Image.new("RGBA", (w, h), (0, 0, 0, 0))


def place(dst, src, anchor="bottom"):
    """Cola src centralizado em dst. anchor: 'bottom' encosta na base."""
    dw, dh = dst.size
    sw, sh = src.size
    x = (dw - sw) // 2
    if anchor == "bottom":
        y = dh - sh
    elif anchor == "center":
        y = (dh - sh) // 2
    else:  # top
        y = 0
    dst.alpha_composite(src, (max(x, 0), max(y, 0)))
    return dst


def trim(im):
    bbox = im.getbbox()
    return im.crop(bbox) if bbox else im


def main():
    src = Image.open(SRC).convert("RGBA")
    os.makedirs(TILES_DIR, exist_ok=True)
    for f in os.listdir(TILES_DIR):
        if f.endswith(".png"):
            os.remove(os.path.join(TILES_DIR, f))
    tiles = {}  # nome -> Image RGBA

    # ---- piso e parede decorados: blocos 32x32 (2x2 de 16px), grade alinhada em (8,267)/(56,268) ----
    floor_block = crop(src, (8, 267, 40, 299))      # 32x32
    brick_block = crop(src, (56, 268, 88, 300))     # 32x32
    tiles["floor_studs"] = floor_block.crop((0, 0, 16, 16))   # piso com 4 rebites
    tiles["floor_bars"] = floor_block.crop((16, 0, 32, 16))   # piso com ranhuras
    tiles["wall_brick"] = brick_block.crop((0, 0, 16, 16))    # parede de tijolo

    # ---- paredes e piso derivados da sala vazia (origem 150,124, grade 8x8) ----
    RX, RY = 150, 124

    def cell(col, row):
        x = RX + col * TS
        y = RY + row * TS
        return src.crop((x, y, x + TS, y + TS))

    tiles["wall_corner_tl"] = cell(0, 0)
    tiles["wall_corner_tr"] = cell(7, 0)
    tiles["wall_corner_bl"] = cell(0, 7)
    tiles["wall_corner_br"] = cell(7, 7)
    tiles["wall_top"] = cell(2, 0)
    tiles["wall_bottom"] = cell(2, 7)
    tiles["wall_left"] = cell(0, 2)
    tiles["wall_right"] = cell(7, 2)
    tiles["wall_left_chain"] = cell(0, 3)
    tiles["floor"] = cell(2, 2)
    tiles["floor_alt"] = cell(4, 5)

    # porta no topo: poste sobe acima da parede -> 16x32 ancorado embaixo
    door = canvas(TS, TS * 2)
    door_src = src.crop((RX + 4 * TS, RY - 16, RX + 5 * TS, RY + TS))  # 16x32
    door.alpha_composite(door_src, (0, 0))
    tiles["wall_door_top"] = door

    # medalhao decorativo do piso (3x3 no centro): cols 3-5, rows 3-5
    med = src.crop((RX + 3 * TS, RY + 3 * TS, RX + 6 * TS, RY + 6 * TS))  # 48x48
    tiles["floor_medallion"] = med  # tile grande 3x3

    # arco / entrada e entulho (fileira do meio, esquerda)
    tiles["archway"] = place(canvas(TS, TS * 2), trim(src.crop((7, 314, 25, 335))), "bottom")
    tiles["rubble"] = place(canvas(TS, TS), trim(src.crop((39, 317, 58, 335))), "bottom")
    tiles["anvil"] = place(canvas(TS, TS), trim(src.crop((7, 349, 21, 361))), "bottom")

    # ---- objetos soltos (fileira de objetos) -> recorte + trim + centraliza ----
    objs = {
        "barrel":       ((105, 277, 118, 291), TS, TS, "bottom"),
        "ladder":       ((129, 273, 139, 290), TS, TS, "bottom"),
        "table":        ((156, 268, 171, 298), TS, TS * 2, "bottom"),
        "chair":        ((148, 281, 157, 296), TS, TS, "bottom"),
        "chest_open":   ((189, 275, 202, 289), TS, TS, "bottom"),
        "gravestone":   ((214, 271, 227, 291), TS, TS, "bottom"),
        "weapon_rack":  ((239, 268, 265, 291), TS * 2, TS * 2, "bottom"),
        "torch":        ((104, 303, 120, 327), TS, TS * 2, "bottom"),
        "slime_green":  ((129, 306, 146, 322), TS, TS, "bottom"),
        "slime_blue":   ((150, 306, 167, 322), TS, TS, "bottom"),
        "slime_pink":   ((171, 306, 188, 322), TS, TS, "bottom"),
        "fence":        ((199, 308, 220, 322), TS * 2, TS, "bottom"),
        "bar":          ((231, 307, 239, 322), TS, TS, "bottom"),
    }
    for name, (box, tw, th, anchor) in objs.items():
        piece = trim(src.crop(box))
        # nao deixa transbordar da celula
        if piece.size[0] > tw or piece.size[1] > th:
            piece = piece.crop((0, 0, min(piece.size[0], tw), min(piece.size[1], th)))
        tiles[name] = place(canvas(tw, th), piece, anchor)

    # ---- grava tiles isolados ----
    for name, img in tiles.items():
        img.save(os.path.join(TILES_DIR, name + ".png"))

    # ---- empacota atlas (grade 16px, 12 colunas), varredura simples linha a linha ----
    import math
    COLS = 12
    slots = []  # (name, cw, ch, img) - celulas ocupadas por tile
    for name, img in tiles.items():
        cw = math.ceil(img.size[0] / TS)
        ch = math.ceil(img.size[1] / TS)
        slots.append((name, cw, ch, img))

    grid = {}  # (cx,cy) -> nome
    placements = {}

    def fits(cx, cy, cw, ch):
        for dx in range(cw):
            for dy in range(ch):
                if (cx + dx, cy + dy) in grid:
                    return False
        return cx + cw <= COLS

    for name, cw, ch, img in sorted(slots, key=lambda s: -s[2]):
        placed = False
        cy = 0
        while not placed:
            for cx in range(COLS):
                if fits(cx, cy, cw, ch):
                    for dx in range(cw):
                        for dy in range(ch):
                            grid[(cx + dx, cy + dy)] = name
                    placements[name] = (cx, cy, cw, ch)
                    placed = True
                    break
            if not placed:
                cy += 1

    rows = max(p[1] + p[3] for p in placements.values())
    atlas = Image.new("RGBA", (COLS * TS, rows * TS), (0, 0, 0, 0))
    manifest = {"tile_size": TS, "columns": COLS, "image": "dungeon_tileset.png", "tiles": {}}
    for name, cw, ch, img in slots:
        cx, cy, _, _ = placements[name]
        atlas.alpha_composite(img, (cx * TS, cy * TS))
        manifest["tiles"][name] = {"x": cx * TS, "y": cy * TS, "w": img.size[0], "h": img.size[1]}

    atlas.save(ATLAS_PNG)
    with open(ATLAS_JSON, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"{len(tiles)} tiles -> {TILES_DIR}")
    print(f"atlas {atlas.size} -> {ATLAS_PNG}")
    print(f"manifesto -> {ATLAS_JSON}")


if __name__ == "__main__":
    main()
