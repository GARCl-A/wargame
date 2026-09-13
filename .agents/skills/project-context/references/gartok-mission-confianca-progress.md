---
name: gartok-mission-confianca-progress
description: "The Bankers' trust-mission arc (crime/guard, Old Road ambush, chest, the mission itself) is fully shipped"
metadata: 
  node_type: memory
  type: project
  originSessionId: 7a1286a0-9158-4790-8ece-64a7ad582b3a
  modified: 2026-09-13T16:51:34.310Z
---

Done, all 4 systems, committed 2026-09-12/13 across 4 commits (plus a small
fix-up commit for a regression found mid-arc). The design doc that tracked
this (`docs/plans/missao-confianca-banqueiros.md`) was deleted once it
closed out -- its job was letting a memory-less session resume mid-arc, and
there is no arc left to resume. What shipped:

- **Sistema 1** -- `Unit.crime`, `world.Node.jurisdiction`, `Guild.jailed`,
  a "guard" pause in `campaign.advance`, `justice_screen.GuardScreen` (accept
  prison / fight the patrol / flee).
- **Sistema 2** -- the Old Road (`world.Node.unsafe`) rolls an ambush per
  travel leg, same pause/resume seam as the guard.
- **Sistema 3** -- a generic locked chest (`chest.py`), picked via
  `gear_screen.py`'s right-click menu.
- **Sistema 4** -- the Bankers' trust mission: Ankareth (renamed "The City")
  hands out a sealed chest, Ledger Hold (a new fortress node) trades it for a
  letter (one ambush along the way, mission-conditional not node-permanent),
  turning the letter in banks the `bankers_trust` deed once the 3 economic
  deeds are already done -- reputation with the Bankers reaches 4.

Why this matters: this was the gate for buying guild property in the city,
itself a prerequisite for [[gartok-open-world-vision]]'s base-building.

**How to apply:** property-in-the-city / base-building is the natural next
initiative in this thread, but it needs its own fresh design doc -- nothing
here to resume, just context for why the Bankers arc existed.
