# Character sheet audit — grouped by information tier

21 screens, 5 groups. Two shared components shipped so far: the full
sheet (`gartok/ui/sheet_card.py`, commit `56375f6`) and the gear/loadout
side of `gartok/ui/loadout_panel.py` (`shop_row`/`container_panel`,
wired into bank + city property). This file tracks what's done vs.
what's still a screenshot waiting on its migration. Screenshots for
anything already migrated are deleted as it lands -- what remains in
each folder is exactly what's still pending.

## Status at a glance

| Group | Status |
|---|---|
| 01_full_sheet | **partly done** -- shared modal + battle inspect + char editor preview shipped; draft_screen's own card and guild_screen's embedded panel still pending |
| 02_combat_card | **done** -- squad, taverna, and prison screens all use `gartok/ui/combat_card.py`. |
| 03_gear_card | **done** -- bank, city property, loot, market, and gear/group screens all use the shared `loadout_panel` component. Equip slots are live drop zones everywhere. |
| 04_roster_row | pending -- `draw_row` exists in code but isn't wired into any screen yet |
| 05_misc | pending |

## 01_full_sheet/ -- everything about the unit

HP/AC/MD/SPD(/INIT), all 6 attributes, weapon to-hit + damage, gear/carry,
languages, racial ability.

**Done:**
- The shared modal (`sheet_panel.SheetModalMixin`, popped open
  identically from six screens -- group, guild, level, market, reward,
  squad) and the two plain-text renderers (`battle_screen._draw_inspect`,
  `char_editor_screen`'s live preview) all draw through `gartok.ui.
  sheet_card.draw_sheet` now, in the war-table palette. `gartok/sheet.py`
  (the old plain-text renderer) is gone.
- `guild_screen.png` -- the left roster rows (`04_roster_row`) AND the 
  permanently-embedded right-column detail panel were fully migrated to 
  `sheet_card.draw_row` and `draw_sheet`.

**Still pending** (screenshots kept below):
- `draft_screen_gallery.png` -- `DraftScreen._draw_card`, a from-scratch
  reimplementation (plus archetype tag pills) that never touched
  `sheet_panel` at all. Not migrated: it interleaves `edit_mode` (swap
  race/occupation inline) and per-chip tooltips the shared component
  doesn't have a slot for yet.

## 02_combat_card/ -- "can this unit fight or be recruited" snapshot

HP/AC/MD/Speed + weapon one-liner + CHA-or-copper + languages/ability
blurb + tags. `squad_screen.png` (arena squad picking), `taverna_screen.png`
and `prison_screen.png` (recruit-pitch / bail candidates) all hand-roll
this independently, and taverna's and prison's versions are close to a
line-for-line duplicate of each other (same author, same shape, copy-pasted
screen-to-screen rather than shared).

`taverna_screen.png` and `prison_screen.png` also each carry a second,
smaller pattern at the bottom -- the "YOUR PARTY" strip (CHA mod,
languages, N slots free, a state tag). That strip is its own near-perfect
duplicate between the two screens and is a good second, smaller
component to extract alongside the candidate card itself.

**Done:**
- `squad_screen.py`, `taverna_screen.py`, and `prison_screen.py` were fully refactored to use `gartok/ui/combat_card.py` (`draw_combat_card` and `draw_party_row`). The old bespoke components have been deleted.
- The screenshots have been deleted.

## 03_gear_card/ -- inventory/loadout, no combat stats

Load bar + equipped slots (hand/off/armor) + pack list. No HP/AC anywhere
in this group -- it's a genuinely different concern from the two groups
above.

**Done:** `bank_screen.py` and `city_property_screen.py` are fully
rewritten on `gartok/ui/loadout_panel.py`'s `rail`/`column` (the same
pieces `group_screen.py` already used) plus two new shared pieces,
`shop_row`/`container_panel`, for the external side (the strongbox / the
house). Both screenshots are gone from this folder. What actually
changed, beyond the visual rebuild: equip slots are live drop zones now
(a weapon can land straight in a member's hand from the chest, the house,
or another member's pack -- not pack-only like before), the chest/house
stopped being a flat unstacked list (`Guild.bank_items`/
`property_city_items` are real `[(name, qty)]` stacks now, with a `- N +`
stepper on the container's own rows), and money is pooled for the visit
and settled back out proportional to what each member walked in with
(`economy.settle_pooled_purse`) instead of bank's old "charge whoever's
poorest right now" or being untouched. A member's own pack still always
moves as a whole stack (split it on the group screen first for less) --
only the container side got the stepper, matching what `group_screen`'s
pack rows already do.

- `market_screen.png` -- its bespoke loadout cards were replaced with
  `loadout_panel.column`, bringing it visually in line with the rest of
  the game while preserving the custom stock list, category tabs, and
  haggling logic. Buying from stock now supports dropping directly into
  an equip slot (hand/armor).
- `loot_screen.png` -- migrated to `loadout_panel.container_panel`.
- `gear_screen.py` and `group_screen.py` already call `loadout_panel.column()`
  directly. All `03_gear_card` screens are fully standardized.

## 04_roster_row/ -- compact list item, one pluggable trailing stat

Token + name + race/occupation, plus exactly one extra fact the screen
cares about: `hunt_screen.png` (rations, work XP), `crafting_screen.png`
(recipe count / in-progress flag), `reward_screen.png` (copper),
`justice_screen.png` (crime count), `wilds_claim_screen.png` (nothing
extra at all -- just token + name). `level_screen.png`'s header strip is
the same pattern too (name + token + HP), sitting above the unrelated
talent-tree body that this audit doesn't otherwise touch.

`gartok.ui.sheet_card.draw_row` exists in code (built alongside the rest
of the component) and is now used by `guild_screen`'s list and the six
other screens. It supports a `draw_trailing` callback that allows each
screen to inject its own extra facts on the right side.

**Done:**
- `04_roster_row` is fully migrated. `hunt_screen`, `crafting_screen`,
  `reward_screen`, `justice_screen`, `wilds_claim_screen`, and the
  `level_screen` header all use `draw_row` now.
- `hunt_screen` and `reward_screen` were converted from horizontal
  cards to standard vertical lists. The *screen* (the hunting mechanic) obviously stays --
  but its bespoke `_draw_party` card is one of the thinnest, least
  justified custom renderers in the game. It shows less than the generic
  roster row would need to anyway.

## 05_misc/ -- doesn't cleanly fit either bucket

`draft_screen_identity.png` -- the leader-pick row (token, name,
race/occupation, all 6 raw attribute scores, no HP/AC/weapon at all).
Used exactly once, nowhere else in the game shows attributes alone
without at least HP/AC alongside them.

**Done:** Migrated to use `draw_row` with a `draw_trailing` callback
that renders the 6 raw attributes.

---

## Net effect once everything below collapses

| Group | Screens hand-rolling it today | Target |
|---|---|---|
| Full sheet | ~~sheet_panel~~, ~~char_editor~~, ~~battle_screen~~, draft_screen, ~~guild_screen~~ | 1 component, 3 chrome variants |
| Combat/candidate card | ~~squad_screen~~, ~~taverna_screen~~, ~~prison_screen~~ | 1 component + 1 party-fit-row |
| Gear/loadout card | ~~bank~~, ~~city_property~~, ~~market~~, ~~loot~~, ~~group_screen~~, ~~gear_screen~~ | 1 component |
| Roster row | ~~guild_screen~~, ~~hunt_screen~~, ~~crafting_screen~~, ~~reward_screen~~, ~~justice_screen~~, ~~wilds_claim_screen~~, ~~level_screen (header)~~ | 1 component |
| Misc (attributes-only row) | ~~draft_screen (identity phase)~~ | folds into roster row or combat card |

Struck-through entries are done. The `char_editor_screen`'s *editable
form* (left column) stays out of scope for all of this -- it's an editor,
not a display, and doesn't need to share chrome with anything above.
