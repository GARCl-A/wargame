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

from . import economy, recruit

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
    label: str
    attr: str | None          # the speaker's attribute it rolls; None = no check
    spoken: bool              # needs a language shared with the leader


PARLEY_VERBS = ("persuade", "bluff", "intimidate")   # the Human's Parley talent adds to these

VERBS = {v.id: v for v in (
    Verb("persuade", "Persuade", "charisma", True),
    Verb("teach", "Teach", "intelligence", True),
    Verb("bluff", "Bluff", "charisma", True),
    Verb("intimidate", "Intimidate", "charisma", True),
    Verb("bribe", "Bribe", None, False),
    Verb("surrender", "Surrender", None, False),
    Verb("leave", "Run", None, False),
    Verb("attack", "Attack", None, False),
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
    return total >= dc, total - dc, f"d20({nat}) {mod:+} = {total} vs DC {dc}"


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
        return f"{unit.race['name']} {unit.occupation['name']}"

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
                opt.check = f"{v.attr[:3].upper()} {mod:+d} vs DC {dc}"
                opt.odds = odds(mod, dc)
            if verb == "bribe":
                opt.check = f"${self.price()}"
                if _purse(members) < self.price():
                    opt.block = "not enough coin"
            opt.block = self.refusal(verb) or opt.block
            if (v.spoken or verb in self.worded) and not self.shared(speaker):
                opt.block = (f"needs {', '.join(self.leader.languages)}" if self.leader is not None
                             else "nobody there talks")
            out.append(opt)
        return out

    def option(self, verb, speaker, members):
        return next((o for o in self.options(speaker, members) if o.verb == verb), None)

    # -- trying it ------------------------------------------------------- #
    def choose(self, verb, speaker, members, rng=random):
        opt = self.option(verb, speaker, members)
        if opt is None or not opt.open:
            raise ValueError(f"{verb!r} is not open: {opt.block if opt else 'not offered'}")
        if verb == "bribe":
            price = self.price()
            economy.charge_richest_first(members, price)
            result = Result("peace", f"{speaker.name} counts out ${price}. {self._bribed()}", paid=price)
        elif VERBS[verb].attr is None:
            result = self._plain(verb, speaker)
        else:
            passed, margin, line = roll(self.mod(verb, speaker), self.dc(verb), rng)
            result = self._checked(verb, speaker, passed, margin, line)
        if result.over:
            self.result = result
        return result

    def _bribed(self):
        return "They take it and let you go."

    def _plain(self, verb, speaker):
        return Result("fight", "Steel it is.", Opening())

    def _checked(self, verb, speaker, passed, margin, line):
        raise NotImplementedError


class Ambush(Encounter):
    """A pack that found the group first: on the road, at work, on a supply run."""
    kind = "ambush"
    verbs = ("persuade", "bluff", "intimidate", "bribe", "attack")

    def __init__(self, foes, title="AMBUSHED", line=None):
        n = len(foes)
        super().__init__(foes, title, line or f'"Your purse or your blood." {n} of them block the way.')
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
        return {"persuade": "talk them out of it: no fight · a miss and it is a fight",
                "bluff": "send them off on a lie · a miss and they strike first",
                "intimidate": "shake them: they start demoralized, or run · a miss gives them the jump",
                "bribe": "pay them off: no fight",
                "attack": "roll initiative"}.get(verb, "")

    def _checked(self, verb, speaker, passed, margin, line):
        who = self.leader.name if self.leader is not None else "They"
        if verb == "persuade":
            if passed:
                return Result("peace", f"{speaker.name} talks {who} down ({line}). They let you by.")
            return Result("fight", f"{who} will not hear it ({line}).", Opening())
        if verb == "bluff":
            if passed:
                return Result("peace", f"{speaker.name}'s story holds ({line}). They go looking elsewhere.")
            return Result("fight", f"{who} sees through it ({line}) and strikes first!",
                          Opening(surprised="player"))
        if passed and margin >= ROUT_MARGIN:
            return Result("peace", f"{speaker.name} stares {who} down ({line}). They break and run.")
        if passed:
            return Result("fight", f"{speaker.name} shakes them ({line}). They come on, but unsure.",
                          Opening(demoralized="enemy"))
        return Result("fight", f"{who} laughs it off ({line}) and gets the jump on you.",
                      Opening(initiative={"enemy": INITIATIVE_EDGE}))


class Patrol(Encounter):
    """The City guard has caught members with a rap sheet (`justice.catch`)."""
    kind = "guard"

    def __init__(self, foes, caught, can_run):
        names = ", ".join(u.name for u in caught)
        super().__init__(foes, "THE GUARD", f'"{names}, in the name of the City -- you will come with us."')
        self.caught = list(caught)
        self.can_run = can_run

    def offered(self):
        return ("surrender", "bluff", "bribe", "attack") + (("leave",) if self.can_run else ())

    def price(self):
        return GUARD_BRIBE_PER_CRIME * max(1, sum(u.crime for u in self.caught))

    def note(self, verb):
        return {"surrender": "crime clears to 0: time served in the City's cells",
                "bluff": "the wrong man: they let you go, the crime stays · a miss and they strike first",
                "bribe": "they look away: the crime stays",
                "attack": "lethal; living through it adds to the rap sheet",
                "leave": "fall back the way the group came"}.get(verb, "")

    def _bribed(self):
        return "The patrol finds somewhere else to be. The rap sheet stays."

    def _plain(self, verb, speaker):
        if verb == "surrender":
            return Result("surrender", "The group lays down its arms.")
        if verb == "leave":
            return Result("leave", "The group turns and runs.")
        return Result("fight", "The group draws on the City guard.", Opening())

    def _checked(self, verb, speaker, passed, margin, line):
        if passed:
            return Result("peace", f"{speaker.name} swears it is a mistake ({line}). The patrol moves on.")
        return Result("fight", f"Nobody believes it ({line}). The patrol draws steel!",
                      Opening(surprised="player"))


class Challenge(Encounter):
    """A patrol on its rounds stops the squad it found (the dragon lair's kobolds, `lair.py`). Its
    word is its master's: a bribe needs their tongue too, and every bluff told in the place makes
    the next harder (`bluffs`). Attack starts the fight before they can call out."""
    kind = "challenge"
    verbs = ("bluff", "bribe", "attack")
    worded = frozenset({"bribe"})

    def __init__(self, foes, bluffs=0):
        super().__init__(foes, "CHALLENGED", "\"Who walks in the master's halls?\" The patrol raises its torch.")
        self.bluffs = bluffs
        self.bluffs_told = 0

    def dc(self, verb):
        return super().dc(verb) + (BLUFF_STEP * self.bluffs if verb == "bluff" else 0)

    def note(self, verb):
        return {"bluff": "the new shift, or tribute for the master · a miss rings the alarm",
                "bribe": "kobolds love what shines: they let you be",
                "attack": "silence them before their next turn, or they call out"}.get(verb, "")

    def _bribed(self):
        return "The coins vanish into the patrol's pouches. They walk on."

    def _plain(self, verb, speaker):
        return Result("fight", f"{speaker.name} strikes before they can call out!", Opening())

    def _checked(self, verb, speaker, passed, margin, line):
        self.bluffs_told += 1
        if passed:
            return Result("peace", f"{speaker.name}'s Draconic holds ({line}). The patrol walks on.")
        return Result("fight", f"The kobolds hiss at the lie ({line}) and strike first!",
                      Opening(surprised="player"))


class WildfireTalk(Encounter):
    """A Wildfire focus (`wildfire.py`): get a hearing (CHA), then show them how (INT)."""
    kind = "wildfire"
    language_gate = False

    def __init__(self, guild, focus, leader):
        from . import wildfire
        self.guild, self.focus, self.wildfire = guild, focus, wildfire
        who = "the Ogre" if focus.great else "the foreman"
        line = ('"Fire clears ground. Everybody knows that." The Ogre does not look up.' if focus.great
                else '"More wood! Green wood burns longest!" The foreman waves the crew on.')
        super().__init__([leader], focus.name.upper(), line)
        self.who = who

    def offered(self):
        step = "persuade" if self.wildfire.next_check(self.focus) == "charisma" else "teach"
        return (step, "bribe", "attack")

    def dc(self, verb):
        return self.wildfire.talk_dc(self.guild, self.focus)

    def note(self, verb):
        return {"persuade": f"get a hearing from {self.who} · a miss and they fight",
                "teach": "show them how to burn a clearing right · a miss and they fight",
                "attack": "take the camp by force"}.get(verb, "")

    def refusal(self, verb):
        return "they want to learn, not be paid" if verb == "bribe" else ""

    def _plain(self, verb, speaker):
        return Result("fight", f"The squad goes for {self.who}.", Opening())

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
            return Result("next", f"{self.lines[self.step + 1][0].name} steps up.")
        return Result("fight", "The crowd roars. The bout begins.", Opening())

    def advance(self):
        self.step += 1
        self.leader, _, self.line = self.lines[self.step]
        return self.current()


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
