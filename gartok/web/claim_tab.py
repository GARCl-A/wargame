"""The Wilds Claim in the browser: on leather the band here (what each one carries toward the claim), on paper
the claim's six stages, the one in hand with its work, and the hearth once the region is swept.

The rules are `claim_desk.ClaimDesk`'s, which pygame's `WildsClaimScreen` reads too: scouting, the Lumber for
the fences, the garrison, the campfire and the oven are its. The verbs that leave the claim (the two fights,
the garrison) live on `HubSession`, which holds the map.
"""

from .. import economy, i18n, orders, wagon_watch
from ..claim_desk import ClaimDesk
from ..guild_claim import WILDS_CLAIM_STAGES
from .shop_tab import _portrait

STEPS = tuple((stage, f"claim_tab.step.{stage}") for stage in
              ("SCOUTED", "CLEARED", "FENCED", "SWEPT", "SUSTAINING", "ESTABLISHED"))
FIGHTS = {"SCOUTED": ("fight_clear", "claim_tab.fight.clear", economy.WILDS_CLAIM_CLEAR_SIZE, economy.WILDS_CLAIM_CLEAR_LEVEL),
          "FENCED": ("fight_sweep", "claim_tab.fight.sweep", economy.WILDS_CLAIM_SWEEP_SIZE, economy.WILDS_CLAIM_SWEEP_LEVEL)}
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
        return orders.holds_post(self.group.order)

    def _actions(self):
        """`(verb, label, enabled, why)` for the stage in hand, as pygame's panel offers them."""
        g, stage = self.guild, self.stage
        if stage == "NONE":
            return [("scout", i18n.t("claim_tab.scout_land_h", wilds_claim_scout_hours=economy.WILDS_CLAIM_SCOUT_HOURS), True, None)]
        if stage in FIGHTS:
            verb, label, _, _ = FIGHTS[stage]
            return [(verb, i18n.t(label), True, None)]
        if stage == "CLEARED":
            carried, have = self.s._party_lumber(), g.wilds_claim_fence_lumber
            return [("deposit", i18n.t("claim_tab.deposit_carried_lumber"), carried > 0, None if carried else i18n.t("claim_tab.nobody_carries_lumber")),
                    ("build", i18n.t("claim_tab.build_fences_h", wilds_claim_fence_hours=economy.WILDS_CLAIM_FENCE_HOURS),
                     have >= economy.WILDS_CLAIM_FENCE_LUMBER,
                     None if have >= economy.WILDS_CLAIM_FENCE_LUMBER else i18n.t("claim_tab.lumber_banked", have=have, wilds_claim_fence_lumber=economy.WILDS_CLAIM_FENCE_LUMBER))]
        if stage == "SWEPT":
            return [("garrison", i18n.t("claim_tab.garrison_here"), True, None)]
        if self.seized:
            return []
        out = []
        if self.garrisoned_here:
            if stage == "SUSTAINING":
                out.append(("leave_garrison", i18n.t("claim_tab.stand_down_garrison"), True, None))
        elif stage == "SUSTAINING" and g.claim_garrison() is None:
            out.append(("garrison", i18n.t("claim_tab.garrison_here"), True, None))
        return out

    def act(self, verb):
        """Run one of the stage's own pieces of work (not a fight nor the garrison: `HubSession` plays those).
        -> the stint the band takes for it, or None for work with no hours (the report says what came of it)."""
        work = {"scout": self.s._scout, "deposit": self.s._deposit_lumber, "build": self.s._build_fences,
                "leave_garrison": self.s._leave_garrison, "campfire": self.s._light_campfire,
                "oven": self.s._build_oven}.get(verb)
        if work is None or verb not in {a[0] for a in self._actions() if a[2]} | self._hearth_verbs():
            raise ValueError(i18n.t("claim_tab.nothing_to_at_claim_now", replace=verb.replace('_', ' ')))
        order = work()
        notice, self.s.notice = self.s.notice, None
        self.report = [notice] if notice else []
        return order

    def start_garrison(self):
        if "garrison" not in {a[0] for a in self._actions()}:
            raise ValueError(i18n.t("claim_tab.there_is_no_claim_to"))
        self.s._start_garrison()

    def fight(self, verb):
        if self.stage not in FIGHTS or FIGHTS[self.stage][0] != verb:
            raise ValueError(i18n.t("claim_tab.there_is_no_fight_to"))
        return i18n.t(FIGHTS[self.stage][1])

    def _hearth(self):
        g = self.guild
        if self.stage not in ("SWEPT", "SUSTAINING", "ESTABLISHED") or self.seized:
            return None
        crew = self.group.carriers
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
            return [i18n.t("claim_tab.land_is_not_scouted_yet"),
                    i18n.t("claim_tab.it_takes_h_no_fight", wilds_claim_scout_hours=economy.WILDS_CLAIM_SCOUT_HOURS)]
        if stage in FIGHTS:
            _, _, size, level = FIGHTS[stage]
            first = (i18n.t("claim_tab.scouted_something_already_lives_here")
                     if stage == "SCOUTED" else
                     i18n.t("claim_tab.fenced_one_more_pass_root"))
            return [first, i18n.t("claim_tab.real_fight_opponents_level", size=size, level=level)]
        if stage == "CLEARED":
            return [i18n.t("claim_tab.cleared_raise_fences_to_hold")]
        if stage == "SWEPT":
            return [i18n.t("claim_tab.swept_clean_claim_only_counts"),
                    i18n.t("claim_tab.days_uninterrupted_lost_raid_or", wilds_claim_sustain_days=economy.WILDS_CLAIM_SUSTAIN_DAYS)]
        if stage == "SUSTAINING":
            return [i18n.t("claim_tab.garrison_holds_claim_each_whole")]
        if self.seized:
            return [i18n.t("claim_tab.seized_occupiers_hold_claim_right"),
                    i18n.t("claim_tab.travel_band_here_to_fight")]
        return [i18n.t("claim_tab.established_land_is_guild_s")]

    def _member(self, u):
        held = [{"name": n, "qty": u.count_of(n)} for n in CARRIED if u.count_of(n)]
        return {"uid": u.uid, "name": u.name, "portrait": _portrait(u),
                "sub": i18n.t("claim_tab.hp", race=u.race_label, hp=u.hp, hp_max=u.hp_max), "held": held}

    def hub_cards(self):
        g, stage = self.guild, self.stage
        cards = [{"label": i18n.lab("stage"), "value": i18n.t("claim_tab.seized") if self.seized else i18n.name("claim_stage", stage),
                  "tone": "bad" if self.seized else "good" if stage == "ESTABLISHED" else None}]
        if stage == "CLEARED":
            cards.append({"label": i18n.t("claim_tab.lumber_banked_2"), "value": f"{g.wilds_claim_fence_lumber} / {economy.WILDS_CLAIM_FENCE_LUMBER}"})
        elif stage == "SUSTAINING":
            cards.append({"label": i18n.t("claim_tab.days_to_hold"), "value": str(g.wilds_claim_sustain_days_left)})
        return cards

    def state(self):
        g, stage = self.guild, self.stage
        at = WILDS_CLAIM_STAGES.index(stage)
        steps = [{"key": k, "label": i18n.t(lbl), "state": "done" if WILDS_CLAIM_STAGES.index(k) <= at else
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
                "hearth": self._hearth(), "watch": watch,
                "members": [self._member(u) for u in self.group.members], "report": self.report}
