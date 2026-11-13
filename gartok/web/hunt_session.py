"""The hunt in the browser, as pygame's `HuntScreen` and `TrackScreen` play it through `app_hunt`: who minds
the wagon (`watch_screen`), what to look for and for how long, each stretch of hours, an ambush or the ox's
trail fought as a campaign fight (`campaign_fight._enter`) that comes back here, then the haul banked and the map.

A stretch is rolled as it starts and runs as a `hunting` order (`MapSession.spend`), so every other band's
order runs with it and the map takes over when another band needs the person; the map keeps this session in
`MapSession.hunts` and opens it again (`arrive`) when the stretch is up. The live hunt is a `hunt.HuntState`
held by this session; while a stretch is out it also rides in the `hunting` order (`Order.state`), so a save
taken then loads with the stretch still running, and the map rebuilds this session from it (`restore`). On the
screen itself (setup, an interlude, an ambush) the hunt lives only here: a load finds the party back."""

from typing import ClassVar

from .. import (
    encounters,
    hunt,
    i18n,
    missions,
    orders,
    ox,
    progression,
    wagon_watch,
    wildfire,
    world,
)
from ..battle import Battle
from ..map_view import node_icon
from ..unit import distribute_load
from .campaign_fight import _enter
from .map_session import _portrait, _when
from .session import Session
from .swift import Look
from .watch_session import toggle, watch_state


def open_hunt(map_session, group, target="meat"):
    session = HuntSession(map_session, group, target)
    map_session.game.open(session)
    return {"screen": session.screen}


class HuntSession(Session):
    screen = "hunt"
    GET: ClassVar[dict] = {"state": lambda s, q: s.state()}
    POST: ClassVar[dict] = {
        "watch": lambda s, b: s.toggle_watch(b["uid"]),
        "go": lambda s, b: s.go(),
        "target": lambda s, b: s.set_target(b["target"]),
        "hours": lambda s, b: s.set_hours(int(b["hours"])),
        "distribute": lambda s, b: s.distribute(),
        "start": lambda s, b: s.start(),
        "hunt_on": lambda s, b: s.hunt_on(),
        "head_back": lambda s, b: s.head_back(),
        "fight": lambda s, b: s.fight(),
        "swift_win": lambda s, b: s.fight(swift=True),
        "talents": lambda s, b: s.talents(b["uid"]),
        "done": lambda s, b: s.done(),
        "leave": lambda s, b: s.leave(),
    }

    def tutorial_key(self):
        return "watch" if self.phase == "watch" else "ox_hunt" if self.tracking else "hunt"

    def __init__(self, map_session, group, target="meat"):
        self.map = map_session
        self.guild = map_session.guild
        self.group = group
        self.node = world.node(group.node)
        self.target = target
        self.goes = list(group.members)
        self.guarded = True
        self.state_ = None                 # the `hunt.HuntState`, once the party heads out
        self.phase = "watch" if wagon_watch.needs_watch(group) else None
        self.hours = self.shifts[1]
        self.events = []                   # what the clock did during the last stretch
        self.result = None                 # `hunt.grant_haul`'s lines, once banked
        self.pack = None                   # the ambush waiting to be fought
        self.found = None                  # the stretch out on the clock: "wilds", "biwolf", "ox" or None
        self.rolled = []                   # the Wilds pack the stretch ended on, rolled with it (`Order.pack`)
        self.look = Look()                 # its clean-stomp estimate
        self.notice = None
        if self.phase is None:
            self._begin()

    @classmethod
    def restore(cls, map_session, group, order=None):
        """The hunt whose stretch `group`'s `hunting` order (or the `order` that came due) carries, out on
        the clock again after a load."""
        order = order or group.order
        d = order.state
        session = cls(map_session, group, d["hunt"]["target"])
        session.state_ = hunt.from_dict(d["hunt"], group.members, session.node)
        session.goes = list(session.state_.party)
        session.guarded, session.found, session.phase = d["guarded"], d["found"], "out"
        session.rolled = list(order.pack)
        return session

    @property
    def tracking(self):
        return self.target == "ox"

    @property
    def shifts(self):
        return ox.TRACK_SHIFT_HOURS if self.tracking else hunt.HUNT_SHIFT_HOURS

    @property
    def party(self):
        return self.state_.party if self.state_ is not None else self.goes

    def _phase(self, *allowed):
        if self.phase not in allowed:
            raise ValueError(i18n.t("hunt_session.not_now"))

    # ------------------------------------------------------------------ #
    # who minds the wagon                                                 #
    # ------------------------------------------------------------------ #
    def toggle_watch(self, uid):
        self._phase("watch")
        self.goes = toggle(self.group, self.goes, uid)
        return self.state()

    def go(self):
        self._phase("watch")
        self.guarded = len(self.goes) < len(self.group.members)
        self._begin()
        return self.state()

    def _begin(self):
        guards = [u for u in self.group.members if u not in self.goes]
        self.state_ = hunt.begin(self.guild, self.goes, self.node, self.group.stance,
                                 target=self.target, guards=guards)
        self.phase = "setup"
        offered = self._offered()
        if offered and self.hours not in offered:
            self.hours = max(offered)

    # ------------------------------------------------------------------ #
    # what to look for, for how long                                      #
    # ------------------------------------------------------------------ #
    def set_target(self, target):
        self._phase("setup")
        if self.tracking or target not in ("meat", "shrooms"):
            raise ValueError(i18n.t("hunt_session.no_such_quarry"))
        self.target = self.state_.target = target
        return self.state()

    def _offered(self):
        if not self.tracking:
            return list(self.shifts)
        daylight = ox.daylight_hours(self.guild.clock.hour_of_day)
        return [h for h in self.shifts if h <= daylight]

    def set_hours(self, h):
        self._phase("setup")
        if h not in self._offered():
            raise ValueError(i18n.t("hunt_session.no_such_shift"))
        self.hours = h
        return self.state()

    def distribute(self):
        self._phase("setup", "interlude")
        if len(self.party) < 2:
            raise ValueError(i18n.t("hunt_session.nobody_to_share_load_with"))
        distribute_load(self.party)
        self.notice = i18n.t("hunt_session.redistributed_packs_by_carrying_capacity")
        return self.state()

    def talents(self, uid):
        from .talent_session import TalentSession
        u = next((m for m in self.party if m.uid == uid), None)
        if u is None or not u.pending_picks:
            raise ValueError(i18n.t("hunt_session.no_talent_to_pick"))
        self.map.game.open(TalentSession(self.map, u, self.party, self._resume, back_label=i18n.t("hunt_session.back_to_hunt")))
        return {"screen": TalentSession.screen}

    def _resume(self):
        self.map.game.open(self)
        return {"screen": self.screen, **self.state()}

    # ------------------------------------------------------------------ #
    # the hours                                                           #
    # ------------------------------------------------------------------ #
    def start(self):
        self._phase("setup")
        offered = self._offered()
        if not offered:
            raise ValueError(i18n.t("hunt_session.too_dark_to_read_ground"))
        self.state_.hours_left = min(self.hours, max(offered)) if self.tracking else self.hours
        return self._stretch()

    def hunt_on(self):
        self._phase("interlude")
        return self._stretch()

    def head_back(self):
        self._phase("interlude")
        self._wrap_up()
        return self.state()

    def _stretch(self):
        """Roll the stretch and send the party out on it: a `hunting` order the map's clock runs."""
        s, guild = self.state_, self.guild
        self.notice = None
        if self.tracking:
            elapsed, found = ox.track(s, guild)
            kind = "ox"
        else:
            lure = hunt.biwolf_lure(guild, s.party)
            s.biwolf = False
            elapsed, found = hunt.hunt_stretch(s, hour=guild.clock.hour_of_day, lure=lure,
                                               roll_pack=lambda: hunt.wilds_pack(guild=guild))
            kind = "biwolf" if s.biwolf else "wilds"
        self.found = kind if found else None
        self.rolled = list(s.pack)
        self.phase = "out"
        self.map.hunts[self.group.gid] = self
        self.group.due_hunt = None
        order = orders.Order("hunting", eta=elapsed, remaining=elapsed, crew=tuple(u.uid for u in s.party),
                             pack=tuple(self.rolled),
                             state={"hunt": hunt.to_dict(s), "found": self.found, "guarded": self.guarded})
        return self.map.spend(self.group, order)[1]

    def _pack(self, found):
        if found == "ox":
            return ox.aurochs_pack()
        if found == "biwolf":
            return hunt.biwolf_pack(self.guild)
        return hunt.wilds_pack(guild=self.guild)

    def arrive(self):
        """The stretch is up (the map's clock ran it): an ambush springs, or the hunt is over."""
        s, guild, m = self.state_, self.guild, self.map
        self.events, m.notices = m.notices, []
        s.party = [u for u in s.party if u in guild.roster]
        found, self.found = self.found, None
        rolled, self.rolled = self.rolled, []
        if guild.empty or not s.party or found is None:
            self._wrap_up()
        else:
            s.fights += 1
            self.pack = rolled or self._pack(found)
            self.phase = "ambush"
            self.look.clear()
            if not self.tracking:
                self.look.of(s.fights, s.party, self.pack, self.node.scenario, guild.clock.is_daylight, self.node.lethal)
        return self._resume()

    def _wrap_up(self):
        self.phase = "done"
        self.group.due_hunt = None
        self.state_.party = [u for u in self.state_.party if u in self.guild.roster]
        if self.result is None:
            self.result = hunt.grant_haul(self.state_)
        self.map._save()

    # ------------------------------------------------------------------ #
    # the fight                                                           #
    # ------------------------------------------------------------------ #
    def fight(self, swift=False):
        self._phase("ambush")
        s, guild, node = self.state_, self.guild, self.node
        result = self.look.result if swift else None
        if swift and result is None:
            raise ValueError(i18n.t("hunt_session.this_fight_is_not_clean"))
        battle = Battle(list(s.party), self.pack, scenario=node.scenario(), daylight=guild.clock.is_daylight,
                        lethal=node.lethal, arena=False, clock_day=guild.clock.day,
                        aggressor="player" if self.tracking else "enemy")
        self.pack = None

        def settle(outcome):
            self.group.due_hunt = None         # kept through the "before a fight" autosave, so a load rolls it again
            if not outcome.won and s.fights > 0:
                s.fights -= 1
            s.party = [u for u in outcome.survivors if u in guild.roster]
            if self.tracking:
                s.hours_left = 0               # one chase per trail found
                if outcome.won:
                    missions.slay_ox(guild)
            return []

        def after(outcome):
            notes = self.map.notices
            if s.biwolf:
                escaped = hunt.biwolf_escaped(battle)
                if missions.settle_biwolf(guild, escaped):
                    notes.append(i18n.t("hunt_session.biwolf_s_leather_is_lost"))
                elif escaped:
                    notes.append(i18n.t("hunt_session.biwolf_got_away_he_will"))
            if self.tracking and outcome.won:
                notes.append(i18n.t("hunt_session.aurochs_immortal_ox_is_dead"))
                if missions.fail_if_hide_lost(guild):
                    notes.append(i18n.t("hunt_session.hide_is_lost_tanner_s"))
            self.events = []
            if outcome.won and s.party and s.hours_left > 0:
                self.phase = "interlude"
                self.map._save()
            else:
                self._wrap_up()
            return self._resume()

        title = i18n.t("hunt_session.ox_s_trail") if self.tracking else i18n.t("hunt_session.biwolf") if s.biwolf else i18n.t("hunt_session.ambush_in_wilds")
        nature = ox.TRACK_NATURE if self.tracking else hunt.BIWOLF_NATURE if s.biwolf else hunt.PACK_NATURE
        return _enter(self.map, self.group, battle, node, "hunt", title, settle, squad=list(s.party), after=after,
                      swift=result, nature=nature)

    def done(self):
        """Back to the map: the wagon left at the door is rolled for, silently, as `App._end_hunt`; a
        hunt that spent no hours leaves it where it stood."""
        self._phase("done")
        self.map.hunts.pop(self.group.gid, None)
        if self.state_.hours_hunted:
            wagon_watch.leave_outside(self.group, self.node, self.guarded)
        from .dialogue_session import _to_map
        if self.guild.empty:
            self.map.wiped = True
            return self.map.back()
        return _to_map(self.map, self.group)

    def leave(self):
        self._phase("watch", "setup")
        from .dialogue_session import _to_map
        return _to_map(self.map, self.group)

    # ------------------------------------------------------------------ #
    # the screen                                                          #
    # ------------------------------------------------------------------ #
    def state(self):
        g, n = self.group, self.node
        day, at = _when(self.guild, 0)
        out = {"place": n.name, "band": g.display_name, "day": day, "at": at, "phase": self.phase,
               "tracking": self.tracking, "title": i18n.t("hunt_session.ox_fields") if self.tracking else i18n.t("hunt_session.wilds"),
               "icon": "/".join(node_icon(n.id) or ("action", "wolf-howl")),
               "notice": self.notice, "events": list(self.events)}
        if self.phase == "watch":
            return {**out, "watch": watch_state(self.group, self.goes)}
        s = self.state_
        out["members"] = [self._member(u) for u in s.party]
        out["guards"] = [u.name for u in s.guards]
        out["yields"] = self._yields()
        out["can_distribute"] = len(s.party) > 1 and self.phase in ("setup", "interlude")
        if self.phase == "setup":
            out["setup"] = self._track_setup() if self.tracking else self._setup()
        elif self.phase == "interlude":
            tally = (i18n.t("hunt_session.kg_of_meat_so_far", meat=s.meat) if s.target == "meat" else
                     i18n.t("hunt_session.mushroom_s_and_fruit_s", shrooms_found=s.shrooms_found, fruit_found=s.fruit_found))
            out["interlude"] = {"hours_left": s.hours_left, "line": i18n.t("hunt_session.pack_driven_off_h_left", hours_left=s.hours_left, tally=tally)}
        elif self.phase == "ambush":
            out["ambush"] = self._ambush()
        else:
            out["done"] = {"title": i18n.t("hunt_session.trail_goes_cold") if self.tracking else i18n.t("hunt_session.back_from_wilds"),
                           "lines": list(self.result or []), "hours": s.hours_hunted, "fights": s.fights}
        return out

    def _member(self, u):
        into, span = progression.to_next(progression.WORK_XP_THRESHOLDS, u.work_xp)
        return {"uid": u.uid, "name": u.name, "portrait": _portrait(u), "race": u.race_label,
                "hp": [max(0, u.hp), u.hp_max], "ac": u.ac,
                "load": [round(u.load, 1), u.carry_normal, u.carry_max], "rations": u.rations,
                "work": {"level": u.work_level, "into": into, "span": span},
                "wis": u.mod_wisdom, "picks": len(u.pending_picks)}

    def _yields(self):
        s = self.state_
        if self.tracking:
            best = max((u.mod_wisdom for u in s.party), default=0)
            line = i18n.t("hunt_session.best_tracker_wisdom", best=best)
        elif s.target == "meat":
            rate = hunt.party_yield(len(s.party)) * s.yield_mult * s.meat_mult / hunt.HUNT_MEAT_HOURS
            line = i18n.t("hunt_session.meat_kg_hour_for_party", rate=rate)
            if s.meat_mult < 1:
                line += i18n.t("hunt_session.wildfires_left_of_game", meat_mult=s.meat_mult)
        else:
            shroom, fruit = hunt.forage_chances(s)
            line = i18n.t("hunt_session.forage_hour_mushroom_fruit", shroom=shroom, fruit=fruit)
        out = {"line": line, "ambush_mult": None}
        if s.ambush_mult != 1.0 or s.night_mult != 1.0:
            why = i18n.t("hunt_session.ogre_s_goblins_range_wilds") if wildfire.hold_standing(self.guild) else i18n.t("hunt_session.cautious")
            out["ambush_mult"] = i18n.t("hunt_session.ambush_chance_x", ambush_mult=s.ambush_mult, why=why)
            if s.night_mult != 1.0:
                out["ambush_mult"] += i18n.t("hunt_session.x_after_dark", night_mult=s.night_mult)
        return out

    def _setup(self):
        s = self.state_
        crew = hunt.party_yield(len(s.party)) * s.yield_mult * s.meat_mult
        per_hour = encounters.ambush_chance_per_hour("hunt", s.ambush_mult)
        odds = round(per_hour * 100, 1)
        night = round(per_hour * s.night_mult * 100, 1)
        return {"targets": [{"id": "meat", "name": i18n.t("hunt_session.hunt_for_meat"), "sub": i18n.t("hunt_session.kg_for_every_hours_of"),
                             "on": s.target == "meat"},
                            {"id": "shrooms", "name": i18n.t("hunt_session.forage_wilds"), "sub": i18n.t("hunt_session.red_mushrooms_and_fresh_fruit"),
                             "on": s.target == "shrooms"}],
                "shifts": [{"hours": h, "on": h == self.hours,
                            "sub": i18n.t("hunt_session.about_kg_of_meat", int=int(h * crew // hunt.HUNT_MEAT_HOURS)) if s.target == "meat"
                            else i18n.t("hunt_session.mushrooms_and_fruit")} for h in self.shifts],
                "note": i18n.t("hunt_session.chance_each_hour_dark" if night != odds else "hunt_session.chance_each_hour", odds=odds, night=night),
                "why": None}

    def _track_setup(self):
        offered = self._offered()
        dc = ox.track_dc(self.guild)
        return {"targets": [],
                "shifts": [{"hours": h, "on": h == self.hours,
                            "sub": i18n.plural("hunt_session.wisdom_check", h)} for h in offered],
                "note": i18n.t("hunt_session.one_check_hour_against_dc", dc=dc, next_dc=dc + ox.TRACK_DC_STEP),
                "why": None if offered else i18n.t("hunt_session.too_dark_to_read_ground_2")}

    def _ambush(self):
        s = self.state_
        if self.tracking:
            return {"title": i18n.t("hunt_session.trail_is_fresh"), "lead": i18n.t("hunt_session.aurochs_is_grazing_somewhere_on"),
                    "line": i18n.t("hunt_session.lethal_chase_he_runs_from"),
                    "foes": []}
        foes = list(self.pack or [])
        n = len(foes)
        lead = (i18n.t("hunt_session.smell_of_your_meat_drew") if s.biwolf else
                i18n.plural("hunt_session.pack_of_hostile_cuts_across", n))
        return {"title": i18n.t("hunt_session.biwolf_2") if s.biwolf else i18n.t("hunt_session.ambush_in_wilds_2"), "lead": lead, "line": None,
                "swift": self.look.state(),
                "foes": [{"name": i18n.name("race", u.name), "race": u.race_label, "portrait": _portrait(u),
                          "weapon": u.equipped_weapon or i18n.t("hunt_session.claws_and_teeth")} for u in foes]}
