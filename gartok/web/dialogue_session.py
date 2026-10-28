"""The talk before a fight (`dialogue.py`) in the browser: the foe's leader as a bestiary page, the
answers as cards with their odds, the band choosing who speaks, and the roll on a slip. It holds
pygame's own `DialogueScreen` headless for who speaks, the verbs and the result.

Three talks open it: a forced fight's (the guard, the ambushes: `forced_talk`), the Wildfire's
(`wildfire_talk`) and an arena boss's lines (`boss_talk`, for the bout once it is in the browser)."""

import re
from typing import ClassVar

from .. import dialogue, encounters, forced, orders, recorder, wildfire, world
from ..constants import fmt_money
from ..dialogue_screen import _BUTTON_LABEL, DialogueScreen
from .map_session import _portrait, _when
from .session import Session

VERB_ICONS = {"persuade": "action/convince", "teach": "action/teacher", "bluff": "action/juggler",
              "intimidate": "action/shouting", "bribe": "item/two-coins", "surrender": "action/kneeling",
              "leave": "action/run", "attack": "item/broadsword"}
SEALS = {"guard": "action/arrest", "boss": "hat/crown", "wildfire": "item/torch"}
_ROLL = re.compile(r"\s*\(d20\((\d+)\) ([+-]\d+)(?:\([A-Z]+\))? = (-?\d+) vs DC (\d+)\)")


def _roll(text):
    """`(the roll as numbers or None, the text without it)`, read off a result's line."""
    m = _ROLL.search(text)
    if m is None:
        return None, text
    nat, mod, total, dc = (int(x) for x in m.groups())
    return {"nat": nat, "mod": mod, "total": total, "dc": dc}, text[:m.start()] + text[m.end():]


def _opening(op):
    """How the fight opens, one row per thing the talk changed."""
    if op is None:
        return []
    rows = []
    if op.surprised == "player":
        rows.append(("action/run", "Caught off guard", "Your band loses its first turn: they act before anyone of yours."))
    if op.surprised == "enemy":
        rows.append(("item/broadsword", "They are caught off guard", "The foes lose their first turn."))
    if op.demoralized == "enemy":
        rows.append(("action/shouting", "They come on shaken", "The foes start the fight demoralized."))
    for team, bonus in op.initiative.items():
        if bonus:
            who = "the foes'" if team == "enemy" else "your band's"
            rows.append(("item/broadsword", "They get the jump" if team == "enemy" else "You get the jump",
                         f"{bonus:+d} to {who} initiative."))
    return [{"icon": i, "title": t, "line": s} for i, t, s in rows] or [
        {"icon": "item/broadsword", "title": "An even start", "line": "Initiative as it falls."}]


class DialogueSession(Session):
    screen = "talk"
    GET: ClassVar[dict] = {"state": lambda s, q: s.state()}
    POST: ClassVar[dict] = {
        "speaker": lambda s, b: s.pick(b["uid"]),
        "choose": lambda s, b: s.choose(b["verb"]),
        "go_on": lambda s, b: s.go_on(),
    }

    def __init__(self, map_session, group, encounter, done, decided=None, on_decided=None, caught=()):
        self.map = map_session
        self.guild = map_session.guild
        self.group = group
        self.done = done                  # result -> the answer, once the person reads how it ended
        self.caught = set(caught)
        self.talk = DialogueScreen(None, self.guild, group, encounter, on_done=done,
                                   on_decided=on_decided, decided=decided)
        self.played = None                # the answer whose roll is on the table, as it read before the roll

    @property
    def enc(self):
        return self.talk.encounter

    # ------------------------------------------------------------------ #
    def pick(self, uid):
        if self.talk.result is not None:
            raise ValueError("the die is cast")
        if not self.enc.offered():
            raise ValueError("nobody answers here")
        who = next((u for u in self.talk.members if u.uid == uid), None)
        if who is None:
            raise ValueError("no such member")
        self.talk.speaker = who
        return self.state()

    def choose(self, verb):
        if self.talk.result is not None:
            raise ValueError("the die is cast")
        if self.talk.speaker is None:
            raise ValueError("nobody to speak")
        who = self.talk.speaker
        opt = self.enc.option(verb, who, self.talk.members)
        self.talk.choose(verb)
        self.played = {"verb": verb, "label": opt.label, "icon": VERB_ICONS[verb], "speaker": who.name,
                       "note": opt.note.partition(" · ")[0], "check": opt.check}
        return self.state()

    def go_on(self):
        result = self.talk.result
        if result is None:
            raise ValueError("nothing has been said yet")
        if result.over:
            return self.done(result)
        self.talk.go_on()
        self.played = None
        return self.state()

    # ------------------------------------------------------------------ #
    def state(self):
        enc, g = self.enc, self.group
        here = world.node(g.node) if world.exists(g.node) else None
        day, at = _when(self.guild, 0)
        members = self.talk.members
        purse = sum(u.money for u in members)
        out = {
            "kind": enc.kind, "title": enc.title, "seal": SEALS.get(enc.kind, "item/broadsword"),
            "place": here.name if here else "", "band": g.display_name, "day": day, "at": at,
            "line": enc.line, "leader": self._leader(), "foes": self._foes(),
            "purse": purse, "purse_text": fmt_money(purse),
            "members": [self._member(u) for u in members],
            "speaker": self.talk.speaker.uid if self.talk.speaker is not None else None,
            "options": [], "result": None, "lines": None,
            "edge": getattr(enc, "edge", 0),
            "wanted": [{"name": u.name, "crime": u.crime} for u in members if u.uid in self.caught],
        }
        if enc.kind == "boss":
            out["lines"] = [{"name": u.name, "caption": cap, "portrait": _portrait(u),
                             "at": "said" if i < enc.step else "now" if i == enc.step else "later"}
                            for i, (u, cap, _) in enumerate(enc.lines)]
        elif self.talk.result is None and self.talk.speaker is not None:
            out["options"] = [self._option(o) for o in enc.options(self.talk.speaker, members)]
        if self.talk.result is not None:
            out["result"] = self._result(self.talk.result)
        return out

    def _leader(self):
        lead = self.enc.leader
        if lead is None:
            return None
        return {"uid": lead.uid, "name": lead.name, "caption": self.enc.caption(lead), "portrait": _portrait(lead),
                "languages": list(lead.languages), "alignment": lead.alignment or ""}

    def _foes(self):
        lead = self.enc.leader
        return [{"uid": u.uid, "name": u.name, "race": u.race["name"], "portrait": _portrait(u),
                 "speaks": u is lead} for u in self.enc.foes]

    def _member(self, u):
        lead = self.enc.leader
        tongue = set(lead.languages) if lead is not None and self.enc.language_gate else set()
        return {"uid": u.uid, "name": u.name, "race": u.race["name"], "occupation": u.occupation["name"],
                "portrait": _portrait(u), "cha": u.mod_charisma, "int": u.mod_intelligence,
                "languages": [{"name": lang, "shared": lang in tongue} for lang in u.languages],
                "understood": self.enc.shared(u), "hp": [u.hp, u.hp_max], "money": u.money,
                "crime": u.crime if u.uid in self.caught else None}

    def _option(self, o):
        passing, _, missing = o.note.partition(" · ")
        need = None if o.odds is None else max(1, min(21, round(21 - o.odds * 20)))
        return {"verb": o.verb, "label": o.label, "icon": VERB_ICONS[o.verb], "pass": passing, "miss": missing,
                "check": o.check, "odds": o.odds, "need": need, "block": o.block}

    def _result(self, r):
        roll, text = _roll(r.text)
        won = roll["total"] >= roll["dc"] if roll else r.kind != "fight"
        return {"kind": r.kind, "text": text, "full": r.text, "roll": roll, "played": self.played, "won": won,
                "button": _BUTTON_LABEL[r.kind], "paid": r.paid,
                "opening": _opening(r.opening) if r.kind == "fight" and self.enc.kind != "boss" else []}


# --------------------------------------------------------------------------- #
# the talks that open it                                                      #
# --------------------------------------------------------------------------- #
def _to_map(map_session, group):
    map_session.game.open(map_session)
    map_session.focus = group.gid
    return map_session._after_order()


def forced_talk(map_session, group):
    """The talk before `group`'s forced fight, as `App._open_dialogue` plays it, or None when the
    pack has nobody who speaks. A talk already rolled (a reload) opens on its result."""
    guild, order = map_session.guild, group.pending
    enc = forced.encounter(guild, group, order)
    if enc is None:
        return None
    decided = dialogue.Result.from_dict(order.parley) if order.parley else None

    def decide(result):
        order.parley = result.to_dict()
        recorder.emit("talk", kind=order.kind, result=result.kind, paid=result.paid)
        map_session._save()

    def done(result):
        if result.kind == "fight":
            return map_session._away(group, order, fight=True)
        if result.kind == "surrender":
            map_session.notices += forced.resolve_guard_prison(guild, group, order)
        elif result.kind == "leave":
            events, _pause = forced.resolve_guard_flee(guild, group, order)   # a re-catch is the band's pending
            map_session.notices += events
        else:
            map_session.notices += [result.text, *forced.settle_talk(guild, group, order)]
        return _to_map(map_session, group)

    return DialogueSession(map_session, group, enc, done, decided=decided, on_decided=decide,
                           caught=order.caught if order.kind == "guard" else ())


def wildfire_talk(map_session, group):
    """TALK at a Wildfire focus, as `MapScreen._wildfire_talk` plays it: a miss or ATTACK sends the
    band at the camp (or the fortress), the last lesson puts the fire out."""
    guild = map_session.guild
    focus = wildfire.focus_at(guild, group.node)
    if focus is None or not wildfire.can_talk(focus):
        raise ValueError("nobody here will talk")
    great = focus.great
    enc = dialogue.WildfireTalk(guild, focus, wildfire.talker(focus, encounters.squad_level(group.members)))

    def done(result):
        map_session.notices.append(result.text)
        if result.kind == "fight":
            map_session.game.open(map_session)
            return map_session._enter(group, orders.interactive("ogre_fight" if great else "camp_fight", hours=0))
        return _to_map(map_session, group)

    return DialogueSession(map_session, group, enc, done)


def boss_talk(map_session, group, talk, then):
    """An arena boss's lines before the guild's first bout against them (`arena.boss_talk`); `then()`
    opens the bout once the last line is read."""
    return DialogueSession(map_session, group, talk, lambda _result: then(), decided=talk.current())
