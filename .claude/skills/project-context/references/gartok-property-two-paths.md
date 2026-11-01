---
name: gartok-property-two-paths
description: "GARTOK guild property (two paths — City via the Bankers, or claim+build+defend in The Wilds): ALL FOUR SISTEMAS SHIPPED 2026-09-13, arc fully closed, plan doc deleted per project convention"
metadata: 
  node_type: memory
  type: project
  originSessionId: 8f4875d4-b5e4-4577-b893-89dbeb65ac35
  modified: 2026-09-13T19:35:01.055Z
---

Design conversation, 2026-09-13, closed after a long critical anamnesis (the
user's own term) across several rounds -- every structural question got a
decision, nothing left to re-ask. All four systems shipped the same session,
one after another, each with its own tests, none requested to stop between
them. **The plan doc (`docs/plans/propriedade-guilda-dois-caminhos.md`) is
DELETED** -- same convention as `missao-confianca-banqueiros.md` before it:
a plan doc lives only until its arc fully ships, then this memory is the
permanent record instead. Do not look for that file; if a future session
wants the blow-by-blow design rationale, it isn't recoverable except via
`git log`/`git show` on that path (the trust-mission doc's own precedent for
how that recovery works, if it's ever actually needed).

This is the concrete shape of "base-building," the initiative
[[gartok-mission-confianca-progress]] flagged as the natural next step once
Bankers reputation hit 4 (already true as of the trust-mission arc closing).
Part of [[gartok-open-world-vision]]'s base-building pillar -- and explicitly
scoped as the seed of a much bigger future initiative (autonomous-work
simulation: crafting, training, magic, caravans, armies), NOT that whole
system. v1 ships only one representative autonomous job (Wilds wood
gathering) to prove the "leave someone working, come back later" payoff
without building the rest.

## Sistema 2 (City property) SHIPPED 2026-09-13

Same session as the design -- the user said "pode implementar" right after
the doc was written, no separate session needed. Buy from the Bankers (rep
gate 4, `economy.CITY_PROPERTY_*`), an automatic recurring tax
(`Guild._city_property_upkeep`, called from `_daily_upkeep`, no screen/click
needed), a missed-payments counter that trips a forced `RepossessionScreen`
(return -> debt that blocks Bankers services + escalates to the guard after
a grace period; squat -> no more tax but the guard now raids the place --
a genuinely new `"eviction"` order kind in `orders.py`/`campaign.py`, same
shape as `"guard"`/`"ambush"`, not a stub). New file
`gartok/city_property_screen.py` (`CityPropertyScreen` + `RepossessionScreen`,
the latter reusing `justice_screen.GuardScreen`'s layout with 2 options
instead of 3). 21 tests in `tests/test_city_property.py`.

## Sistema 1 (garrison engine) SHIPPED 2026-09-13, same session, right after Sistema 2

Only the ENGINE, deliberately no UI -- "lógica antes de UI", the doc's own
stated principle (same as the Groups refactor). No real node offers a job yet
(neither the City nor today's Hunt-only Wilds node) -- that only happens once
Sistema 3 adds the Wilds territory node. Tested by forcing `garrison_job` on a
stand-in node, same trick `test_road_ambush.py` uses for `world.ROAD_AMBUSH_CHANCE`.

- `orders.py`: `Order(kind="garrison", job=...)`, factory `orders.garrison(job)`
  -- neither `AUTO_KINDS` nor `INTERACTIVE_KINDS`. No `dest` field (unlike the
  plan doc's first draft) -- a garrison never travels, it sits where the group
  already is.
- **The `busy`/split-merge fix landed WITHOUT changing `busy`'s meaning**:
  `busy` still reports True for a garrison order (needed so
  `Guild.needs_orders`/`can_auto_advance` keep working -- a garrisoned group
  must not look "idle" and force the map to stop every tick). Instead, added
  `Group.locked` = busy-minus-garrison; `split_group`/`merge_groups` check
  `locked`, not `busy`. `campaign.advance` separately excludes
  `kind == "garrison"` from its `active`/chase list (a garrison has no
  `eta`/`remaining` to complete). **If a future session is tempted to make
  `busy` itself return False for garrison, don't -- that was tried in
  reasoning and rejected, it breaks auto-advance whenever a garrison exists.**
- Daily production: `Guild._garrison_upkeep` (from `_daily_upkeep`, like
  food). Storage is generic per NODE, not per "property":
  `guild.garrison_stock = {node_id: [items]}` -- works for any future job
  site, not hard-wired to City or Wilds specifically.
  `economy.GARRISON_JOBS = {"lumber": "Lumber"}`,
  `economy.GARRISON_YIELD_PER_MEMBER_PER_DAY = 1` (placeholder).
- Item named **"Lumber"**, not "Wood" -- the game already had a flavour item
  "1kg Firewood" (Woodcutter's starting kit, `data.py`), and "Wood" right next
  to it would read as the same stuff. `data.ITEM_WEIGHTS["Lumber"] = 2.0`.
- **Bug found and fixed along the way**: Sistema 2 had shipped without ever
  touching `persist.py` -- none of its new `Guild` fields
  (`property_city_unlocked` etc.) were saved or loaded, so a bought/repossessed/
  squatted property silently reset on every save/load. Fixed together with
  wiring `garrison_stock` into the same file. Tests for both live in
  `tests/test_garrison.py` (16 tests) alongside the garrison engine tests.

## Sistema 3 (Wilds claim campaign) SHIPPED 2026-09-13, same session, right after Sistema 1

The node Sistema 1 was waiting for: `world.wilds_territory` ("The Claim"),
`claim=True`, `garrison_job="lumber"` baked in from birth, linked to `wilds`
by a 2h edge. New screen `wilds_claim_screen.WildsClaimScreen`.

- **The doc's 6 numbered "etapas" collapsed into 5 state transitions** -- the
  stage list already closed in "Decisões já fechadas"
  (`NONE->SCOUTED->CLEARED->FENCED->SWEPT->SUSTAINING->ESTABLISHED`) only has
  room for 5, so "Desmatar" (etapa 3) is NOT its own state -- it's folded
  into the CLEARED->FENCED transition (raising fences implies clearing
  enough to raise them). If a future session is asked to add a distinct
  "deforested" stage, that's a real, deliberate scope change, not a bug to
  fix.
- SCOUT (`wilds_claim_scout`): pure time gate, no check, same status the doc
  left open. CLEAR and SWEEP: two REAL scaled fights
  (`encounters.build_enemy`), not checks or time gates -- app runs them via
  `app._start_claim_battle` (whole present group, no `SquadScreen`, no
  stake), and `App._battle_end`'s new `_claim_stage_pending` hook advances
  the stage on a win, falls through to the normal loot/`_after_activity`
  path otherwise (a claim fight is never a `pause_order`/hunt/arena bout).
- **Bootstrap problem solved**: nothing produces Lumber before the claim
  exists (the lumber yard deliberately pays wage only, never wood -- old,
  intentional flavor). Fix: Lumber is now buyable at the Market
  (`economy.LUMBER_PRICE = 6`, added to `MARKET_STOCK`/`PRICES`) -- haul it
  out by hand to raise the fences. Once `ESTABLISHED`, the garrison produces
  its own and the import loop ends.
- **The SUSTAINING raid does NOT reuse the City's "eviction" arrival-trigger
  mechanism** -- a garrisoned group never "arrives" again once
  `orders.garrison` is issued (excluded from `active` on purpose, Sistema 1).
  New `campaign._wilds_claim_raid_check` runs directly inside `advance()`
  instead (once per call, not scaled to days), independent of any arrival.
  Losing (`campaign.resolve_wilds_raid`) only resets the sustain countdown,
  never the stages already done; winning reissues the exact same
  `orders.garrison(job)` it interrupted.
- **Sistema 4's own attack-on-ESTABLISHED should probably generalize this
  raid pair rather than duplicate it** -- same shape, different gate stage
  and a different loss consequence (seizure, not just a timer reset). Left
  as a note in the plan doc for whoever builds Sistema 4.
- Tests: `tests/test_wilds_claim.py`, 24 tests, including a real pygame draw
  pass over every one of the 7 stage panels.

## Sistema 4 (Wilds attack/retake) SHIPPED 2026-09-13, same session, right after Sistema 3

Closes the risk loop: once `ESTABLISHED`, `guild.wilds_claim_owner`
("guild" | "seized") is the new ownership flag Sistema 3 didn't need.

- **Did generalize the SUSTAINING raid pair, as planned**: `campaign.
  _wilds_claim_attack_check` is the single dispatcher `advance()` now calls
  -- routes to the existing `_wilds_claim_raid_check` while `SUSTAINING`, or
  the new `_wilds_claim_seizure_check` once `ESTABLISHED` + still
  `owner == "guild"`. Kept as two separate roll functions underneath (the
  unguarded-auto-seize branch has no analogue in the sustain raid, and the
  loss consequence differs -- ownership transfer vs. a timer reset), but the
  entry point and the pack-building are shared in spirit, not duplicated
  blindly.
- **Unguarded + ESTABLISHED = silent seizure, no fight** -- exactly as the
  doc specified. Garrisoned = a real fight (`"wilds_seizure"` order kind,
  `campaign.resolve_wilds_seizure`): winning resumes the same garrison job,
  losing seizes the node (structure stands, ownership flips) with no "reset
  and try again" the way a SUSTAINING loss gets.
- **Retaking is arrival-triggered, unlike the seizure check** -- travelling
  TO a seized claim runs into the occupiers on arrival
  (`campaign._wilds_claim_retake_catch`, added to `_arrival_pause`'s chain,
  same shape as `_fortress_ambush_catch`). Winning
  (`campaign.resolve_wilds_claim_retake`) flips ownership back with no redo
  of Sistema 3's campaign -- the structure was never touched, only who holds
  it. This is the one Sistema 4 mechanism that DOES reuse an existing seam
  rather than needing a new one, because retaking genuinely is a normal
  "walk up and fight for it" arrival, unlike a standing garrison that never
  arrives twice.
- `wilds_claim_screen.WildsClaimScreen`'s ESTABLISHED panel now branches on
  `wilds_claim_owner`: seized shows a plain notice and no COLLECT button
  (can't loot ground you don't hold); this state IS reachable through the
  screen (not just theoretical) -- the garrison group that just lost a
  seizure fight is still standing right there, order idled, and can reopen
  the screen without ever "arriving" again.
- Reused `economy.WILDS_RAID_CHANCE`/`LEVEL`/`SIZE` for the seizure/retake
  rolls too, rather than inventing a second tuning knob for what's the same
  kind of threat against the same ground -- same "simple first" treatment
  every other number in this arc got before anyone played it.
- Added a capstone integration test
  (`test_the_full_wilds_claim_lifecycle_end_to_end`,
  `tests/test_wilds_ops.py`) that plays scout -> clear -> fence -> sweep ->
  garrison -> sustain -> established -> seized -> retaken in one go, through
  the real screen/app/campaign wiring -- catches seam bugs the narrower
  per-system tests can't.

Total suite: 506 tests green. **The whole base-building initiative is
closed** -- both paths (City, Wilds) fully playable start to finish,
including losing and recovering each one.

## What's explicitly still future work (not a gap in what shipped)

Everything the plan doc's own "Fora de escopo" section named up front, still
true: no autonomous job besides Wilds Lumber-gathering (City has none), no
mechanical battle-map cover from fences (still a checklist step only), no
group-AI automation (every hauling trip is still manual), no per-unit job
choice inside a garrison. None of these are bugs to fix -- they're the next
initiative's scope, whenever that comes up. [[gartok-open-world-vision]]'s
bigger autonomous-work simulation (crafting, training, magic, caravans,
armies) is the natural home for picking this back up.

## Headline decisions (see the plan doc for full detail + open tuning questions)

- Not mutually exclusive by rule, exclusive in practice: City costs a
  recurring tax, Wilds costs a standing garrison against periodic attack --
  early-game the guild can't afford both.
- City = subordinate to a jurisdiction that isn't the guild's; Wilds =
  guild's own claimed territory, guild BECOMES the local jurisdiction
  (inverts [[gartok-mission-confianca-progress]]'s crime/jurisdiction system
  locally).
- Garrison = a `Group` parked at the property node with a new `"garrison"`
  order kind, not a detached unit pool -- gets food/hunger for free from the
  existing per-group daily upkeep. **Shipped** -- see the Sistema 1 section
  above for exactly how the `busy`/split-merge snag was actually resolved
  (not the way the plan doc first sketched it). See [[gartok-groups-refactor]].
- Wilds claim = a mini-campaign (scout -> fight -> fence [folds in
  deforesting] -> sweep -> sustain-for-N-days), all on one new map node
  distinct from the existing Hunt node. Losing the *sustain* stage only
  resets that stage (garrison + timer), not the earlier progress.
  **Shipped** -- see the Sistema 3 section above for exactly how the
  6-item etapa list became 5 real transitions.
- An unguarded Wilds property is not safe -- it can be silently seized
  (no fight, nobody to contest it). A guarded one that loses its defense
  fight is also seized, but the physical structure survives either way --
  retaking it is a normal fight against the occupiers, never a redo of the
  claim campaign. **Shipped** -- see the Sistema 4 section above.
- City tax default escalates to a repossession offer (return + debt that
  blocks Bankers services until paid, prolonged non-payment escalates to the
  guard) or squatting (guard periodically attacks the property until the
  guild gives up or, near-impossibly at current power levels, beats the
  whole city guard). **Shipped as described** -- see the Sistema 2 section
  above for the actual numbers chosen.
- Fences are meant to eventually grant real battle-map cover (a translucent,
  climb/jump/fly-over obstacle) -- deliberately deferred, v1 treats "build
  fences" as a checklist step only, no combat-terrain hookup yet.

**How to apply:** The whole base-building initiative (all four systems) is
done -- don't re-implement any of it, don't re-litigate the design with the
user, don't "fix" `Group.busy` to exclude garrison (considered and rejected,
Sistema 1), don't add a separate "deforested" stage (Sistema 3), and don't
duplicate the raid/seizure roll logic if extending it further (Sistema 4
already generalized the entry point once). The plan doc is gone -- this
memory is now the only record of the design rationale. If the user asks
what's next for base-building, it's the "Fora de escopo" list above
(autonomous jobs beyond Lumber, mechanical fence cover, group automation,
per-unit garrison jobs) -- a genuinely new initiative, not a continuation of
this one.
