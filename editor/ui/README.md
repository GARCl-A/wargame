# editor/ui — the war-table kit (frozen)

**pygame is the Editor's alone** (`python -m editor`), and the Editor is frozen: it is kept as the
reference for the day it is ported off pygame. The game is the web client; its rules are in
`docs/web_ui/web_client.md`. Nothing here is built on any more.

The look to carry over: "steel desk + paper map". Chrome is dark steel, the world is paper laid on
the table, and brass / blood / green are the only things that glow.

- **Colour is state, not decoration.** Surfaces, lines and neutral text stay muted (`STEEL*`, `TX*`,
  `PAPER*`, `INK*`). `BRASS` = focus / primary, `BLOOD` = danger / shortage, `GREEN` = safe / done.
  A screen that is colourful at rest has spent its signal.
- **Spacing is a multiple of `T.S` (8).** Fixed small offsets (1-2 px borders, glyph nudges) are fine.
- **One concern per component, data in, rects out.** A component takes the area it owns and plain
  dicts / tuples, never a `Group`, `Node` or `Unit` (the screen adapts its model), and returns the hit
  rects the caller needs. Lay out relative to the rect given, with no fixed panel sizes.

The tokens are `tokens.py` (`T`); each other module's docstring says what its data looks like.
