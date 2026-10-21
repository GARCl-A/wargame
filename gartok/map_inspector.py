"""What the map's inspector shows for the selected band at its node: the blocks of each
function, the Wildfire, the gathering shifts, the REST rows and the bottom buttons
(`MapInspectorMixin`, mixed into `MapScreen`)."""

from . import (
    arena,
    economy,
    gather,
    lair,
    missions,
    node_functions,
    ox,
    rest,
    serpent_nest,
    wildfire,
)
from .constants import fmt_money
from .group import CAUTIOUS, NORMAL
from .ui.tokens import T

STANCE_NOTES = {NORMAL: "no change to the ambush chance",
                CAUTIOUS: "fewer ambushes on the road and on hunts"}


class MapInspectorMixin:
    def _wildfire_blocks(self, g, focus):
        """The inspector's rows at a wildfire focus: how long it has, the talk chain (one button a
        member, their modifier on it), and putting the fire out once the crew is beaten."""
        state = self.guild.wildfire
        day = self.guild.clock.day
        if focus.great:
            left = state.start_day + wildfire.DAYS - day
            line = f"the fortress stands in {left} day(s) unless the Ogre is stopped"
        else:
            left = focus.spawn_day + wildfire.BURN_DAYS - day
            line = f"burns through in {left} day(s), and spreads"
        blocks = [{"type": "text", "text": line, "color": T.BLOOD}]
        if focus.cleared:
            blocks += [{"type": "section", "label": "the fire", "gap_before": T.S},
                       {"type": "button", "key": "wf_put_out", "primary": True, "height": 40,
                        "label": f"PUT OUT THE FIRE ({wildfire.PUT_OUT_HOURS} h)"},
                       {"type": "wrapped_text", "color": T.TX_FAINT,
                        "text": f"the best mind of the group rolls INT vs DC {wildfire.PUT_OUT_DC} at the end  ·  "
                                "a miss can be tried again"}]
            return blocks
        if focus.hostile:
            blocks.append({"type": "text", "text": "They are coming for you.", "color": T.BLOOD})
            return blocks
        if wildfire.can_talk(focus):
            attr = wildfire.next_check(focus)
            who = "the Ogre" if focus.great else "the foreman"
            dc = wildfire.talk_dc(self.guild, focus)
            step = "get a hearing" if focus.talk == 0 else "show them how it is done"
            blocks.append({"type": "section", "label": f"talk to {who}", "gap_before": T.S})
            blocks.append({"type": "wrapped_text", "color": T.TX_FAINT,
                           "text": f"{step}: {attr[:3].upper()} vs DC {dc}  ·  a miss and they fight"})
            blocks.append({"type": "button", "key": "wf_talk", "height": 36, "gap_before": 2,
                           "label": f"TALK TO {who.upper()}"})
        return blocks

    # ------------------------------------------------------------------ #
    # INSPECTOR content                                                   #
    # ------------------------------------------------------------------ #
    def _work_line(self, g, here):
        """A work node's one line on the map: what a day's shift pays the group and whether the
        guild may gather here; the shifts themselves are the hub's WORK and GATHERING tabs."""
        day = sum(economy.work_pay(here.id, 16, economy.work_level(u, here.id)) for u in g.members)
        parts = [f"a 16 h shift pays the group {fmt_money(day)}"]
        if gather.can_gather(here.id):
            parts.append("gathering licence held" if self.guild.has_licence(here.id) else "no gathering licence")
        return {"type": "text", "color": T.TX_FAINT, "text": "  ·  ".join(parts)}

    def _has_property_business(self):
        house = self.guild.house
        return house.owned or house.squatting or self.guild.bankers_debt > 0

    def _function_notes(self, fn):
        """The text lines under a function's button: its static note, or what the guild's
        state says about it (strongbox, house, claim)."""
        guild = self.guild
        if fn.id == "bank":
            if not guild.bank.open:
                return []
            return [{"type": "text", "color": T.TX_FAINT,
                     "text": f"strongbox: {guild.bank.load:g} / {guild.bank.capacity} kg"}]
        if fn.id == "property":
            if guild.house.repossession_due:
                note, col = "the Bankers want the house back, or the tax paid", T.BLOOD
            elif guild.house.squatting:
                note, col = "squatting -- the guard can still come to clear it out", T.BRASS
            elif guild.house.owned:
                note = (f"house: {guild.house.stash.load:g} / "
                        f"{economy.CITY_PROPERTY_CAPACITY} kg")
                col = T.TX_FAINT
            else:
                note, col = f"owes the Bankers {fmt_money(guild.bankers_debt)}", T.BLOOD
            return [{"type": "text", "text": note, "color": col}]
        if fn.id == "claim":
            stage = guild.wilds_claim_stage
            if stage == "ESTABLISHED" and guild.wilds_claim_owner == "seized":
                note, col = "SEIZED -- send a group to retake it", T.BLOOD
            elif stage == "ESTABLISHED":
                note, col = "established -- the guild's own ground", T.GREEN
            elif stage == "SUSTAINING":
                note, col = f"sustaining: {guild.wilds_claim_sustain_days_left} day(s) left", T.BRASS
            elif stage == "NONE":
                note, col = "unclaimed -- scout it to begin", T.TX_FAINT
            else:
                note, col = f"stage: {stage.title()}", T.TX_FAINT
            return [{"type": "text", "text": note, "color": col}]
        if fn.note:
            return [{"type": "text", "text": fn.note, "color": T.TX_FAINT}]
        return []

    def _inspector_content(self, g, here):
        if self._group_blocked(g):
            n = len(self._pending_event[1].pack)
            blocks = [{"type": "text", "text": "Ambushed on the road!", "color": T.BLOOD},
                      {"type": "text",
                      "text": f"{n} enem{'y' if n == 1 else 'ies'} block the path -- "
                              "there is no escaping this fight.",
                      "color": T.TX_FAINT}]
            if self.autowin_estimator.result and self.autowin_estimator.result.eligible:
                blocks.append({"type": "section", "label": "swift resolution"})
                blocks.append({"type": "button", "key": "autowin_ambush",
                               "label": "AUTO-WIN (100% - NO XP)", "primary": True})
            return blocks
        if g.busy:
            blocks = [{"type": "text", "text": f"Busy: {self._order_status(g)}", "color": T.BRASS}]
            if g.order is not None and g.order.kind == "rest":
                blocks.append({"type": "button", "key": "stop_rest", "label": "STOP RESTING",
                               "danger": True})
            if g.order is not None and g.order.kind == "garrison":
                if here.has("recruit"):
                    blocks.append({"type": "button", "key": "visit_tavern", "label": "ENTER THE TAVERN", "primary": True})
                if here.has("claim"):
                    blocks.append({"type": "button", "key": "visit_claim", "label": "THE WILDS CLAIM", "primary": True})
                blocks.append({"type": "button", "key": "recall_garrison", "label": "RECALL FROM GARRISON", "danger": True})
            return blocks

        blocks = []
        if here.is_battle:
            defense = here.arena and arena.defense_due(self.guild)
            label = ("DEFEND YOUR TITLE" if defense else
                    "BET AT THE ARENA" if here.arena else "ATTACK")
            blocks.append({"type": "button", "key": "arena", "label": label, "primary": True})
            note = ("1v1 for the Champion of the Pit -- no stake, no backup" if defense
                   else "non-lethal · stake money, win the purse" if here.arena
                   else "lethal combat · loot the bodies")
            blocks.append({"type": "text", "text": note, "color": T.BRASS if defense else T.TX_FAINT})
        focus = wildfire.focus_at(self.guild, here.id)
        if focus is not None:
            blocks += self._wildfire_blocks(g, focus)
        trail_cold = here.has("ox_hunt") and missions.pending_ox(self.guild) is None
        front_quiet = here.has("skirmish") and missions.pending_front(self.guild, g) is None
        offered = [f for f in node_functions.offered(here)
                   if f.label and (f.id != "property" or self._has_property_business())
                   and (f.id != "ox_hunt" or not trail_cold)
                   and (f.id != "skirmish" or not front_quiet)
                   and (f.id != "camp_fight" or not focus.cleared)]
        if trail_cold:
            blocks.append({"type": "text", "color": T.TX_FAINT,
                           "text": "The trail is cold. Only the tanner's job brings you back here."})
        elif front_quiet:
            blocks.append({"type": "text", "color": T.TX_FAINT,
                           "text": "The line holds without you. Only the Faith Order's errand "
                                   "puts you in the trench."})
        elif not (here.is_battle or here.has("work") or offered or focus is not None):
            blocks.append({"type": "text", "text": "Nothing happens here. A safe stop.",
                          "color": T.TX_FAINT})
        for fn in offered:
            first = not blocks
            btn = {"type": "button", "key": fn.order_kind,
                   "label": here.shop_label if fn.id == "shop" and here.shop_label else fn.label}
            if fn.id == "ancient_ruins":
                btn["primary"] = True
            if not first:
                btn["gap_before"] = T.S * 2
            blocks.append(btn)
            blocks += self._function_notes(fn)
            if fn.id == "shop" and here.has("work"):
                blocks.append(self._work_line(g, here))

        job_offers = missions.offers_at(self.guild, here.id)
        if job_offers:
            count = len(job_offers)
            label = "New mission on offer" if count == 1 else f"{count} new missions on offer"
            names = ", ".join(t.name for t in job_offers)
            blocks.append({"type": "text", "color": T.BRASS,
                           "text": f"! {label}: {names}"})

        if here.id == "road" and not self.guild.is_node_revealed("ancient_ruins"):
            blocks.append({"type": "button", "key": "scout_ruins", "label": "EXPLORE THE AREA (4 h)",
                          "gap_before": T.S * 2})
            blocks.append({"type": "text", "text": "Scout the surroundings for hidden paths or landmarks (WIS check)",
                          "color": T.TX_FAINT})

        if (here.id == "lumber_yard" and missions.pending_snake(self.guild) is not None
                and not self.guild.is_node_revealed(serpent_nest.NODE)):
            blocks.append({"type": "button", "key": "search_nest",
                           "label": f"SEARCH FOR THE NEST ({serpent_nest.SEARCH_HOURS} h)", "gap_before": T.S * 2})
            blocks.append({"type": "text", "text": "Follow the shed skins to the Snake Dragon's den (WIS check)",
                           "color": T.TX_FAINT})

        if (here.id == "mine" and missions.pending_clutch(self.guild) is not None
                and not self.guild.is_node_revealed(lair.NODE)):
            blocks.append({"type": "button", "key": "search_lair",
                           "label": f"SEARCH THE DEEP GALLERIES ({lair.SEARCH_HOURS} h)", "gap_before": T.S * 2})
            blocks.append({"type": "text", "text": "Follow the warm air past where the miners stopped (WIS check)",
                           "color": T.TX_FAINT})

        if here.id == "country_roads" and not self.guild.is_node_revealed("ox_fields"):
            blocks.append({"type": "button", "key": "scout_fields",
                           "label": f"SEARCH THE LANES ({ox.SCOUT_HOURS} h)", "gap_before": T.S * 2})
            blocks.append({"type": "text", "text": "Look for where the land opens out (WIS check)",
                           "color": T.TX_FAINT})

        return blocks

    @staticmethod
    def _rest_row(key, label, plan, eaters=1):
        """One REST row: what it takes and what it costs (`eaters` mouths), or why it is off."""
        if not plan.available:
            return {"type": "button", "key": key, "label": label, "sub": plan.reason,
                    "tooltip": plan.reason, "enabled": False, "gap_before": 2, "height": 32}
        rations = plan.meals * eaters
        meals = "no meal" if rations == 0 else f"{rations} meal{'s' * (rations != 1)} in all"
        if key != "rest:full":
            return {"type": "button", "key": key, "label": f"{label}  ·  {meals}", "gap_before": 2, "height": 26}
        who = f"{plan.worst[0]} {plan.worst[1]}/{plan.worst[2]}"
        head = "UNTIL RATIONS HIT THE FLOOR" if plan.capped else label
        tooltip = None
        if plan.capped:
            who += f"  ·  {plan.short_days} more day{'s' * (plan.short_days != 1)} of rations to be full"
            tooltip = f"Rations run out before full health ({plan.short_days} more day{'s' * (plan.short_days != 1)} needed)"
        return {"type": "button", "key": key, "gap_before": 2, "height": 32,
                "label": f"{head}  ·  {rest.format_hours(plan.hours)}",
                "sub": f"{meals}  ·  {who}", "tooltip": tooltip}

    def _rest_urgent(self, g):
        """A stop only helps if a hungry member can actually reach a ration --
        their own pack, or a group-mate's shared larder."""
        hungry = [u for u in g.members if u.hunger_level > 0]
        reachable = any(u.rations for u in hungry) or any(
            u.share_food and u.rations for u in g.members)
        return bool(hungry) and reachable

    def _everyone_garrisoned(self):
        groups = [g for g in self.guild.groups if not g.empty]
        return bool(groups) and all(g.order is not None and g.order.kind == "garrison"
                                    for g in groups)

    def _inspector_bottom(self, g):
        """MANAGE GEAR/REST only apply to a band that's actually here to act on
        them; the CTA (`_footer_cta`) is the map's own "what's next" pointer,
        not about `g` specifically, so it's always appended regardless."""
        items = []
        if not (g.busy or self._group_blocked(g)):
            items.append({"type": "button", "key": "manage_group", "label": "MANAGE GEAR & QUESTS", "height": 32})
            if self.on_cook is not None:
                if g.has_campfire(self.guild.clock.seconds):
                    left = g.campfire_hours_left(self.guild.clock.seconds)
                    items.append({"type": "button", "key": "campfire_cook",
                                  "label": f"CAMPFIRE COOKING ({left:g}h)", "primary": True,
                                  "gap_before": 2, "height": 32})
                else:
                    missing = []
                    if not any(u.has_item(economy.FIELD_CAMPFIRE_TOOL) for u in (*g.members, *g.stores)):
                        missing.append("Flint & Steel")
                    if sum(u.unlocked_of(economy.FIELD_CAMPFIRE_LUMBER) for u in g.members) < 1:
                        missing.append("1 Lumber")
                    if sum(u.unlocked_of(economy.FIELD_CAMPFIRE_COAL) for u in g.members) < 1:
                        missing.append("1 Coal")
                    sub = "burns 4h · " + (f"needs {', '.join(missing)}" if missing else "ready to light")
                    items.append({"type": "button", "key": "campfire_cook",
                                  "label": "LIGHT CAMPFIRE & COOK", "enabled": not missing,
                                  "sub": sub, "gap_before": 2, "height": 32})
            items.append({"type": "button", "key": "stance", "gap_before": 2, "height": 32,
                          "label": f"TRAVEL: {g.stance.upper()}",
                          "sub": STANCE_NOTES[g.stance]})
            # nothing may move the clock past an unresolved event
            paused = self._pending_event is not None
            starving = g.rations == 0 and not paused
            items.append({"type": "button", "key": "rest_menu",
                          "label": "REST (OPEN)  ▴" if self._rest_open else "REST  ▾",
                          "gap_before": T.S,
                          "primary": (self._rest_urgent(g) or self._rest_open) and not paused,
                          "danger": starving, "enabled": not paused, "height": 32})
            if self._rest_open and not paused:
                items += [self._rest_row(k, label, plan, len(g.members)) for k, label, plan in self._rest_plans(g)]
        key, label, danger, enabled = self._footer_cta()
        items.append({"type": "button", "key": key, "label": label, "gap_before": T.S,
                     "primary": enabled, "danger": danger, "enabled": enabled, "height": 36})
        return items
