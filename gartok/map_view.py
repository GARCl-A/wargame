"""What the campaign map shows of a band and the node it stands on, with no pygame: the
inspector's blocks (a `tone` where a screen picks the colour), the order's status line, the
REST plans, where a pawn stands and each node's glyph. pygame's `MapScreen` and the browser's
`MapSession` both read it; each supplies `guild`, `_group_blocked` and `_pending_event`."""

from . import (
    arena,
    campaign,
    economy,
    gather,
    lair,
    missions,
    node_functions,
    ox,
    rest,
    scenario,
    serpent_nest,
    wildfire,
    world,
)
from .constants import fmt_money
from .group import CAUTIOUS, NORMAL

ADVANCE_HOURS = 24                      # the world-wide wait, once every group is garrisoned

STANCE_NOTES = {NORMAL: "no change to the ambush chance",
                CAUTIOUS: "fewer ambushes only with the Wilds vocation or a Woodland Scout"}

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
            return f"ambushed -- {n} enem{'y' if n == 1 else 'ies'} block the path"
        o = group.order
        if o is None or o.kind == "idle":
            return "idle"
        if o.kind == "travel" and o.task == "supply_run":
            return f"supply run → {world.node(o.dest).name} ({o.remaining + o.owed:.1f} h)"
        if o.kind == "travel":
            dest_name = world.node(o.final_dest).name
            if o.path:                            # more waypoints still to come
                return f"→ {dest_name} via {world.node(o.dest).name} ({o.remaining:g} h)"
            return f"→ {dest_name} ({o.remaining:g} h)"
        if o.kind == "work":
            doing = "gathering" if o.gather else "searching" if o.task in campaign.SEARCHES else "working"
            return f"{doing} ({o.remaining:g} h left)"
        if o.kind == "rest":
            return f"resting ({rest.format_hours(o.remaining)} left)"
        if o.kind == "solo":
            doing = "in the hospital" if o.task == "hospital" else f"crafting {o.recipe}"
            return f"{doing} ({o.remaining:g} h left)"
        return f"heading to {o.kind} ({o.remaining:g} h)"

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
                ("rest:full", "UNTIL FULL", rest.until_full(self.guild, g))]

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
        blocks = [{"type": "text", "text": line, "tone": "bad"}]
        if focus.cleared:
            blocks += [{"type": "section", "label": "the fire", "gap_before": 8},
                       {"type": "button", "key": "wf_put_out", "primary": True, "height": 40,
                        "label": f"PUT OUT THE FIRE ({wildfire.PUT_OUT_HOURS} h)"},
                       {"type": "wrapped_text", "tone": "faint",
                        "text": f"the best mind of the group rolls INT vs DC {wildfire.PUT_OUT_DC} at the end  ·  "
                                "a miss can be tried again"}]
            return blocks
        if focus.hostile:
            blocks.append({"type": "text", "text": "They are coming for you.", "tone": "bad"})
            return blocks
        if wildfire.can_talk(focus):
            attr = wildfire.next_check(focus)
            who = "the Ogre" if focus.great else "the foreman"
            dc = wildfire.talk_dc(self.guild, focus)
            step = "get a hearing" if focus.talk == 0 else "show them how it is done"
            blocks.append({"type": "section", "label": f"talk to {who}", "gap_before": 8})
            blocks.append({"type": "wrapped_text", "tone": "faint",
                           "text": f"{step}: {attr[:3].upper()} vs DC {dc}  ·  a miss and they fight"})
            blocks.append({"type": "button", "key": "wf_talk", "height": 36, "gap_before": 2,
                           "label": f"TALK TO {who.upper()}"})
        return blocks

    def _work_line(self, g, here):
        """A work node's one line on the map: what a day's shift pays the group and whether the
        guild may gather here; the shifts themselves are the hub's WORK and GATHERING tabs."""
        day = sum(economy.work_pay(here.id, 16, economy.work_level(u, here.id)) for u in g.members)
        parts = [f"a 16 h shift pays the group {fmt_money(day)}"]
        if gather.can_gather(here.id):
            parts.append("gathering licence held" if self.guild.has_licence(here.id) else "no gathering licence")
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
                     "text": f"strongbox: {guild.bank.load:g} / {guild.bank.capacity} kg"}]
        if fn.id == "property":
            if guild.house.repossession_due:
                note, col = "the Bankers want the house back, or the tax paid", "bad"
            elif guild.house.squatting:
                note, col = "squatting -- the guard can still come to clear it out", "warn"
            elif guild.house.owned:
                note = (f"house: {guild.house.stash.load:g} / "
                        f"{economy.CITY_PROPERTY_CAPACITY} kg")
                col = "faint"
            else:
                note, col = f"owes the Bankers {fmt_money(guild.bankers_debt)}", "bad"
            return [{"type": "text", "text": note, "tone": col}]
        if fn.id == "claim":
            stage = guild.wilds_claim_stage
            if stage == "ESTABLISHED" and guild.wilds_claim_owner == "seized":
                note, col = "SEIZED -- send a group to retake it", "bad"
            elif stage == "ESTABLISHED":
                note, col = "established -- the guild's own ground", "good"
            elif stage == "SUSTAINING":
                note, col = f"sustaining: {guild.wilds_claim_sustain_days_left} day(s) left", "warn"
            elif stage == "NONE":
                note, col = "unclaimed -- scout it to begin", "faint"
            else:
                note, col = f"stage: {stage.title()}", "faint"
            return [{"type": "text", "text": note, "tone": col}]
        if fn.note:
            return [{"type": "text", "text": fn.note, "tone": "faint"}]
        return []

    def _inspector_content(self, g, here):
        if self._group_blocked(g):
            n = len(self._pending_event[1].pack)
            blocks = [{"type": "text", "text": "Ambushed on the road!", "tone": "bad"},
                      {"type": "text",
                      "text": f"{n} enem{'y' if n == 1 else 'ies'} block the path -- "
                              "there is no escaping this fight.",
                      "tone": "faint"}]
            return blocks
        if g.busy:
            blocks = [{"type": "text", "text": f"Busy: {self._order_status(g)}", "tone": "warn"}]
            if g.order is not None and g.order.kind == "rest":
                blocks.append({"type": "button", "key": "stop_rest", "label": "STOP RESTING",
                               "danger": True})
            if g.order is not None and g.order.kind == "travel" and g.order.path and not g.order.task:
                blocks.append({"type": "button", "key": "cancel_trip",
                               "label": f"STOP AT {world.node(g.order.dest).name.upper()}",
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
                           "text": "The trail is cold. Only the tanner's job brings you back here."})
        elif ruins_empty:
            blocks.append({"type": "text", "tone": "faint",
                           "text": "The ruins lie silent. Nothing is left down there."})
        elif front_quiet:
            blocks.append({"type": "text", "tone": "faint",
                           "text": "The line holds without you. Only the Faith Order's errand "
                                   "puts you in the trench."})
        elif not (here.is_battle or here.has("work") or offered or focus is not None):
            blocks.append({"type": "text", "text": "Nothing happens here. A safe stop.",
                          "tone": "faint"})
        for fn in offered:
            first = not blocks
            btn = {"type": "button", "key": fn.order_kind,
                   "label": here.shop_label if fn.id == "shop" and here.shop_label else fn.label}
            if fn.id == "ancient_ruins":
                btn["primary"] = True
            if not first:
                btn["gap_before"] = 16
            blocks.append(btn)
            blocks += self._function_notes(fn)
            if fn.id == "shop" and here.has("work"):
                blocks.append(self._work_line(g, here))

        job_offers = missions.offers_at(self.guild, here.id)
        if job_offers:
            count = len(job_offers)
            label = "New mission on offer" if count == 1 else f"{count} new missions on offer"
            names = ", ".join(t.name for t in job_offers)
            blocks.append({"type": "text", "tone": "warn",
                           "text": f"! {label}: {names}"})

        if here.id == "road" and not self.guild.is_node_revealed("ancient_ruins"):
            blocks.append({"type": "button", "key": "scout_ruins", "label": f"EXPLORE THE AREA ({campaign.SCOUT_RUINS_HOURS} h)",
                          "gap_before": 16})
            blocks.append({"type": "text", "text": "Scout the surroundings for hidden paths or landmarks (WIS check)",
                          "tone": "faint"})

        if (here.id == "lumber_yard" and missions.pending_snake(self.guild) is not None
                and not self.guild.is_node_revealed(serpent_nest.NODE)):
            blocks.append({"type": "button", "key": "search_nest",
                           "label": f"SEARCH FOR THE NEST ({serpent_nest.SEARCH_HOURS} h)", "gap_before": 16})
            blocks.append({"type": "text", "text": "Follow the shed skins to the Snake Dragon's den (WIS check)",
                           "tone": "faint"})

        if (here.id == "mine" and missions.pending_clutch(self.guild) is not None
                and not self.guild.is_node_revealed(lair.NODE)):
            blocks.append({"type": "button", "key": "search_lair",
                           "label": f"SEARCH THE DEEP GALLERIES ({lair.SEARCH_HOURS} h)", "gap_before": 16})
            blocks.append({"type": "text", "text": "Follow the warm air past where the miners stopped (WIS check)",
                           "tone": "faint"})

        if here.id == "country_roads" and not self.guild.is_node_revealed("ox_fields"):
            blocks.append({"type": "button", "key": "scout_fields",
                           "label": f"SEARCH THE LANES ({ox.SCOUT_HOURS} h)", "gap_before": 16})
            blocks.append({"type": "text", "text": "Look for where the land opens out (WIS check)",
                           "tone": "faint"})

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

