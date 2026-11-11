"""What the campaign map shows of a band and the node it stands on, with no pygame: the
inspector's blocks (a `tone` where a screen picks the colour), the order's status line, the
REST plans, where a pawn stands and each node's glyph. pygame's `MapScreen` and the browser's
`MapSession` both read it; each supplies `guild`, `_group_blocked` and `_pending_event`."""

from . import (
    arena,
    campaign,
    cult_site,
    economy,
    gather,
    i18n,
    lair,
    missions,
    node_functions,
    ox,
    rest,
    scenario,
    serpent_nest,
    stints,
    wildfire,
    world,
)
from .constants import fmt_money
from .group import CAUTIOUS, NORMAL

ADVANCE_HOURS = 24                      # the world-wide wait, once every group is garrisoned

STANCE_NOTES = {NORMAL: "map_view.stance_note.normal",
                CAUTIOUS: "map_view.stance_note.cautious"}

NODE_ICON = {
    "city": ("map", "city"), "lumber_yard": ("action", "stick-splitting"), "carpenter": ("action", "crafting"), "mine": ("action", "mining"),
    "arena": ("body", "sword-tie"), "market": ("action", "trade"), "smith": ("map", "smith"),
    "tanner": ("map", "hide"), "apothecary": ("map", "flask"), "tavern": ("action", "drinking"),
    "prison": ("body", "imprisoned"), "road": ("map", "signpost"), "wilds": ("action", "wolf-howl"),
    "ledger_hold": ("map", "fort"), "wilds_territory": ("map", "claim"), "library": ("gui", "open-book"),
    "farm": ("map", "wheat"), "ancient_ruins": ("map", "ruins"), "country_roads": ("action", "journey"),
    "ox_fields": ("map", "ox"), "blood_sanctuary": ("map", "blood"),
    "serpents_nest": ("head", "snake-bite"), "dragon_lair": ("head", "dragon-head"),
    "nature_grove": ("map", "leaf"), "faith_cathedral": ("map", "cathedral"),
    "frontier_outpost": ("body", "spiked-wall"), "battlefield": ("action", "trench-assault"),
    "cult_site": ("symbol", "pentagram-rose"),
}
# The ethereal nodes (`wildfire.py`): a focus is numbered as it starts, so it goes by its prefix.
ETHEREAL_ICON = {wildfire.GREAT_ID: ("head", "ogre"), wildfire.FORTRESS_ID: ("head", "ogre")}   # never on the map together
FOCUS_ICON = ("body", "fire-silhouette")


def node_icon(node_id):
    if node_id.startswith("wildfire_focus_"):
        return FOCUS_ICON
    return NODE_ICON.get(node_id) or ETHEREAL_ICON.get(node_id)


def position(g):
    """Where the group's pawn stands: its node, or `(from, to, share)` part-way along the leg it
    walks (or stopped on, for a caravan held by its ambush). The share counts the hours a stopped
    leg still owes, so the pawn never gives an ambush away before it springs."""
    o = g.order if g.order is not None and g.order.kind == "travel" else g.pending
    if o is None or not o.dest or o.dest == g.node or o.eta <= 0:
        return g.node
    return (g.node, o.dest, max(0.0, min(1.0, (o.eta - o.remaining - o.owed) / o.eta)))


class MapView:
    def _order_status(self, group):
        """One-line status for a group's ROSTER card / INSPECTOR header."""
        if self._group_blocked(group):
            n = len(self._pending_event[1].pack)
            return i18n.plural("map_view.ambushed_enem_block_path", n)
        o = group.order
        if o is None or o.kind == "idle":
            routine = group.routine
            return i18n.t("map_view.routine_stopped", paused=routine.paused) if routine is not None and routine.paused else i18n.t("map_view.idle")
        if o.kind == "travel" and o.task == "supply_run":
            return i18n.t("map_view.supply_run_h", name=world.node(o.dest).name, value=o.remaining + o.owed)
        if o.kind == "travel":
            dest_name = world.node(o.final_dest).name
            if o.path:                            # more waypoints still to come
                return i18n.t("map_view.via_h", dest_name=dest_name, name=world.node(o.dest).name, remaining=o.remaining)
            return f"→ {dest_name} ({o.remaining:g} h)"
        if stints.is_stint(o):
            return f"{stints.doing(o)} ({o.remaining:g} h left)"
        if o.kind == "work":
            doing = "gathering" if o.gather else "searching" if o.task in campaign.SEARCHES else "working"
            return f"{doing} ({o.remaining:g} h left)"
        if o.kind == "rest":
            return i18n.t("map_view.resting_left", format_hours=rest.format_hours(o.remaining))
        if o.kind == "hunting":
            return f"hunting ({o.remaining:g} h left)"
        if o.kind == "solo":
            doing = i18n.t("map_view.in_hospital") if o.task == "hospital" else i18n.t("map_view.crafting", recipe=o.recipe)
            return f"{doing} ({o.remaining:g} h left)"
        return i18n.t("map_view.heading_to_h", kind=o.kind, remaining=o.remaining)

    def _mates_for(self, g):
        """Other idle bands standing right there -- MERGE candidates, offered
        from `g`'s own roster card once it's expanded (see roster_panel's
        SPLIT UI), never from a band that can't act on it either way."""
        return [(o.gid, o.display_name) for o in self.guild.groups
               if o is not g and o.node == g.node and not o.busy and not self._group_blocked(o)]

    def _rest_plans(self, g):
        """`[(key, label, plan)]` for the REST rows of group `g`."""
        return [("rest:1", "1 h", rest.fixed(self.guild, 1)),
                ("rest:8", "8 h", rest.fixed(self.guild, 8)),
                ("rest:full", i18n.t("map_view.until_full"), rest.until_full(self.guild, g))]

    def _wildfire_blocks(self, g, focus):
        """The inspector's rows at a wildfire focus: how long it has, the talk chain (one button a
        member, their modifier on it), and putting the fire out once the crew is beaten."""
        state = self.guild.wildfire
        day = self.guild.clock.day
        if focus.great:
            left = state.start_day + wildfire.DAYS - day
            line = i18n.t("map_view.fortress_stands_in_day_s", left=left)
        else:
            left = focus.spawn_day + wildfire.BURN_DAYS - day
            line = i18n.t("map_view.burns_through_in_day_s", left=left)
        blocks = [{"type": "text", "text": line, "tone": "bad"}]
        if focus.cleared:
            blocks += [{"type": "section", "label": i18n.t("map_view.fire")},
                       {"type": "button", "key": "wf_put_out", "primary": True,
                        "label": i18n.t("map_view.put_out_fire_h", put_out_hours=wildfire.PUT_OUT_HOURS)},
                       {"type": "wrapped_text", "tone": "faint",
                        "text": i18n.t("map_view.best_mind_of_group_rolls", put_out_dc=wildfire.PUT_OUT_DC)}]
            return blocks
        if focus.hostile:
            blocks.append({"type": "text", "text": i18n.t("map_view.they_are_coming_for_you"), "tone": "bad"})
            return blocks
        if wildfire.can_talk(focus):
            attr = wildfire.next_check(focus)
            who = i18n.t("map_view.ogre") if focus.great else i18n.t("map_view.foreman")
            dc = wildfire.talk_dc(self.guild, focus)
            step = "get a hearing" if focus.talk == 0 else i18n.t("map_view.show_them_how_it_is")
            blocks.append({"type": "section", "label": i18n.t("map_view.talk_to", who=who)})
            blocks.append({"type": "wrapped_text", "tone": "faint",
                           "text": i18n.t("map_view.vs_dc_miss_and_they", step=step, upper=attr[:3].upper(), dc=dc)})
            blocks.append({"type": "button", "key": "wf_talk",
                           "label": i18n.t("map_view.talk_to_2", upper=who.upper())})
        return blocks

    def _work_line(self, g, here):
        """A work node's one line on the map: what a day's shift pays the group and whether the
        guild may gather here; the shifts themselves are the hub's WORK and GATHERING tabs."""
        day = sum(economy.work_pay(here.id, 16, economy.work_level(u, here.id)) for u in g.members)
        parts = [i18n.t("map_view.h_shift_pays_group", fmt_money=fmt_money(day))]
        if gather.can_gather(here.id):
            parts.append(i18n.t("map_view.gathering_licence_held") if self.guild.has_licence(here.id) else i18n.t("map_view.no_gathering_licence"))
        return {"type": "text", "tone": "faint", "text": "  ·  ".join(parts)}

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
            return [{"type": "text", "tone": "faint",
                     "text": i18n.t("map_view.strongbox_kg", load=guild.bank.load, capacity=guild.bank.capacity)}]
        if fn.id == "property":
            if guild.house.repossession_due:
                note, col = i18n.t("map_view.bankers_want_house_back_or"), "bad"
            elif guild.house.squatting:
                note, col = i18n.t("map_view.squatting_guard_can_still_come"), "warn"
            elif guild.house.owned:
                note = (i18n.t("map_view.house_kg", load=guild.house.stash.load, city_property_capacity=economy.CITY_PROPERTY_CAPACITY))
                col = "faint"
            else:
                note, col = i18n.t("map_view.owes_bankers", fmt_money=fmt_money(guild.bankers_debt)), "bad"
            return [{"type": "text", "text": note, "tone": col}]
        if fn.id == "claim":
            stage = guild.wilds_claim_stage
            if stage == "ESTABLISHED" and guild.wilds_claim_owner == "seized":
                note, col = i18n.t("map_view.seized_send_group_to_retake"), "bad"
            elif stage == "ESTABLISHED":
                note, col = i18n.t("map_view.established_guild_s_own_ground"), "good"
            elif stage == "SUSTAINING":
                note, col = i18n.t("map_view.sustaining_day_s_left", wilds_claim_sustain_days_left=guild.wilds_claim_sustain_days_left), "warn"
            elif stage == "NONE":
                note, col = i18n.t("map_view.unclaimed_scout_it_to_begin"), "faint"
            else:
                note, col = i18n.t("map_view.stage", title=stage.title()), "faint"
            return [{"type": "text", "text": note, "tone": col}]
        if fn.note:
            return [{"type": "text", "text": fn.note, "tone": "faint"}]
        return []

    def _inspector_content(self, g, here):
        if self._group_blocked(g):
            n = len(self._pending_event[1].pack)
            blocks = [{"type": "text", "text": i18n.t("map_view.ambushed_on_road"), "tone": "bad"},
                      {"type": "text",
                      "text": i18n.plural("map_view.enem_block_path_there_is", n),
                      "tone": "faint"}]
            return blocks
        if g.busy:
            blocks = [{"type": "text", "text": i18n.t("map_view.busy", order_status=self._order_status(g)), "tone": "warn"}]
            if g.order is not None and g.order.kind == "rest":
                blocks.append({"type": "button", "key": "stop_rest", "label": i18n.t("map_view.stop_resting"),
                               "danger": True})
            if g.order is not None and g.order.kind == "travel" and g.order.path and not g.order.task:
                blocks.append({"type": "button", "key": "cancel_trip",
                               "label": i18n.t("map_view.stop_at", upper=world.node(g.order.dest).name.upper()),
                               "danger": True})
            if g.order is not None and g.order.kind == "garrison":
                if here.has("recruit"):
                    blocks.append({"type": "button", "key": "visit_tavern", "label": i18n.t("map_view.enter_tavern"), "primary": True})
                if here.has("claim"):
                    blocks.append({"type": "button", "key": "visit_claim", "label": i18n.t("map_view.wilds_claim"), "primary": True})
                blocks.append({"type": "button", "key": "recall_garrison", "label": i18n.t("map_view.recall_from_garrison"), "danger": True})
            return blocks

        blocks = []
        routine = g.routine
        if routine is not None and routine.paused:
            blocks += [{"type": "text", "text": i18n.t("map_view.routine_stopped_2", paused=routine.paused), "tone": "warn"},
                       {"type": "button", "key": "continue_routine", "label": i18n.t("map_view.continue_routine"), "primary": True}]
        if here.is_battle:
            defense = here.arena and arena.defense_due(self.guild)
            label = (i18n.t("map_view.defend_your_title") if defense else
                    i18n.t("map_view.bet_at_arena") if here.arena else "ATTACK")
            blocks.append({"type": "button", "key": "arena", "label": label, "primary": True})
            note = (i18n.t("map_view.v_for_champion_of_pit") if defense
                   else i18n.t("map_view.non_lethal_stake_money_win") if here.arena
                   else i18n.t("map_view.lethal_combat_loot_bodies"))
            blocks.append({"type": "text", "text": note, "tone": "warn" if defense else "faint"})
        focus = wildfire.focus_at(self.guild, here.id)
        if focus is not None:
            blocks += self._wildfire_blocks(g, focus)
        trail_cold = here.has("ox_hunt") and missions.pending_ox(self.guild) is None
        front_quiet = here.has("skirmish") and missions.pending_front(self.guild, g) is None
        ruins_empty = here.has("ancient_ruins") and scenario.ruins_empty(self.guild)
        offered = [f for f in node_functions.offered(here)
                   if f.label and (f.id != "property" or self._has_property_business())
                   and (f.id != "ox_hunt" or not trail_cold)
                   and (f.id != "skirmish" or not front_quiet)
                   and (f.id != "camp_fight" or not focus.cleared)
                   and (f.id != "ancient_ruins" or not ruins_empty)]
        if trail_cold:
            blocks.append({"type": "text", "tone": "faint",
                           "text": i18n.t("map_view.trail_is_cold_only_tanner")})
        elif ruins_empty:
            blocks.append({"type": "text", "tone": "faint",
                           "text": i18n.t("map_view.ruins_lie_silent_nothing_is")})
        elif front_quiet:
            blocks.append({"type": "text", "tone": "faint",
                           "text": i18n.t("map_view.line_holds_without_you_only")})
        elif not (here.is_battle or here.has("work") or offered or focus is not None):
            blocks.append({"type": "text", "text": i18n.t("map_view.nothing_happens_here_safe_stop"),
                          "tone": "faint"})
        for fn in offered:
            btn = {"type": "button", "key": fn.order_kind,
                   "label": here.shop_label if fn.id == "shop" and here.shop_label else fn.label}
            if fn.id == "ancient_ruins":
                btn["primary"] = True
            blocks.append(btn)
            blocks += self._function_notes(fn)
            if fn.id == "shop" and here.has("work"):
                blocks.append(self._work_line(g, here))

        job_offers = missions.offers_at(self.guild, here.id)
        if job_offers:
            count = len(job_offers)
            label = i18n.t("map_view.new_mission_on_offer") if count == 1 else i18n.t("map_view.new_missions_on_offer", count=count)
            names = ", ".join(t.name for t in job_offers)
            blocks.append({"type": "text", "tone": "warn",
                           "text": f"! {label}: {names}"})

        if here.id == "road" and not self.guild.is_node_revealed("ancient_ruins"):
            blocks.append({"type": "button", "key": "scout_ruins", "label": i18n.t("map_view.explore_area_h", scout_ruins_hours=campaign.SCOUT_RUINS_HOURS)})
            blocks.append({"type": "text", "text": i18n.t("map_view.scout_surroundings_for_hidden_paths"),
                          "tone": "faint"})

        if (here.id == "lumber_yard" and missions.pending_snake(self.guild) is not None
                and not self.guild.is_node_revealed(serpent_nest.NODE)):
            blocks.append({"type": "button", "key": "search_nest",
                           "label": i18n.t("map_view.search_for_nest_h", search_hours=serpent_nest.SEARCH_HOURS)})
            blocks.append({"type": "text", "text": i18n.t("map_view.follow_shed_skins_to_snake"),
                           "tone": "faint"})

        if (here.id == "mine" and missions.pending_clutch(self.guild) is not None
                and not self.guild.is_node_revealed(lair.NODE)):
            blocks.append({"type": "button", "key": "search_lair",
                           "label": i18n.t("map_view.search_deep_galleries_h", search_hours=lair.SEARCH_HOURS)})
            blocks.append({"type": "text", "text": i18n.t("map_view.follow_warm_air_past_where"),
                           "tone": "faint"})

        if here.id == "country_roads" and not self.guild.is_node_revealed("ox_fields"):
            blocks.append({"type": "button", "key": "scout_fields",
                           "label": i18n.t("map_view.search_lanes_h", scout_hours=ox.SCOUT_HOURS)})
            blocks.append({"type": "text", "text": i18n.t("map_view.look_for_where_land_opens"),
                           "tone": "faint"})

        if (here.id == "country_roads" and cult_site.quest_active(self.guild)
                and not self.guild.is_node_revealed(cult_site.NODE)):
            blocks.append({"type": "button", "key": "search_cult",
                           "label": i18n.t("map_view.search_cult_h", search_hours=cult_site.SEARCH_HOURS)})
            blocks.append({"type": "text", "text": i18n.t("map_view.search_cult_hint"), "tone": "faint"})

        return blocks

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

