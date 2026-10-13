# Assets

```
assets/
  icons/            game-icons.net silhouettes (SVG). LOADED at runtime.
    action/ body/ gui/ hat/ head/    flattened <category>/<name>.svg  (no per-author dir)
    map/                 drawn for this game: the map nodes and occupations game-icons.net lacks
    LICENSE.txt          CC BY 3.0 — see file (covers everything but map/)
  portraits/        engraved medallion portraits, one folder per race.
```

## icons/ — used by the game

`gartok/artwork.py` loads these on demand, rasterises each SVG once at the size
asked for, tints it, and caches by `(category, name, px, colour)`:

- `head/` -- `ui.primitives.token_badge` draws the unit's **race silhouette** on the
  team-coloured disc (`artwork.RACE_ICON` maps race name -> file), falling back to the
  board letter when a race has no glyph.
- the **occupation** glyph leads the race / occupation line of the character sheet, the
  member rows and the guild screen (`artwork.OCCUPATION_ICON`, `artwork.occupation_icon`).
- the **map nodes** each draw their own glyph (`map_screen.NODE_ICON`).

`tests/test_icons.py` fails for a node or an occupation with no glyph, or one whose file is
missing. `map/` is drawn as plain filled shapes on a 512 box (clockwise subpaths fill, a
counter-clockwise one cuts a hole).

Adding an icon: drop a white-on-transparent SVG into the right folder, reference
it by bare name (`artwork.icon("head", "orc-head", 24)`).
