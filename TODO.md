# TODO — playtest feedback (2026-10-05)

Scores 1-5. **Ease**: 5 = quick, 1 = long. **Impact**: 5 = big improvement.
Estimated from the descriptions, not the code; "verify" = check before committing to the fix.

## 1. UI bugs and inconsistencies

- [x] Foraging shows up as meat hunting (ease 5 · impact 2) — header/interlude text now follows the target
- [x] Racial level shows Lv0 on a Lv1 character (ease 5 · impact 2) — roster showed only the combat level; now "Lv <racial> (C# W#)"
- [x] Prison shows letters instead of portraits (ease 4 · impact 2) — also fixed the same gap in the arena squad screen
- [x] Guild-colour ring around tokens in combat (ease 4 · impact 5)
- [x] Portrait id stored on the Unit, same face on every screen (ease 3 · impact 4) — screens now pass it; old saves derive it from the uid instead of hash()
- [ ] Improve the found-the-guild screen (ease 2 · impact 3) — scope is vague, define what's wrong first

## 2. Combat

- [x] Dying: clock is 4 turns; a hit on a dying body ticks the clock once instead of killing it (ease 4 · impact 4)
- [x] Worlds with many saves: autosave before every fight (last 10), named manual saves, wipe keeps the world (ease 3 · impact 5)
- [ ] Auto battler with priority programming, Siralim-style (ease 1 · impact 5) — its own arc, own branch; needs UI + AI + tests

## 3. Talents

- [x] Constitution talent under Hardy: Recovery, heal 1 HP after combat (ease 4 · impact 2)
- [x] Work talent, level 3 (Steady Pace, under Brisk Hands): work counts as rest (ease 3 · impact 3)

## 4. Economy and world activities

- [x] Verify tavern study cost is actually charged (ease 4 · impact 4) — students paid, but a broke group sat there forever; now released when nobody can pay, and non-students no longer get a free room meal
- [x] Hunt/forage yield scales with party size, diminishing returns (3 hunters = 1.0, saturates at 7) (ease 3 · impact 3)
- [x] No way to leave The Wilds once inside (ease 3 · impact 4) — the hunt setup screen had no back button; added LEAVE
- [x] Pack Mule commission no longer forces a Goliath: Pack Mule and Damage Dealer merged into one strength label, STRONG; FAST, LARGE, SEES IN DARK and MAGIC removed (ease 3 · impact 3)

## 5. Inventory and group management

- [x] "Manage gear" limited to the selected group (ease 3 · impact 4) — closes item transfers between groups in different places
- [x] Coins as a real inventory item: Copper Coin stack, 200 per kg, split and move in the gear screens (ease 2 · impact 3)

## Suggested order

1. Quick wins: tavern study cost check, leaving The Wilds.
2. Then: pre-combat backup save, dying rework, portrait audit, manage-gear per group.
3. Separate arc: auto battler.
