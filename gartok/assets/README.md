# Assets

```
assets/
  icons/            game-icons.net silhouettes (SVG). LOADED at runtime.
    body/  hat/  head/    flattened <category>/<name>.svg  (no per-author dir)
    LICENSE.txt          CC BY 3.0 — see file
  portraits/        engraved medallion portraits, one folder per race.
```

## icons/ — used by the game

`gartok/artwork.py` loads these on demand, rasterises each SVG once at the size
asked for, tints it, and caches by `(category, name, px, colour)`. Right now only
`head/` is wired up: `ui.primitives.token_badge` draws the unit's **race silhouette** on
the team-coloured disc (`artwork.RACE_ICON` maps race name -> file), falling back
to the board letter when a race has no glyph.

`body/` and `hat/` are staged for later (occupation art on the character sheet /
guild detail panel). Nothing loads them yet.

Adding an icon: drop a white-on-transparent SVG into the right folder, reference
it by bare name (`artwork.icon("head", "orc-head", 24)`).
