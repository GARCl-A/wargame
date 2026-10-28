"""A member's talent trees in the browser: the four tracks, one tree at a time with every talent's
state, the talent in hand with what it moves on the sheet, and the pick. The layout (the map, the
branch) is the client's and reads only `requires`; a pick is `Unit.choose_talent`, as pygame's
`LevelScreen` takes it, and the save is written on each one.

Opened from a member's sheet (`GuildSession.talents`) and a level-up (`ReportSession.talents`);
`back` goes to whichever sent it."""

import copy
from typing import ClassVar

from .. import progression, talents
from .map_session import _portrait
from .session import Session

LABELS = {"combat": "Combat", "work": "Work", "racial": "Racial", "magic": "Magic"}
XP = {"combat": ("combat_xp", progression.COMBAT_XP_THRESHOLDS),
      "work": ("work_xp", progression.WORK_XP_THRESHOLDS),
      "magic": ("magic_xp", progression.MAGIC_XP_THRESHOLDS)}
ATTRS = (("STR", "strength"), ("DEX", "dexterity"), ("CON", "constitution"),
         ("INT", "intelligence"), ("WIS", "wisdom"), ("CHA", "charisma"))
SHEET = (*ATTRS, ("Max HP", "hp_max"), ("AC", "ac"), ("Mental Def.", "mental_defense"),
         ("Speed", "speed"), ("Load limit", "carry_max"))


def tree(unit, track):
    return talents.racial_tree(unit.race["name"]) if track == "racial" else talents.TREE[track]


def node_state(unit, track, t):
    """taken / open (a pick can take it now) / waiting (it could, with a pick) / granted (a school's
    root, held only through initiation) / locked (what it needs is not held)."""
    if unit.holds_talent(track, t.id):
        return "taken"
    if t.granted:
        return "granted"
    if unit.offerable(track, t):
        return "open" if unit.picks_available(track) > 0 else "waiting"
    return "locked"


def _sheet(u):
    return {k: round(getattr(u, a), 1) for k, a in SHEET}


class TalentSession(Session):
    screen = "talents"
    GET: ClassVar[dict] = {"state": lambda s, q: s.state()}
    POST: ClassVar[dict] = {
        "look": lambda s, b: s.look(b.get("uid"), b.get("track"), b.get("id")),
        "take": lambda s, b: s.take(b["track"], b["id"]),
        "back": lambda s, b: s.back(),
    }

    def __init__(self, map_session, unit, band, back, *, back_label="Back", chain=None):
        self.map = map_session
        self.guild = map_session.guild
        self.band = list(band) or [unit]
        self.unit = unit
        self.back_to = back
        self.back_label = back_label
        self.chain = chain                       # the report's chain of screens, when a level-up sent it
        self.track = self.sel = None
        self._land()

    def _land(self):
        """On the first track with a pick waiting (else combat), the talent in hand its first open one."""
        u = self.unit
        self.track = next(iter(u.pending_picks), "combat")
        self.sel = self._first(self.track)

    def _first(self, track):
        nodes = tree(self.unit, track)
        return next((t.id for t in nodes if node_state(self.unit, track, t) == "open"),
                    nodes[0].id if nodes else None)

    # ------------------------------------------------------------------ #
    # what the person does                                                #
    # ------------------------------------------------------------------ #
    def look(self, uid=None, track=None, tid=None):
        """Another member (on their first pick), another track, or a talent taken in hand."""
        if uid is not None and uid != self.unit.uid:
            u = next((m for m in self.band if m.uid == uid), None)
            if u is None:
                raise ValueError("no such member in the band")
            self.unit = u
            self._land()
        if track is not None:
            if track not in talents.TRACKS:
                raise ValueError(f"no such track: {track}")
            if track != self.track:
                self.track, self.sel = track, self._first(track)
        if tid is not None:
            if tid not in {t.id for t in tree(self.unit, self.track)}:
                raise ValueError("that talent is not on this tree")
            self.sel = tid
        return self.state()

    def take(self, track, tid):
        u, t = self.unit, talents.get(tid)
        if t is None or t.track != track or t not in tree(u, track):
            raise ValueError("that talent is not on this tree")
        state = node_state(u, track, t)
        if state != "open":
            raise ValueError(self._why(u, track, t, state))
        if not u.choose_talent(track, tid):
            raise ValueError(f"{u.name} cannot take {t.name}")
        self.map._save()
        self.track, self.sel = track, tid
        return self.state()

    def back(self):
        return self.back_to()

    # ------------------------------------------------------------------ #
    # the screen                                                          #
    # ------------------------------------------------------------------ #
    def state(self):
        u = self.unit
        nodes = tree(u, self.track)
        hand = next((t for t in nodes if t.id == self.sel), None)
        return {
            "guild": self.guild.name, "day": self.guild.clock.day, "back": self.back_label, "chain": self.chain,
            "unit": {"uid": u.uid, "name": u.name, "race": u.race["name"], "occupation": u.occupation["name"],
                     "portrait": _portrait(u), "hp": max(0, u.hp), "hp_max": u.hp_max,
                     "racial_level": u.racial_level, "schools": list(u.magic_sources),
                     "attrs": [{"k": k, "v": getattr(u, a)} for k, a in ATTRS]},
            "tracks": [self._track(u, tr) for tr in talents.TRACKS],
            "track": self.track,
            "nodes": [self._node(u, self.track, t) for t in nodes],
            "hand": self._hand(u, self.track, hand) if hand else None,
            "can_take": [{"track": tr, "id": t.id, "name": t.name, "tier": t.tier}
                         for tr in talents.TRACKS for t in tree(u, tr) if node_state(u, tr, t) == "open"],
            "band": [{"uid": m.uid, "name": m.name, "portrait": _portrait(m),
                      "picks": sum(max(0, m.picks_available(tr)) for tr in m.pending_picks)} for m in self.band],
        }

    def _track(self, u, track):
        nodes = tree(u, track)
        out = {"track": track, "label": LABELS[track], "level": u.track_level[track],
               "picks": max(0, u.picks_available(track)) if track in u.pending_picks else 0,
               "held": sum(u.holds_talent(track, t.id) for t in nodes), "total": len(nodes),
               "into": None, "span": None, "next_racial": None}
        if track in XP:
            attr, thresholds = XP[track]
            out["into"], out["span"] = progression.to_next(thresholds, getattr(u, attr))
        else:
            out["next_racial"] = (progression.racial_picks(u.racial_level) + 1) * progression.RACIAL_PICK_EVERY
        return out

    @staticmethod
    def _node(u, track, t):
        return {"id": t.id, "name": t.name, "tier": t.tier, "requires": t.requires, "icon": t.icon or None,
                "effect": t.effect, "state": node_state(u, track, t)}

    def _why(self, u, track, t, state):
        if state == "taken":
            return f"{u.name} holds {t.name} already"
        if state == "granted":
            return f"{t.name} comes with initiation into {(t.school or 'a school').capitalize()}"
        if state == "locked":
            return f"{t.name} needs {talents.get(t.requires).name} first"
        if track == "magic" and not u.magic_sources:
            return f"{u.name} has no school yet: a school opens with initiation at its sanctuary"
        if track == "racial":
            nxt = (progression.racial_picks(u.racial_level) + 1) * progression.RACIAL_PICK_EVERY
            return f"the next racial pick comes at racial level {nxt}"
        return f"{u.name} has no {LABELS[track].lower()} pick to spend; one comes with the next level"

    def _hand(self, u, track, t):
        state = node_state(u, track, t)
        chain = [t]
        while chain[0].requires:
            chain.insert(0, talents.get(chain[0].requires))
        why = self._why(u, track, t, state)
        out = {"id": t.id, "status": "Ready to take" if state == "open" else
               "Held" if state == "taken" else why[0].upper() + why[1:],
               "branch": [{"id": c.id, "name": c.name, "icon": c.icon or None, "state": node_state(u, track, c)}
                          for c in chain],
               "opens": [{"id": c.id, "name": c.name, "icon": c.icon or None, "state": node_state(u, track, c)}
                         for c in tree(u, track) if c.requires == t.id],
               "delta": None}
        if state == "open":
            out["delta"] = self._delta(u, track, t)
        return out

    @staticmethod
    def _delta(u, track, t):
        """What the pick moves on the sheet: `[label, before, after]` for each number it changes. Read off a
        copy with the talent added, not through `choose_talent` (the play log would record a pick)."""
        twin = copy.deepcopy(u)
        twin.talents[track].append(t.id)
        twin._apply_attributes()
        twin._derive_combat()
        before, after = _sheet(u), _sheet(twin)
        return [[k, before[k], after[k]] for k, _ in SHEET if before[k] != after[k]]
