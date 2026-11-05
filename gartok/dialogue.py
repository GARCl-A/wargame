"""Dialogue before initiative: when the guild meets a foe that can talk, words come first.

An `Encounter` is one meeting: the foes, their leader (the one who talks), the verbs on offer
and what each does. The player picks who speaks and a verb (`options` lists them, a closed one
with the reason); `choose` rolls it and returns a `Result`:

- `peace`: no fight (they let you by, take the coin, run, or learn);
- `fight`: the battle starts, with an `Opening` (who is caught off guard, who starts shaken,
  who gets the jump on initiative) the caller hands to `Battle.open_with`;
- `leave` / `surrender`: the encounter's own way out (the guard's RUN and ARREST);
- `next`: the dialogue goes on (the Wildfire's second step).

A check is d20 + the speaker's modifier against a DC; a natural 1 or 20 is just its number.
Every verb that talks needs a language the speaker shares with the leader (`recruit`'s gate);
coin and steel need none. A pack with nobody who speaks (beasts, the dead) opens no dialogue.

Who caught whom is the caller's business (`forced.py`, `wildfire.py`): an encounter only says
what the words did. `ai_choice` is the squad's side when nobody plays it.
"""

import random
from dataclasses import dataclass, field

from . import economy, i18n, recruit

BASE_DC = 15                  # an ordinary speaker (CHA +1) talks an even pack down 35% of the time
BRIBE_PER_FOE = 3             # copper a foe asks per (its level + 1)
GUARD_BRIBE_PER_CRIME = 10    # copper a patrol asks per point of crime it caught
ALIGN_SHIFT = 3               # Persuade: a good leader is this much easier, an evil one harder
OUTMATCH_CAP = 4              # an ambush: at most this much easier (or harder) for the odds
ROUT_MARGIN = 5               # Intimidate passed by this much: they run instead of fighting shaken
INITIATIVE_EDGE = 5           # a failed Intimidate: the foes' head start on initiative
BLUFF_STEP = 2                # a Challenge: each bluff already told raises the next one's DC


@dataclass(frozen=True)
class Verb:
    id: str
    attr: str | None          # the speaker's attribute it rolls; None = no check
    spoken: bool              # needs a language shared with the leader

    @property
    def label(self):
        return i18n.t(f"dialogue.verb.{self.id}")


PARLEY_VERBS = ("persuade", "bluff", "intimidate")   # the Human's Parley talent adds to these

VERBS = {v.id: v for v in (
    Verb("persuade", "charisma", True),
    Verb("teach", "intelligence", True),
    Verb("bluff", "charisma", True),
    Verb("intimidate", "charisma", True),
    Verb("bribe", None, False),
    Verb("surrender", None, False),
    Verb("leave", None, False),
    Verb("attack", None, False),
)}


@dataclass
class Opening:
    """How a fight that came out of a dialogue starts."""
    surprised: str | None = None      # the team that loses its first turn
    demoralized: str | None = None    # the team that starts Demoralized
    initiative: dict = field(default_factory=dict)   # team -> initiative bonus

    def to_dict(self):
        return {"surprised": self.surprised, "demoralized": self.demoralized,
                "initiative": dict(self.initiative)}

    @classmethod
    def from_dict(cls, d):
        return cls(d.get("surprised"), d.get("demoralized"), dict(d.get("initiative") or {}))


@dataclass
class Result:
    kind: str                         # "peace" | "fight" | "leave" | "surrender" | "next"
    text: str
    opening: Opening | None = None
    paid: int = 0

    @property
    def over(self):
        return self.kind != "next"

    def to_dict(self):
        return {"kind": self.kind, "text": self.text, "paid": self.paid,
                "opening": self.opening.to_dict() if self.opening else None}

    @classmethod
    def from_dict(cls, d):
        opening = Opening.from_dict(d["opening"]) if d.get("opening") else None
        return cls(d["kind"], d["text"], opening, d.get("paid", 0))


@dataclass
class Option:
    verb: str
    label: str
    note: str                         # what passing does
    check: str = ""                   # "CHA +2 vs DC 12", "$18", ""
    odds: float | None = None         # chance to pass, for a check
    block: str = ""                   # why it cannot be taken now

    @property
    def open(self):
        return not self.block


def _note(kind, verb, **params):
    key = f"dialogue.note.{kind}.{verb}"
    return i18n.t(key, **params) if i18n.has(key) else ""


def leader_of(foes):
    """The foe who talks for the rest: the most experienced one with a language, or None."""
    speakers = [u for u in foes if u.languages]
    return max(speakers, key=lambda u: (u.racial_level, u.mean_level)) if speakers else None


def first_speaker(encounter, members):
    """Who speaks for the squad unless the player picks another: the best Charisma among those
    the foes understand."""
    understood = [u for u in members if encounter.shared(u)] or members
    return max(understood, key=lambda u: u.mod_charisma) if understood else None


def can_talk(foes):
    return leader_of(foes) is not None


def odds(mod, dc):
    return max(0.0, min(1.0, (21 - (dc - mod)) / 20))


def roll(mod, dc, rng=random):
    """-> (passed, margin, line)."""
    nat = rng.randint(1, 20)
    total = nat + mod
    return total >= dc, total - dc, i18n.t("dialogue.roll", nat=nat, mod=mod, total=total, dc=dc)


def _purse(members):
    return sum(u.money for u in members)


class Encounter:
    """A meeting with foes who talk. Subclasses say which verbs they offer and what each does."""
    kind = ""
    verbs = ()
    language_gate = True
    worded = frozenset()          # verbs that need a shared language here although they need none elsewhere

    def __init__(self, foes, title, line):
        self.foes = list(foes)
        self.leader = leader_of(self.foes)
        self.title = title
        self.line = line
        self.result = None            # the last `Result`, once one ends it

    # -- what the speaker can try ---------------------------------------- #
    def shared(self, speaker):
        if not self.language_gate:
            return True
        if self.leader is None:
            return False
        return bool(recruit.shared_languages(speaker, self.leader))

    def mod(self, verb, speaker):
        parley = speaker.talent_bonus("parley") if verb in PARLEY_VERBS else 0
        if verb == "intimidate" and speaker.has_talent("intimidating_presence"):
            return max(speaker.mod_charisma, speaker.mod_strength) + parley
        return getattr(speaker, f"mod_{VERBS[verb].attr}") + parley

    def dc(self, verb):
        return BASE_DC + (self.leader.mod_wisdom if self.leader is not None else 0)

    def price(self):
        return sum(BRIBE_PER_FOE * (u.mean_level + 1) for u in self.foes)

    def offered(self):
        return self.verbs

    def caption(self, unit):
        return unit.race_label

    def advance(self):
        """The next step once the player has read a `next` result; None goes back to the verbs."""
        return None

    def note(self, verb):
        return ""

    def refusal(self, verb):
        """Why this encounter will not hear `verb` at all, or ""."""
        return ""

    def options(self, speaker, members):
        out = []
        for verb in self.offered():
            v = VERBS[verb]
            opt = Option(verb, v.label, self.note(verb))
            if v.attr is not None:
                mod, dc = self.mod(verb, speaker), self.dc(verb)
                opt.check = i18n.t("dialogue.check", attr=v.attr[:3].upper(), mod=mod, dc=dc)
                opt.odds = odds(mod, dc)
            if verb == "bribe":
                opt.check = f"${self.price()}"
                if _purse(members) < self.price():
                    opt.block = i18n.t("dialogue.block.coin")
            opt.block = self.refusal(verb) or opt.block
            if (v.spoken or verb in self.worded) and not self.shared(speaker):
                opt.block = (i18n.t("dialogue.block.language", languages=", ".join(self.leader.languages))
                             if self.leader is not None else i18n.t("dialogue.block.nobody"))
            out.append(opt)
        return out

    def option(self, verb, speaker, members):
        return next((o for o in self.options(speaker, members) if o.verb == verb), None)

    # -- trying it ------------------------------------------------------- #
    def choose(self, verb, speaker, members, rng=random):
        opt = self.option(verb, speaker, members)
        if opt is None or not opt.open:
            raise ValueError(i18n.t("dialogue.error.not_open", verb=VERBS[verb].label,
                                    why=opt.block if opt else i18n.t("dialogue.error.not_offered")))
        if verb == "bribe":
            price = self.price()
            economy.charge_richest_first(members, price)
            result = Result("peace", i18n.t("dialogue.bribe_paid", who=speaker.name, price=price, outcome=self._bribed()),
                            paid=price)
        elif VERBS[verb].attr is None:
            result = self._plain(verb, speaker)
        else:
            passed, margin, line = roll(self.mod(verb, speaker), self.dc(verb), rng)
            result = self._checked(verb, speaker, passed, margin, line)
        if result.over:
            self.result = result
        return result

    def _bribed(self):
        return i18n.t("dialogue.bribed.ambush")

    def _plain(self, verb, speaker):
        return Result("fight", i18n.t("dialogue.steel"), Opening())

    def _checked(self, verb, speaker, passed, margin, line):
        raise NotImplementedError


class Ambush(Encounter):
    """A pack that found the group first: on the road, at work, on a supply run."""
    kind = "ambush"
    verbs = ("persuade", "bluff", "intimidate", "bribe", "attack")

    def __init__(self, foes, title=None, line=None):
        n = len(foes)
        super().__init__(foes, title or i18n.t("dialogue.title.ambush"),
                         line or i18n.t("dialogue.line.ambush", n=n))
        self.edge = 0

    def set_odds(self, squad):
        """How much the squad's look moves every check: its hit points against the pack's. A pack
        that outweighs the squad has no reason to listen; one that is outweighed is glad of a way out."""
        mine = sum(u.hp_max for u in squad)
        theirs = sum(u.hp_max for u in self.foes) or 1
        ratio = mine / theirs
        self.edge = max(-OUTMATCH_CAP, min(OUTMATCH_CAP, round((ratio - 1) * OUTMATCH_CAP)))

    def dc(self, verb):
        dc = super().dc(verb)
        if verb == "persuade" and self.leader is not None:
            from .data import alignment_axes
            dc -= ALIGN_SHIFT * alignment_axes(self.leader.alignment)[1]
        return dc - self.edge

    def note(self, verb):
        return _note("ambush", verb)

    def _checked(self, verb, speaker, passed, margin, line):
        who = self.leader.name if self.leader is not None else i18n.t("dialogue.they")
        if verb == "persuade":
            if passed:
                return Result("peace", i18n.t("dialogue.ambush.persuade_win", speaker=speaker.name, who=who, line=line))
            return Result("fight", i18n.t("dialogue.ambush.persuade_miss", who=who, line=line), Opening())
        if verb == "bluff":
            if passed:
                return Result("peace", i18n.t("dialogue.ambush.bluff_win", speaker=speaker.name, line=line))
            return Result("fight", i18n.t("dialogue.ambush.bluff_miss", who=who, line=line),
                          Opening(surprised="player"))
        if passed and margin >= ROUT_MARGIN:
            return Result("peace", i18n.t("dialogue.ambush.rout", speaker=speaker.name, who=who, line=line))
        if passed:
            return Result("fight", i18n.t("dialogue.ambush.shaken", speaker=speaker.name, line=line),
                          Opening(demoralized="enemy"))
        return Result("fight", i18n.t("dialogue.ambush.laughs", who=who, line=line),
                      Opening(initiative={"enemy": INITIATIVE_EDGE}))


class Patrol(Encounter):
    """The City guard has caught members with a rap sheet (`justice.catch`)."""
    kind = "guard"

    def __init__(self, foes, caught, can_run):
        names = ", ".join(u.name for u in caught)
        super().__init__(foes, i18n.t("dialogue.title.guard"), i18n.t("dialogue.line.guard", names=names))
        self.caught = list(caught)
        self.can_run = can_run

    def offered(self):
        return ("surrender", "bluff", "bribe", "attack") + (("leave",) if self.can_run else ())

    def price(self):
        return GUARD_BRIBE_PER_CRIME * max(1, sum(u.crime for u in self.caught))

    def note(self, verb):
        return _note("guard", verb)

    def _bribed(self):
        return i18n.t("dialogue.bribed.guard")

    def _plain(self, verb, speaker):
        if verb == "surrender":
            return Result("surrender", i18n.t("dialogue.guard.surrender"))
        if verb == "leave":
            return Result("leave", i18n.t("dialogue.guard.leave"))
        return Result("fight", i18n.t("dialogue.guard.attack"), Opening())

    def _checked(self, verb, speaker, passed, margin, line):
        if passed:
            return Result("peace", i18n.t("dialogue.guard.bluff_win", speaker=speaker.name, line=line))
        return Result("fight", i18n.t("dialogue.guard.bluff_miss", line=line),
                      Opening(surprised="player"))


class Challenge(Encounter):
    """A patrol on its rounds stops the squad it found (the dragon lair's kobolds, `lair.py`). Its
    word is its master's: a bribe needs their tongue too, and every bluff told in the place makes
    the next harder (`bluffs`). Attack starts the fight before they can call out."""
    kind = "challenge"
    verbs = ("bluff", "bribe", "attack")
    worded = frozenset({"bribe"})

    def __init__(self, foes, bluffs=0):
        super().__init__(foes, i18n.t("dialogue.title.challenge"), i18n.t("dialogue.line.challenge"))
        self.bluffs = bluffs
        self.bluffs_told = 0

    def dc(self, verb):
        return super().dc(verb) + (BLUFF_STEP * self.bluffs if verb == "bluff" else 0)

    def note(self, verb):
        return _note("challenge", verb)

    def _bribed(self):
        return i18n.t("dialogue.bribed.challenge")

    def _plain(self, verb, speaker):
        return Result("fight", i18n.t("dialogue.challenge.attack", speaker=speaker.name), Opening())

    def _checked(self, verb, speaker, passed, margin, line):
        self.bluffs_told += 1
        if passed:
            return Result("peace", i18n.t("dialogue.challenge.bluff_win", speaker=speaker.name, line=line))
        return Result("fight", i18n.t("dialogue.challenge.bluff_miss", line=line),
                      Opening(surprised="player"))


class WildfireTalk(Encounter):
    """A Wildfire focus (`wildfire.py`): get a hearing (CHA), then show them how (INT)."""
    kind = "wildfire"
    language_gate = False

    def __init__(self, guild, focus, leader):
        from . import wildfire
        self.guild, self.focus, self.wildfire = guild, focus, wildfire
        who = i18n.t("dialogue.wildfire.who_great" if focus.great else "dialogue.wildfire.who")
        line = i18n.t("dialogue.line.wildfire_great" if focus.great else "dialogue.line.wildfire")
        super().__init__([leader], focus.name.upper(), line)
        self.who = who

    def offered(self):
        step = "persuade" if self.wildfire.next_check(self.focus) == "charisma" else "teach"
        return (step, "bribe", "attack")

    def dc(self, verb):
        return self.wildfire.talk_dc(self.guild, self.focus)

    def note(self, verb):
        return _note("wildfire", verb, who=self.who)

    def refusal(self, verb):
        return i18n.t("dialogue.wildfire.refusal") if verb == "bribe" else ""

    def _plain(self, verb, speaker):
        return Result("fight", i18n.t("dialogue.wildfire.attack", who=self.who), Opening())

    def choose(self, verb, speaker, members, rng=random):
        if VERBS[verb].attr is None:
            return super().choose(verb, speaker, members, rng)
        passed, text = self.wildfire.talk(self.guild, self.focus, speaker, rng)
        if not passed:
            result = Result("fight", text, Opening())
        elif self.wildfire.can_talk(self.focus):
            result = Result("next", text)
        else:
            result = Result("peace", text)
        if result.over:
            self.result = result
        return result


class BossTalk(Encounter):
    """An arena boss presents themself before the guild's first bout against them (`arena.boss_talk`):
    one line per speaker, in order, and no verbs. The last line ends in the fight."""
    kind = "boss"
    language_gate = False

    def __init__(self, title, lines):
        """`lines`: [(unit, caption, line)], in the order they speak."""
        self.lines = list(lines)
        self.step = 0
        super().__init__([u for u, _, _ in self.lines], title, self.lines[0][2])
        self.leader = self.lines[0][0]

    def caption(self, unit):
        return self.lines[self.step][1]

    def current(self):
        if self.step < len(self.lines) - 1:
            return Result("next", i18n.t("dialogue.boss.next", who=self.lines[self.step + 1][0].name))
        return Result("fight", i18n.t("dialogue.boss.fight"), Opening())

    def advance(self):
        self.step += 1
        self.leader, _, self.line = self.lines[self.step]
        return self.current()


# --------------------------------------------------------------------------- #
# one talk being played by a person                                           #
# --------------------------------------------------------------------------- #
def button_label(kind):
    return i18n.t(f"dialogue.button.{kind}")


class Talk:
    """An encounter as a person plays it: who speaks (`first_speaker` until picked), the verb rolled,
    the result shown until they go on. `on_decided(result)` fires the moment a roll ends it (the caller
    stores it, so a reload cannot roll again); `on_done(result)` once the person reads how it ended.
    A `decided` result opens the talk already showing it."""

    def __init__(self, encounter, members, on_done, on_decided=None, decided=None):
        self.encounter = encounter
        self.members = list(members)
        self.on_done = on_done
        self.on_decided = on_decided
        self.result = decided
        self.speaker = first_speaker(encounter, self.members)

    def pick(self, unit):
        if self.result is not None:
            raise ValueError(i18n.t("dialogue.error.cast"))
        if not self.encounter.offered():
            raise ValueError(i18n.t("dialogue.error.silent"))
        if unit not in self.members:
            raise ValueError(i18n.t("dialogue.error.member"))
        self.speaker = unit

    def choose(self, verb):
        if self.result is not None:
            raise ValueError(i18n.t("dialogue.error.cast"))
        if self.speaker is None:
            raise ValueError(i18n.t("dialogue.error.speaker"))
        self.result = self.encounter.choose(verb, self.speaker, self.members)
        if self.result.over and self.on_decided is not None:
            self.on_decided(self.result)
        return self.result

    def go_on(self):
        """The result's button: the end handed to `on_done` (its answer returned), or the next step."""
        if self.result is None:
            raise ValueError(i18n.t("dialogue.error.unsaid"))
        if self.result.over:
            return self.on_done(self.result)
        self.result = self.encounter.advance()
        return None


# --------------------------------------------------------------------------- #
# the squad's side, when nobody plays it                                       #
# --------------------------------------------------------------------------- #
_VALUE = {"peace": 1.0, "fight": 0.0, "surprised": -0.5, "shaken": 0.4, "jumped": -0.2}
_EXPECT = {"persuade": ("peace", "fight"), "bluff": ("peace", "surprised"),
           "intimidate": ("shaken", "jumped"), "teach": ("peace", "fight")}


def ai_choice(encounter, members, fight_odds=0.5):
    """`(verb, speaker)` the squad's AI takes: the open option with the best expected worth,
    `fight_odds` being its chance to win the fight (an `autowin` estimate when it has one).
    A bribe is worth taking when it costs less than a tenth of the group's purse."""
    fight = fight_odds - 0.5
    best, best_val = ("attack", members[0]), fight
    purse = _purse(members)
    for speaker in members:
        for opt in encounter.options(speaker, members):
            if not opt.open:
                continue
            if opt.verb == "bribe":
                val = 1.0 if encounter.price() * 10 <= purse else fight
            elif opt.verb in _EXPECT:
                win, lose = _EXPECT[opt.verb]
                val = opt.odds * (_VALUE[win] + (fight if win == "shaken" else 0)) \
                    + (1 - opt.odds) * (_VALUE[lose] + fight)
            else:
                continue
            if val > best_val:
                best, best_val = (opt.verb, speaker), val
    return best


def ai_play(encounter, members, fight_odds=0.5, rng=random):
    """Play `encounter` to its end for a squad nobody plays (`ai_choice` at every step)."""
    while True:
        verb, speaker = ai_choice(encounter, members, fight_odds)
        result = encounter.choose(verb, speaker, members, rng)
        if result.over:
            return result
