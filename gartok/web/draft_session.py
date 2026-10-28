"""A new guild in the browser, as pygame's `VocationScreen` and `DraftScreen`: the vocation, the pool of
nine with the commission tokens, then the charter (the name, the banner, who leads). The pool's rules are
pygame's own `DraftScreen` held headless; FOUND THE GUILD founds it as `App._draft_done` and opens the map.

The title's New guild opens it."""

from typing import ClassVar

from .. import artwork, persist, recorder, settings, vocations, wildfire, world
from ..archetypes import ARCHETYPES, is_compatible, unit_archetypes
from ..combatant import Combatant
from ..draft_screen import (
    _MAX_GUILD_NAME,
    COMMISSION_TOKENS,
    POOL_SIZE,
    TEAM_SIZE,
    DraftScreen,
    _leader_recruits,
)
from ..guild import Guild
from ..tutorial import TutorialState
from ..ui.banner import BANNER_COLORS
from ..ui.sheet_card import unit_to_ch
from .map_session import MapSession, _icon, _portrait
from .session import Session, asset_url

STEPS = ("vocation", "pick", "charter")
VOCATION_GLYPHS = {vocations.WARBAND: "item/round-shield", vocations.DELVERS: "item/war-pick",
                   vocations.WILDS: "item/pocket-bow", vocations.SCHOLARS: "item/book-cover",
                   vocations.CARAVAN: "item/compass", vocations.MARSH: "item/drop"}
_UNIT_NAME = 24


class DraftSession(Session):
    screen = "draft"
    GET: ClassVar[dict] = {"state": lambda s, q: s.state()}
    POST: ClassVar[dict] = {
        "vocation": lambda s, b: s.choose_vocation(b["id"]),
        "next": lambda s, b: s.next(),
        "back": lambda s, b: s.back(),
        "pick": lambda s, b: s.pick(int(b["index"])),
        "commission": lambda s, b: s.commission(list(b["labels"])),
        "cancel": lambda s, b: s.cancel(),
        "name": lambda s, b: s.set_name(b["name"]),
        "rename": lambda s, b: s.rename(int(b["index"]), b["name"]),
        "color": lambda s, b: s.set_color(int(b["index"])),
        "emblem": lambda s, b: s.set_emblem(b["slug"]),
        "leader": lambda s, b: s.set_leader(int(b["index"])),
        "found": lambda s, b: s.found(b.get("name")),
    }

    def __init__(self):
        self.step = "vocation"
        self.vocation = None
        self.draft = None           # pygame's DraftScreen, made once the vocation is settled
        self.tutorial = TutorialState()

    def tutorials(self):
        return self.tutorial

    def tutorial_key(self):
        """As pygame's draft: the welcome first, then the card of the step."""
        if "draft.intro" not in self.tutorial.seen:
            return "draft.intro"
        return {"vocation": "draft.vocation", "pick": "draft.pick", "charter": "draft.identity"}[self.step]

    # ------------------------------------------------------------------ #
    # verbs                                                              #
    # ------------------------------------------------------------------ #
    def _at(self, *steps):
        if self.step not in steps:
            raise ValueError(f"not on the {' or '.join(steps)} step")

    def choose_vocation(self, vid):
        self._at("vocation")
        v = vocations.get(vid)
        if v is None:
            raise ValueError(f"no vocation called {vid}")
        if not v.active:
            raise ValueError(f"{v.name} is not open yet")
        self.vocation = vid
        return self.state()

    def next(self):
        if self.step == "vocation":
            if self.vocation is None:
                raise ValueError("pick a vocation first")
            if self.draft is None or self.draft.vocation != self.vocation:
                self.draft = DraftScreen(None, on_done=None, tutorial=self.tutorial, vocation=self.vocation)
            self.step = "pick"
        elif self.step == "pick":
            if len(self.draft.picks) != TEAM_SIZE:
                raise ValueError(f"pick {TEAM_SIZE} of the {POOL_SIZE}")
            self.draft.pending_labels = []
            if self.draft.leader_pick not in self.draft.picks:
                self.draft.leader_pick = None
            self.step = "charter"
        else:
            raise ValueError("the charter is the last step")
        return self.state()

    def back(self):
        """A step back; from the vocation, the title. The pool stays while the vocation does."""
        if self.step == "vocation":
            from .title_session import TitleSession
            self.game.open(TitleSession())
            return {"screen": TitleSession.screen}
        self.step = STEPS[STEPS.index(self.step) - 1]
        return self.state()

    def pick(self, index):
        """Pick or let go of a candidate; with a commission waiting, it replaces that candidate."""
        self._at("pick")
        if not 0 <= index < len(self.draft.pool):
            raise ValueError("no such candidate")
        unit = self.draft.pool[index]
        if self.draft.pending_labels:
            self.draft._replace(unit)
        elif unit not in self.draft.picks and len(self.draft.picks) >= TEAM_SIZE:
            raise ValueError(f"the squad is {TEAM_SIZE}: let one go first")
        else:
            self.draft._toggle_pick(unit)
        return self.state()

    def commission(self, labels):
        """Call for `labels`, a token each; the next candidate picked is replaced by one who has them."""
        self._at("pick")
        if not labels:
            raise ValueError("tick at least one archetype")
        if len(labels) > self.draft.tokens:
            raise ValueError(f"{self.draft.tokens} token{'s' * (self.draft.tokens != 1)} left")
        chosen = []
        for key in labels:
            if key not in ARCHETYPES:
                raise ValueError(f"no archetype called {key}")
            if not is_compatible(chosen, key):
                raise ValueError(f"{key} does not go with {', '.join(chosen)}")
            chosen.append(key)
        self.draft.pending_labels = chosen
        return self.state()

    def cancel(self):
        self._at("pick")
        self.draft.pending_labels = []
        return self.state()

    def set_name(self, name):
        self._at("charter")
        self.draft.guild_name = str(name).strip()[:_MAX_GUILD_NAME]
        return self.state()

    def rename(self, index, name):
        self._at("charter")
        name = str(name).strip()[:_UNIT_NAME]
        if not name:
            raise ValueError("a founder needs a name")
        self._founder(index).name = name
        return self.state()

    def set_color(self, index):
        self._at("charter")
        if not 0 <= index < len(BANNER_COLORS):
            raise ValueError("no such colour")
        self.draft.banner_color = BANNER_COLORS[index][1]
        return self.state()

    def set_emblem(self, slug):
        self._at("charter")
        if slug not in {s for _, s, _ in artwork.BANNER_ICONS}:
            raise ValueError(f"no emblem called {slug}")
        self.draft.banner_icon = slug
        return self.state()

    def set_leader(self, index):
        self._at("charter")
        self.draft.leader_pick = self._founder(index)
        return self.state()

    def _founder(self, index):
        if not 0 <= index < len(self.draft.picks):
            raise ValueError("no such founder")
        return self.draft.picks[index]

    def found(self, name=None):
        """Found the guild as `App._draft_done` does, save it and open the map; `name` is the guild's name
        as last written, when it was not sent on its own."""
        self._at("charter")
        d = self.draft
        if name is not None:
            self.set_name(name)
        if d.leader_pick is None:
            raise ValueError("pick who leads the guild")
        world_id = persist.new_world_id()
        guild = Guild(d.picks, node=world.START_NODE, leader=d.leader_pick, name=d.guild_name or "The Guild",
                      banner_color=d.banner_color, banner_icon=d.banner_icon, tutorial=self.tutorial,
                      vocation=self.vocation)
        wildfire.sync_world(guild)
        if settings.get("record_play") == "ON":
            recorder.attach(persist.world_dir(world_id), guild)
        m = MapSession(guild, world_id)
        self.game.open(m)
        m._land()
        return {"screen": m.screen}

    # ------------------------------------------------------------------ #
    # the screen                                                         #
    # ------------------------------------------------------------------ #
    def state(self):
        out = {"step": self.step, "steps": self._steps(), "vocation": self._vocation(self.vocation)}
        if self.step == "vocation":
            out["vocations"] = [self._vocation(v.id) for v in vocations.VOCATIONS.values()]
        elif self.step == "pick":
            d = self.draft
            out.update(pool=[self._card(u) for u in d.pool], squad=[d.pool.index(u) for u in d.picks],
                       team=TEAM_SIZE, tokens=d.tokens, tokens_max=COMMISSION_TOKENS, pending=list(d.pending_labels),
                       archetypes=[{"key": a.key, "label": a.label, "desc": a.desc, "style": a.style}
                                   for a in ARCHETYPES.values()])
        else:
            out["charter"] = self._charter()
        return out

    def _steps(self):
        d = self.draft
        voc = vocations.get(self.vocation)
        now = STEPS.index(self.step)
        squad = ", ".join(u.name for u in d.picks) if d else ""
        rows = [("Vocation", voc.name if voc and now > 0 else "The trade it is founded on"),
                ("The squad", squad if now > 1 else f"{len(d.picks)} of {TEAM_SIZE} picked from the {POOL_SIZE}"
                 if now == 1 else f"{TEAM_SIZE} of {POOL_SIZE}"),
                ("The charter", "Its name, its arms, who leads")]
        return [{"label": label, "sub": sub, "state": "done" if i < now else "now" if i == now else "later"}
                for i, (label, sub) in enumerate(rows)]

    def _vocation(self, vid):
        v = vocations.get(vid)
        if v is None:
            return None
        return {"id": v.id, "name": v.name, "motto": v.motto, "perk": v.perk, "open": v.active,
                "icon": VOCATION_GLYPHS.get(v.id), "chosen": v.id == self.vocation,
                "races": [{"race": r, "portrait": asset_url(artwork.portrait_path(r, 0))} for r in v.races]}

    def _card(self, u):
        d = self.draft
        ch = unit_to_ch(Combatant(u))
        called = d.commissioned.get(id(u), [])
        tags = [{"label": lb, "style": st, "desc": ds, "commissioned": lb in called} for lb, st, ds in unit_archetypes(u)]
        tags.sort(key=lambda t: not t["commissioned"])
        w = ch["weapon"]
        return {"name": u.name, "race": ch["race"], "occ": ch["occ"], "align": ch["align"], "size": ch["size"],
                "age": ch["age"], "portrait": _portrait(u), "hp": ch["hp"][1], "ac": ch["ac"], "md": ch["md"],
                "spd": ch["spd"], "init": ch["init"],
                "attrs": [{"k": k, "v": v, "mod": m} for k, v, m, _ in ch["attrs"]],
                "weapon": {"name": w["nm"], "hit": w["hit"], "dmg": w["dmg"],
                           "tags": " · ".join(p.strip() for p in w["tags"].split("·") if p.strip()),
                           "action": w["action"]},
                "ability": {"name": ch["ability"][0], "text": ch["ability"][1]}, "langs": ch["langs"],
                "tags": tags, "commissioned": bool(called), "picked": u in d.picks}

    def _charter(self):
        d = self.draft
        founders = []
        for u in d.picks:
            card = self._card(u)
            n, why = _leader_recruits(u)
            card.update(recruits=n, recruits_why=why, leader=u is d.leader_pick)
            founders.append(card)
        return {"name": d.guild_name, "max_name": _MAX_GUILD_NAME, "max_founder": _UNIT_NAME,
                "color": list(d.banner_color), "emblem": d.banner_icon,
                "colors": [{"name": n, "rgb": list(c), "on": tuple(c) == tuple(d.banner_color)} for n, c in BANNER_COLORS],
                "emblems": [{"slug": s, "label": lb, "icon": _icon((c, s)), "on": s == d.banner_icon}
                            for c, s, lb in artwork.BANNER_ICONS],
                "founders": founders, "can_found": d.leader_pick is not None}
