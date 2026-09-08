# Assets

```
assets/
  icons/            game-icons.net silhouettes (SVG). LOADED at runtime.
    body/  hat/  head/    flattened <category>/<name>.svg  (no per-author dir)
    LICENSE.txt          CC BY 3.0 — see file
  dungeon/          the "16x16 Dungeon" promo sheet + its sliced tileset. ORPHAN.
    16x16dungeon.png     source sheet
    build_tileset.py     slices it -> dungeon_tileset.png/.json + tiles/*.png
    dungeon_tileset.*    packed atlas + name->rect manifest
    tiles/              each tile isolated, transparent
```

## icons/ — used by the game

`gartok/artwork.py` loads these on demand, rasterises each SVG once at the size
asked for, tints it, and caches by `(category, name, px, colour)`. Right now only
`head/` is wired up: `theme.token_badge` draws the unit's **race silhouette** on
the team-coloured disc (`artwork.RACE_ICON` maps race name -> file), falling back
to the board letter when a race has no glyph.

`body/` and `hat/` are staged for later (occupation art on the character sheet /
guild detail panel). Nothing loads them yet.

Adding an icon: drop a white-on-transparent SVG into the right folder, reference
it by bare name (`artwork.icon("head", "orc-head", 24)`).

## dungeon/ — orphaned

The board is rendered procedurally (see `gartok-ui-redesign`); this tileset is
kept on disk in case props (barrels, chests) come back. Regenerate with
`python gartok/assets/dungeon/build_tileset.py` (needs Pillow).
