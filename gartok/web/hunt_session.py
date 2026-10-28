"""The hunt in the browser, as pygame's `HuntScreen` and `TrackScreen` play it through `app_hunt`: who minds
the wagon (`watch_screen`), what to look for and for how long, each stretch of hours on the clock
(`MapSession.tick_outside`, so the other bands keep in step), an ambush or the ox's trail fought as a
campaign fight (`campaign_fight._enter`) that comes back here, then the haul banked and the map.

The live hunt is a `hunt.HuntState` held by this session; like pygame, a hunt is never saved."""

from typing import ClassVar

from .. import hunt, missions, ox, progression, wagon_watch, wildfire, world
from ..battle import Battle
from ..map_screen import node_icon
from ..unit import distribute_load
from .campaign_fight import _enter
from .map_session import _portrait, _when
from .session import Session
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
        "talents": lambda s, b: s.talents(b["uid"]),
        "done": lambda s, b: s.done(),
        "leave": lambda s, b: s.leave(),
    }

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
        self.notice = None
        if self.phase is None:
            self._begin()

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
            raise ValueError("not now")

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
            raise ValueError("no such quarry")
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
            raise ValueError("no such shift")
        self.hours = h
        return self.state()

    def distribute(self):
        self._phase("setup", "interlude")
        if len(self.party) < 2:
            raise ValueError("nobody to share the load with")
        distribute_load(self.party)
        self.notice = "Redistributed packs by carrying capacity."
        return self.state()

    def talents(self, uid):
        from .talent_session import TalentSession
        u = next((m for m in self.party if m.uid == uid), None)
        if u is None or not u.pending_picks:
            raise ValueError("no talent to pick")
        self.map.game.open(TalentSession(self.map, u, self.party, self._resume, back_label="Back to the hunt"))
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
            raise ValueError("Too dark to read the ground -- come back at dawn")
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
        s, guild = self.state_, self.guild
        self.notice = None
        if self.tracking:
            elapsed, found = ox.track(s, guild)
            pack = ox.aurochs_pack if found else None
        else:
            lure = hunt.biwolf_lure(guild, s.party)
            s.biwolf = False
            elapsed, found = hunt.hunt_stretch(s, hour=guild.clock.hour_of_day, lure=lure)
            pack = (lambda: hunt.biwolf_pack(guild)) if s.biwolf else (lambda: hunt.wilds_pack(guild=guild))
        self.events, _dead = self.map.tick_outside(elapsed, busy=s.party)
        s.party = [u for u in s.party if u in guild.roster]
        if guild.empty or not s.party or not found:
            self._wrap_up()
        else:
            s.fights += 1
            self.pack = pack()
            self.phase = "ambush"
        return self.state()

    def _wrap_up(self):
        self.phase = "done"
        self.state_.party = [u for u in self.state_.party if u in self.guild.roster]
        if self.result is None:
            self.result = hunt.grant_haul(self.state_)
        self.map._save()

    # ------------------------------------------------------------------ #
    # the fight                                                           #
    # ------------------------------------------------------------------ #
    def fight(self):
        self._phase("ambush")
        s, guild, node = self.state_, self.guild, self.node
        battle = Battle(list(s.party), self.pack, scenario=node.scenario(), daylight=guild.clock.is_daylight,
                        lethal=node.lethal, arena=False, clock_day=guild.clock.day,
                        aggressor="player" if self.tracking else "enemy")
        self.pack = None

        def settle(outcome):
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
            if s.biwolf and missions.fail_if_leather_lost(guild):
                notes.append("The Biwolf's leather is lost -- the tanner's job is failed for good.")
            if self.tracking and outcome.won:
                notes.append("Aurochs, the immortal ox, is dead.")
                if missions.fail_if_hide_lost(guild):
                    notes.append("The hide is lost -- the tanner's job is failed for good.")
            self.events = []
            if outcome.won and s.party and s.hours_left > 0:
                self.phase = "interlude"
                self.map._save()
            else:
                self._wrap_up()
            return self._resume()

        title = "The ox's trail" if self.tracking else "The Biwolf" if s.biwolf else "Ambush in the Wilds"
        return _enter(self.map, self.group, battle, node, "hunt", title, settle, squad=list(s.party), after=after)

    def done(self):
        """Back to the map: the wagon left at the door is rolled for, silently, as `App._end_hunt`; a
        hunt that spent no hours leaves it where it stood."""
        self._phase("done")
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
               "tracking": self.tracking, "title": "The Ox Fields" if self.tracking else "The Wilds",
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
            tally = (f"{s.meat} kg of meat so far." if s.target == "meat" else
                     f"{s.shrooms_found} mushroom(s) and {s.fruit_found} fruit(s) so far.")
            out["interlude"] = {"hours_left": s.hours_left, "line": f"Pack driven off. {s.hours_left} h left in "
                                f"the shift, {tally}"}
        elif self.phase == "ambush":
            out["ambush"] = self._ambush()
        else:
            out["done"] = {"title": "The trail goes cold" if self.tracking else "Back from the Wilds",
                           "lines": list(self.result or []), "hours": s.hours_hunted, "fights": s.fights}
        return out

    def _member(self, u):
        into, span = progression.to_next(progression.WORK_XP_THRESHOLDS, u.work_xp)
        return {"uid": u.uid, "name": u.name, "portrait": _portrait(u), "race": u.race["name"],
                "occupation": u.occupation["name"], "hp": [max(0, u.hp), u.hp_max], "ac": u.ac,
                "load": [round(u.load, 1), u.carry_normal, u.carry_max], "rations": u.rations,
                "work": {"level": u.work_level, "into": into, "span": span},
                "wis": u.mod_wisdom, "picks": len(u.pending_picks)}

    def _yields(self):
        s = self.state_
        if self.tracking:
            best = max((u.mod_wisdom for u in s.party), default=0)
            line = f"Best tracker: Wisdom {best:+d}"
        elif s.target == "meat":
            rate = hunt.party_yield(len(s.party)) * s.yield_mult * s.meat_mult / hunt.HUNT_MEAT_HOURS
            line = f"Meat: {rate:.2f} kg an hour for the party"
            if s.meat_mult < 1:
                line += f" (the wildfires left {s.meat_mult:.0%} of the game)"
        else:
            shroom, fruit = hunt.forage_chances(s)
            line = f"Forage an hour: {shroom:.0%} mushroom, {fruit:.0%} fruit"
        out = {"line": line, "ambush_mult": None}
        if s.ambush_mult != 1.0:
            why = "the Ogre's goblins range the Wilds" if wildfire.hold_standing(self.guild) else "cautious"
            out["ambush_mult"] = f"Ambush chance x{s.ambush_mult:.2f} ({why})"
        return out

    def _setup(self):
        s = self.state_
        crew = hunt.party_yield(len(s.party)) * s.yield_mult * s.meat_mult
        odds = round(hunt.AMBUSH_CHANCE_PER_HOUR * s.ambush_mult * 100)
        return {"targets": [{"id": "meat", "name": "Hunt for meat", "sub": "1 kg for every 2 hours of a crew of three",
                             "on": s.target == "meat"},
                            {"id": "shrooms", "name": "Forage the Wilds", "sub": "Red Mushrooms and fresh fruit",
                             "on": s.target == "shrooms"}],
                "shifts": [{"hours": h, "on": h == self.hours,
                            "sub": f"about {int(h * crew // hunt.HUNT_MEAT_HOURS)} kg of meat" if s.target == "meat"
                            else "mushrooms and fruit"} for h in self.shifts],
                "note": f"{odds}% chance each hour that a pack finds you first: a scaled fight, lethal, "
                        "but the bodies are worth looting.",
                "why": None}

    def _track_setup(self):
        offered = self._offered()
        dc = ox.track_dc(self.guild)
        return {"targets": [],
                "shifts": [{"hours": h, "on": h == self.hours,
                            "sub": f"{h} Wisdom check{'s' * (h != 1)}"} for h in offered],
                "note": f"One check an hour against DC {dc}; a found trail opens the field and makes the next "
                        f"DC {dc + ox.TRACK_DC_STEP}. The tracks can only be read by daylight.",
                "why": None if offered else "Too dark to read the ground -- come back at dawn."}

    def _ambush(self):
        s = self.state_
        if self.tracking:
            return {"title": "The trail is fresh!", "lead": "Aurochs is grazing somewhere on the open fields ahead.",
                    "line": "A lethal chase: he runs from anyone near. Pin him in a canyon and bring him down, "
                            "and every few rounds the herd answers his call.",
                    "foes": []}
        foes = list(self.pack or [])
        n = len(foes)
        lead = ("The smell of your meat drew the Biwolf out of the dark!" if s.biwolf else
                f"A pack of {n} hostile{'s' * (n != 1)} cuts across the trail: a lethal fight, and victory leaves "
                "the field to loot.")
        return {"title": "The Biwolf!" if s.biwolf else "Ambush in the Wilds!", "lead": lead, "line": None,
                "foes": [{"name": u.name, "race": u.race["name"], "portrait": _portrait(u),
                          "weapon": u.equipped_weapon or "Claws and teeth"} for u in foes]}
