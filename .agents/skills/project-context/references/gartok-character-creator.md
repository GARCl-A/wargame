---
name: gartok-character-creator
description: "The Editor / sandbox character creator, npc_lib NPC library, and the Unit sandbox-edit methods"
metadata: 
  node_type: memory
  type: project
  originSessionId: 3e784886-38b8-4631-824e-de1de20ac39b
  modified: 2026-09-10T22:17:40.133Z
---

Main menu now has an **EDITOR** button (`menu_screen` `on_editor` → `app._start_editor`)
→ `EditorMenuScreen` — two doors, both open now: character creator and scenario
creator (the map editor, see [[gartok-map-editor]]).

`char_editor_screen.CharEditorScreen` is a **sandbox**, not a player flow — not
bound by draft/XP gating. Every editable field set straight to a valid value:
race/occupation/alignment from tables, 6 attributes as 3d6 scores (3..18),
combat/work level by stepper (picks + hit dice follow via `Unit.set_track_level`),
talents from the trees, languages, purse, full loadout from the item catalog.
Left column is a mouse-wheel-scrollable form; right column = live
`sheet.character_sheet(Combatant(u))` + the NPC library list.

`Unit` sandbox-edit block (after "draft editing"): `set_name`, `set_alignment`,
`set_base_attribute`, `set_age`, `set_language`, `set_gold`, `set_track_level`
(resyncs hp rolls + talent picks on the way down), `drop_talent` (cascades to
dependents). `choose_talent` unchanged — still gated by `picks_available`, so
level up first to grant picks.

**DUPLICATE button (Sep 2026, commit `2521b47`).** Top bar, next to RANDOMIZE.
`CharEditorScreen._duplicate`: `persist.unit_to_dict` → drop `uid` → `from_save`
(mints a fresh identity) → name " (copy)" → `_load_unit(clone, slug=None)`, so
SAVE writes a new `npcs/` file. For authoring near-identical boss variants.

**PROGRESSION section now has THREE steppers** (COMBAT / WORK / RACIAL) since the
racial track landed (see [[gartok-talent-trees]]). RACIAL is `set_track_level(
"racial", n)` → pins `Unit._racial_override` (a sandbox racial level, sticky like
`_hp_override`), setting hit dice + racial picks straight, independent of
combat/work. An "auto" tag on the line below clears it. TALENTS section is three
columns; the racial column shows `talents.racial_tree(race)` and "— none for this
race yet" when empty.

`npc_lib.py`: NPC library outside the campaign saves — one JSON per NPC in
`npcs/` at repo root, **git-tracked** (authored content, like world.py). Same
payload as a save-slot roster entry (`persist.unit_to_dict`) + `npc_slug`.
`save_npc` / `load_npc` / `delete_npc` / `list_npcs`. Nothing consumes these yet
— the point is to hand-author the arena champion team (see
[[gartok-factions-reputation]]) and later `use NPC x`.

**CTF boss team (started Sep 2026).** The user is hand-authoring a boss team for
the 2nd arena faction — the "Day Games" / capture-the-flag chief fight
(`maps/capture-the-flag-the-gamers.json`). First member: **Ribit** (`npcs/ribit.json`),
a Grippli Farmer. The team's kit comes from race + occupation + attributes +
talents + gear today; the `fleet` talent (+1 Speed) was added partly for this.

**Boss abilities go through the racial talent track, NOT a custom-ability field.**
The earlier "per-NPC custom-ability field" plan was dropped — the user's call
(Sep 2026): NPCs should be things a player can also become, so Ribit's tongue is
the Grippli-gated `tongue` racial node, earnable by any player Grippli. It grew
into a real weapon slot (`equipped_tongue`, 1-handed, its own "Lash" attack) +
the "TONGUE" pick row in the creator's PURSE + GEAR (shown only when the unit has
the talent). See [[gartok-talent-trees]].
