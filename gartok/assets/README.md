# Assets

```
assets/
  icons/       SVG silhouettes, white on transparent: action/ body/ gui/ hat/ head/ item/ flattened to
               <category>/<name>.svg (game-icons.net, no per-author dir), and map/, drawn for this game
               (the map nodes game-icons.net lacks). LICENSE.txt covers all but map/. blood/ meat/ poison/
               state/ symbol/ trap/ wing/ keep the download's own nesting (ffffff/transparent/1x1/<author>/
               <name>.svg): the condition marks of the battle board read them (`web/condition_marks.py`).
  portraits/   engraved medallion portraits, one folder per race, creature or `npc`, numbered PNGs.
  sounds/      Kenney sound effects (OGG, CC0, LICENSE.txt); `gartok/sound.py` names each cue's files.
```

Who reads them: `gartok/art_files.py` says where each file is (portrait of a unit, `RACE_ICON`,
banner emblems; `map_view.NODE_ICON` for the nodes), the web serves them as they are
under `/assets/`, and `editor/artwork.py` rasterises and tints the SVGs for pygame. A race
or node without a glyph fails a test (`AGENTS.md`); new portraits are made as `web_client.md` says (*How the art is made*).

`map/` is plain filled shapes on a 512 box: a clockwise subpath fills, a counter-clockwise one cuts a hole.

Adding an icon: drop a white-on-transparent SVG into the right folder and reference it by bare name
(`artwork.icon("head", "orc-head", 24)`).
