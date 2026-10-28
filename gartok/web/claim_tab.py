"""The Wilds Claim in the browser: on leather the band here (what each one carries toward the claim), on paper
the claim's six stages, the one in hand with its work, and the hearth once the region is swept.

The rules are `claim_desk.ClaimDesk`'s, which pygame's `WildsClaimScreen` reads too: scouting, the Lumber for
the fences, the garrison and its job, the campfire, the oven and the banked Lumber are its. The
verbs that leave the claim (the two fights, the garrison) live on `HubSession`, which holds the map.
"""

from .. import economy, wagon_watch
from ..claim_desk import ClaimDesk
from ..guild_claim import WILDS_CLAIM_STAGES
from .shop_tab import _portrait

STEPS = (("SCOUTED", "Scout"), ("CLEARED", "Clear"), ("FENCED", "Fence"), ("SWEPT", "Sweep"),
         ("SUSTAINING", "Garrison"), ("ESTABLISHED", "Established"))
FIGHTS = {"SCOUTED": ("fight_clear", "Clear the land", economy.WILDS_CLAIM_CLEAR_SIZE, economy.WILDS_CLAIM_CLEAR_LEVEL),
          "FENCED": ("fight_sweep", "Sweep the region", economy.WILDS_CLAIM_SWEEP_SIZE, economy.WILDS_CLAIM_SWEEP_LEVEL)}
CARRIED = ("Lumber", economy.CLAIM_OVEN_BRICK)


class ClaimTab:
    def __init__(self, guild, group, node):
        self.s = ClaimDesk(guild, group)
        self.guild, self.group, self.node = guild, group, node
        self.report = []                # what the last piece of work said

    @property
    def stage(self):
        return self.guild.wilds_claim_stage

    @property
    def seized(self):
        return self.guild.wilds_claim_owner == "seized"

    @property
    def garrisoned_here(self):
        o = self.group.order
        return o is not None and o.kind == "garrison"

    def _actions(self):
        """`(verb, label, enabled, why)` for the stage in hand, as pygame's panel offers them."""
        g, stage = self.guild, self.stage
        if stage == "NONE":
            return [("scout", f"Scout the land · {economy.WILDS_CLAIM_SCOUT_HOURS} h", True, None)]
        if stage in FIGHTS:
            verb, label, _, _ = FIGHTS[stage]
            return [(verb, label, True, None)]
        if stage == "CLEARED":
            carried, have = self.s._party_lumber(), g.wilds_claim_fence_lumber
            return [("deposit", "Deposit the carried Lumber", carried > 0, None if carried else "nobody carries Lumber"),
                    ("build", f"Build the fences · {economy.WILDS_CLAIM_FENCE_HOURS} h",
                     have >= economy.WILDS_CLAIM_FENCE_LUMBER,
                     None if have >= economy.WILDS_CLAIM_FENCE_LUMBER else f"{have} / {economy.WILDS_CLAIM_FENCE_LUMBER} Lumber banked")]
        if stage == "SWEPT":
            return [("garrison", "Garrison here", True, None)]
        if self.seized:
            return []
        out = []
        if stage == "ESTABLISHED":
            stock = g.garrison_stock_at(self.group.node)
            out.append(("collect", "Collect the Lumber", bool(stock), None if stock else "nothing banked yet"))
        if self.garrisoned_here:
            hold = self.group.order.job == "hold"
            out.append(("garrison_job", "Gather Lumber instead" if hold else "Just hold the claim (rest)", True, None))
            if stage == "SUSTAINING":
                out.append(("leave_garrison", "Stand down the garrison", True, None))
        elif stage == "SUSTAINING" and g.claim_garrison() is None:
            out.append(("garrison", "Garrison here", True, None))
        return out

    def act(self, verb):
        """Run one of the stage's own pieces of work (not a fight nor the garrison: `HubSession` plays those)."""
        work = {"scout": self.s._scout, "deposit": self.s._deposit_lumber, "build": self.s._build_fences,
                "leave_garrison": self.s._leave_garrison, "garrison_job": self.s._toggle_garrison_job,
                "collect": self.s._collect_lumber, "campfire": self.s._light_campfire,
                "oven": self.s._build_oven}.get(verb)
        if work is None or verb not in {a[0] for a in self._actions() if a[2]} | self._hearth_verbs():
            raise ValueError(f"nothing to {verb.replace('_', ' ')} at the claim now")
        work()
        notice, self.s.notice = self.s.notice, None
        self.report = [notice] if notice else []

    def start_garrison(self):
        if "garrison" not in {a[0] for a in self._actions()}:
            raise ValueError("there is no claim to garrison yet")
        self.s._start_garrison()

    def fight(self, verb):
        if self.stage not in FIGHTS or FIGHTS[self.stage][0] != verb:
            raise ValueError("there is no fight to pick at the claim now")
        return FIGHTS[self.stage][1]

    def _hearth(self):
        g = self.guild
        if self.stage not in ("SWEPT", "SUSTAINING", "ESTABLISHED") or self.seized:
            return None
        crew = self.group.members
        fuel = sum(m.count_of(economy.CAMPFIRE_FUEL) for m in crew)
        bricks = sum(m.count_of(economy.CLAIM_OVEN_BRICK) for m in crew)
        return {"lit": bool(g.wilds_claim_campfire), "oven": bool(g.claim_oven), "can_cook": bool(g.wilds_claim_can_cook),
                "fuel": economy.CAMPFIRE_FUEL, "fuel_have": fuel, "fire_hours": economy.CAMPFIRE_HOURS,
                "dc": economy.CAMPFIRE_DC, "brick": economy.CLAIM_OVEN_BRICK, "bricks_have": bricks,
                "bricks_need": economy.CLAIM_OVEN_BRICKS, "oven_hours": economy.CLAIM_OVEN_HOURS,
                "can_fire": fuel > 0 and not g.wilds_claim_can_cook,
                "can_oven": bricks >= economy.CLAIM_OVEN_BRICKS and not g.claim_oven}

    def _hearth_verbs(self):
        h = self._hearth()
        return {v for v, on in (("campfire", h and h["can_fire"]), ("oven", h and h["can_oven"])) if on}

    def _lines(self):
        stage = self.stage
        if stage == "NONE":
            return ["The land is not scouted yet: someone has to walk it before the guild can do anything else here.",
                    f"It takes {economy.WILDS_CLAIM_SCOUT_HOURS} h. No fight, no roll."]
        if stage in FIGHTS:
            _, _, size, level = FIGHTS[stage]
            first = ("Scouted. Something already lives here: clear it out before building anything."
                     if stage == "SCOUTED" else
                     "Fenced. One more pass: root out any nest or bandit camp still close enough to matter.")
            return [first, f"A real fight: {size} opponents, level {level}."]
        if stage == "CLEARED":
            return ["Cleared. Raise fences to hold the ground, with Lumber hauled here from the Market or the Yard."]
        if stage == "SWEPT":
            return ["Swept clean. The claim only counts once someone holds it: garrison this band here and sustain it.",
                    f"{economy.WILDS_CLAIM_SUSTAIN_DAYS} days, uninterrupted. A lost raid or pulling out early starts the count over."]
        if stage == "SUSTAINING":
            return ["The garrison holds the claim; each whole day with someone here counts down."]
        if self.seized:
            return ["Seized. Occupiers hold the claim right now: the structure still stands, it is just not the guild's to work.",
                    "Travel a band here to fight for it back: only the ground needs retaking, not the whole campaign."]
        return ["Established. The land is the guild's: the garrison keeps working it on its own."]

    def _member(self, u):
        held = [{"name": n, "qty": u.count_of(n)} for n in CARRIED if u.count_of(n)]
        return {"uid": u.uid, "name": u.name, "portrait": _portrait(u),
                "sub": f"{u.race['name']} {u.occupation['name'].lower()} · HP {u.hp} / {u.hp_max}", "held": held}

    def hub_cards(self):
        g, stage = self.guild, self.stage
        cards = [{"label": "stage", "value": "Seized" if self.seized else stage.title(),
                  "tone": "bad" if self.seized else "good" if stage == "ESTABLISHED" else None}]
        if stage == "CLEARED":
            cards.append({"label": "lumber banked", "value": f"{g.wilds_claim_fence_lumber} / {economy.WILDS_CLAIM_FENCE_LUMBER}"})
        elif stage == "SUSTAINING":
            cards.append({"label": "days to hold", "value": str(g.wilds_claim_sustain_days_left)})
        elif stage == "ESTABLISHED" and not self.seized:
            cards.append({"label": "lumber banked", "value": str(len(g.garrison_stock_at(self.group.node)))})
        return cards

    def state(self):
        g, stage = self.guild, self.stage
        at = WILDS_CLAIM_STAGES.index(stage)
        steps = [{"key": k, "label": lbl, "state": "done" if WILDS_CLAIM_STAGES.index(k) <= at else
                  "now" if WILDS_CLAIM_STAGES.index(k) == at + 1 else "todo"} for k, lbl in STEPS]
        if stage == "ESTABLISHED":
            steps[-1]["state"] = "seized" if self.seized else "done"
        garrison = g.claim_garrison()
        watch = None
        if g.claim_garage_open and garrison is None and not g.claim_garage.empty:
            watch = f"{wagon_watch.flight_chance(g.claim_garage):.0%}"
        return {"cards": self.hub_cards(), "stage": stage, "seized": self.seized, "steps": steps,
                "lines": self._lines(),
                "actions": [{"verb": v, "label": lbl, "can": ok, "why": why} for v, lbl, ok, why in self._actions()],
                "fight": stage in FIGHTS,
                "lumber": {"have": g.wilds_claim_fence_lumber, "need": economy.WILDS_CLAIM_FENCE_LUMBER,
                           "carried": self.s._party_lumber()} if stage == "CLEARED" else None,
                "days_left": g.wilds_claim_sustain_days_left if stage == "SUSTAINING" else None,
                "garrison": garrison.display_name if garrison else None, "here": self.garrisoned_here,
                "job": self.group.order.job if self.garrisoned_here else None,
                "banked": len(g.garrison_stock_at(self.group.node)) if stage == "ESTABLISHED" else None,
                "hearth": self._hearth(), "watch": watch,
                "members": [self._member(u) for u in self.group.members], "report": self.report}
