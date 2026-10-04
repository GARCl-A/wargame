# Portraits System & Treefolk (ex-Leshy)

Added circular engraved medallion portraits to the game, established the portrait asset pipeline, and renamed/rebalanced the Leshy race to Treefolk.

## The Problem

1. **Modular compositor dead end:** Slicing modular facial features (eyes, noses, mouths, heads) from generative models failed across fantasy races due to incompatible anatomical anchors, varying head shapes, and overlapping features (beards, branches, horns).
2. **Visual aesthetic mismatch:** Full photo-style portraits did not fit the game's tabletop brass/steel/parchment identity.
3. **Leshy thematic drift:** The "Leshy" was originally `Small` with `d6` HD, but the chosen woodcut illustration identity portrays formidable humanoid bark/foliage beings that fit a `Medium` creature much better.

## What Was Decided

- **Style:** Dark fantasy OSR woodcut / ink engraving on aged parchment, cropped into clean circular medallions with an outer ink rim.
- **Race Renaming & Stats:**
  - Renamed from `Leshy` to `Treefolk`.
  - Size changed from `Small` to `Medium`.
  - Hit Die kept at `d6`.
  - Ability `autotroph` and language `Verdant` preserved.
  - Backwards-compatibility alias added in `data.race_by_name("Leshy") -> Treefolk`.
- **Directory Structure:**
  - `gartok/assets/portraits/<race_lower>/<id>.png`.
  - Adding a new race is purely dropping clean PNG files into a folder matching the lower-cased race name (e.g. `treefolk/` with 10 medallions, `goblin/` with 7 curated medallions, `hobgoblin/` with 9 curated medallions, `orc/` with 12 complete medallions, `automaton/` with 10 curated medallions, `human/` with 12 complete medallions, `elf/` with 12 complete medallions, `kobold/` with 11 curated medallions, `lizardfolk/` with 9 curated medallions, `halfling/` with 12 complete medallions, `gnome/` with 12 complete medallions, `dwarf/` with 9 curated medallions, `centaur/` with 12 complete medallions, `gnoll/` with 11 curated medallions, `grippli/` with 11 curated medallions, `sprite/` with 11 curated medallions, `kenku/` with 8 curated medallions, `goliath/` with 8 curated medallions).
- **Loader & Fallback (`artwork.portrait`):**
  - Cached via `@functools.lru_cache(maxsize=256)`.
  - Automatically scales to `(px, px)` using `pygame.transform.smoothscale`.
  - Uses natural numeric key sorting so indices >= 10 sequence after single digits.
  - Maps `portrait_id % len(files)`.
  - Returns `None` if no portraits exist for a race, enabling seamless fallback across all screens to the existing SVG silhouettes (`artwork.race_icon`).
- **PRNG Protection in `Unit`:**
  - `Unit.portrait_id` is derived deterministically from `int(self.uid[:8], 16)`.
  - **Crucial:** Never roll `random.randint` in `Unit.__init__` for purely cosmetic attributes, as doing so alters the global PRNG stream and breaks test suites relying on fixed seeds (`random.seed(3)`).

## Integration Points

- `ui/primitives.py:token_badge`: Blits medallion portrait if available.
- `theme.py:token_badge`: Legacy bridge updated.
- `ui/combat_card.py`: Renders portrait on vertical recruit/squad cards and party rows.
- `ui/sheet_card.py`: Displays portrait token on character sheets.
- `battle_screen.py`: Renders portrait tokens directly on the tactical grid cells and on the initiative strip.
- `persist.py`: Serializes and restores `portrait_id`.
