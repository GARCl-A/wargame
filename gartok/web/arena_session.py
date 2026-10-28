"""The arena in the browser: the bouts on offer, who fights and the stake, as pygame's `SquadScreen` in
arena mode (`App._open_arena`); a due title defense goes straight to the board, as
`App._start_title_defense`. The bout is a campaign fight (`campaign_fight._enter`) whose report pays the
purse; a boss's lines come first the guild's first time (`dialogue_session.boss_talk`).

Won against Adelio or the Ribbit Brothers, the report ends on the same screen with the offer to recruit
them (`AdelioPromptScreen`, `RibbitPromptScreen`), which opens the Tavern's RECRUIT with them alone."""

from typing import ClassVar

from .. import arena, artwork, economy, matchup, objectives, orders, world
from ..battle import Battle
from ..constants import fmt_money
from .campaign_fight import _enter
from .map_session import _portrait, _when
from .session import Session, asset_url

BLURBS = {
    "pit": "The Pit's opening fight: scrappers off the street, one for each of yours.",
    "champion": "Adelio Small-Knife and two hired nobodies, on the Pit's own sand. Whoever puts him down "
                "takes his title, and there is no rematch.",
    "brawl": "The Games' straight fight: three a side, opponents of any level from 1 to 6.",
    "ctf": "Three a side again, but it ends when a fighter carries their flag home, not when a side falls.",
    "boss": "The three Ribbit brothers and three lackeys, capture the flag on their own field, six a side.",
}
RECRUITS = {
    "adelio": {"title": "The Fallen Champion", "button": "Talk to Adelio", "leave": "Leave him",
               "lines": ["Adelio Small-Knife lies defeated on the sands of the Pit.",
                         "His title is lost, but his blade is still sharp.",
                         "Do you want to convince him to join your guild?"]},
    "ribbits": {"title": "The Fallen Brothers", "button": "Talk to the brothers", "leave": "Leave them",
                "lines": ["The Ribbit Brothers croak in defeat on the field.",
                          "They are tough, cunning and know how to fight together.",
                          "Do you want to convince them to join your guild?"]},
}


def _kind(b):
    return "champion" if b.champion else "boss" if b.boss else "ctf" if b.ctf else "brawl" if b.stage2 else "pit"


def open_arena(map_session, group):
    """What entering the arena opens: the champion's due defense when they stand in this band, else
    the bouts."""
    champ = arena.champion_of(map_session.guild)
    if arena.defense_due(map_session.guild) and champ in group.members:
        return title_defense(map_session, group)
    session = ArenaSession(map_session, group)
    map_session.game.open(session)
    return {"screen": session.screen}


def title_defense(map_session, group):
    """The champion alone against one newcomer built a level above them; no stake, not to the death."""
    guild, node = map_session.guild, world.node(group.node)
    champ, offer = arena.champion_of(guild), arena.defense_bout()
    enemies, scenario = matchup.build(node, offer, squad_size=1, guild=guild)
    battle = Battle([champ], enemies, scenario=scenario, daylight=guild.clock.is_daylight, lethal=False,
                    arena=True, clock_day=guild.clock.day)
    return _bout(map_session, group, [champ], battle, node, offer)


def _bout(map_session, group, squad, battle, node, offer):
    guild = map_session.guild

    def settle(outcome):
        objectives.complete(guild, "obj_arena_bout")
        note = outcome.arena_title_event
        return [note] if note and outcome.arena_reward is None else []

    def after(outcome):
        from .dialogue_session import _to_map
        recruit = None
        if outcome.won and offer.champion and not any(u.name.startswith("Adelio") for u in guild.roster):
            recruit = "adelio"
        elif outcome.won and offer.boss:
            recruit = "ribbits"
        if recruit is None:
            return _to_map(map_session, group)
        session = ArenaSession(map_session, group, recruit=recruit)
        map_session.game.open(session)
        return {"screen": session.screen}

    return _enter(map_session, group, battle, node, offer.name, offer.name, settle,
                  squad=squad, offer=offer, after=after)


class ArenaSession(Session):
    screen = "arena"
    GET: ClassVar[dict] = {"state": lambda s, q: s.state()}
    POST: ClassVar[dict] = {
        "bout": lambda s, b: s.pick_bout(int(b["i"])),
        "pick": lambda s, b: s.toggle(b["uid"]),
        "fight": lambda s, b: s.fight(),
        "back": lambda s, b: s.map.back(),
        "recruit": lambda s, b: s.recruit(),
        "leave": lambda s, b: s.leave(),
    }

    def __init__(self, map_session, group, recruit=None):
        self.map = map_session
        self.guild = map_session.guild
        self.group = group
        self.node = world.node(group.node)
        self.offered = recruit             # "adelio" | "ribbits": the report ended on the offer to recruit
        self.bouts = arena.bouts_on_offer(self.guild)
        self.at = 0
        fit = [u for u in group.members if not u.incapacitated]
        self.picked = fit if len(fit) <= self.offer.player_cap else []

    @property
    def offer(self):
        return self.bouts[self.at]

    @property
    def cost(self):
        return self.offer.entry * len(self.picked)

    @property
    def why(self):
        """Why the bout cannot be fought as picked, or None."""
        if not self.picked:
            return "Pick who fights"
        if len(self.picked) > self.offer.player_cap:
            return f"At most {self.offer.player_cap} may fight this bout"
        if self.group.money < self.cost:
            return f"The band holds {fmt_money(self.group.money)} of the {fmt_money(self.cost)} stake"
        return None

    # ------------------------------------------------------------------ #
    def _bouts_open(self):
        if self.offered is not None:
            raise ValueError("the bout is over")

    def pick_bout(self, i):
        self._bouts_open()
        if not 0 <= i < len(self.bouts):
            raise ValueError("no such bout")
        self.at = i
        del self.picked[self.offer.player_cap:]     # a smaller bout drops the overflow
        return self.state()

    def toggle(self, uid):
        self._bouts_open()
        u = next((m for m in self.group.members if m.uid == uid), None)
        if u is None:
            raise ValueError("no such member in the band")
        if u in self.picked:
            self.picked.remove(u)
        elif u.incapacitated:
            raise ValueError(f"{u.name} has collapsed from hunger and cannot fight")
        elif len(self.picked) >= self.offer.player_cap:
            raise ValueError(f"at most {self.offer.player_cap} may fight this bout")
        else:
            self.picked.append(u)
        return self.state()

    def fight(self):
        """Stake and fight, as `App._start_battle`: the stake comes out of the whole band's purses."""
        self._bouts_open()
        if self.why is not None:
            raise ValueError(self.why)
        guild, node, offer, squad = self.guild, self.node, self.offer, list(self.picked)
        economy.charge_richest_first(self.group.members, self.cost)
        enemies, scenario = matchup.build(node, offer, squad_size=len(squad), guild=guild)
        battle = Battle(squad, enemies, scenario=scenario, daylight=guild.clock.is_daylight, lethal=node.lethal,
                        arena=node.arena, clock_day=guild.clock.day)
        talk = arena.boss_talk(guild, offer)
        if talk is None:
            return _bout(self.map, self.group, squad, battle, node, offer)
        from .dialogue_session import boss_talk
        guild.boss_talks_seen.add(arena.boss_talk_key(offer))
        session = boss_talk(self.map, self.group, talk, lambda: _bout(self.map, self.group, squad, battle, node, offer))
        self.map.game.open(session)
        return {"screen": session.screen}

    def recruit(self):
        """Talk them round: the Tavern's RECRUIT with them as the only strangers."""
        if self.offered is None:
            raise ValueError("nobody to recruit here")
        from .hub_session import HubSession
        if self.offered == "adelio":
            adelio = arena.load_champion()
            adelio.arena_title, adelio.arena_role, adelio.side = False, None, "player"
            candidates = [adelio]
        else:
            candidates = arena.load_ribbit_brothers()
        session = HubSession(self.map, self.group, orders.Order("pit_recruit"), candidates=candidates)
        self.map.game.open(session)
        return {"screen": session.screen}

    def leave(self):
        if self.offered is None:
            raise ValueError("nobody to leave here")
        from .dialogue_session import _to_map
        return _to_map(self.map, self.group)

    # ------------------------------------------------------------------ #
    def state(self):
        g, n = self.group, self.node
        day, at = _when(self.guild, 0)
        v = world.vendor(n.id, "arena")
        out = {"place": n.name, "band": g.display_name, "day": day, "at": at,
               "keeper": None if v is None else {
                   "name": v.name, "caption": f"{v.race} {v.role}", "line": v.line,
                   "portrait": asset_url(artwork.portrait_path(None, v.portrait)) if v.portrait else None}}
        if self.offered is not None:
            return {**out, "recruit": self._recruit()}
        champ, due = arena.champion_of(self.guild), arena.defense_due(self.guild)
        return {**out, "bouts": [self._bout(i, b) for i, b in enumerate(self.bouts)],
                "members": [self._member(u) for u in g.members],
                "stake": {"per": self.offer.entry, "fighters": len(self.picked), "cost": self.cost,
                          "cost_text": fmt_money(self.cost), "held": g.money, "held_text": fmt_money(g.money),
                          "cap": self.offer.player_cap},
                "why": self.why,
                "defense": None if not due else {
                    "name": champ.name, "by": arena.defense_deadline(self.guild),
                    "line": f"{champ.name} must come to the Pit to defend the title by day "
                            f"{arena.defense_deadline(self.guild)}; this band does not bring them."}}

    def _bout(self, i, b):
        return {"i": i, "name": b.name, "kind": _kind(b), "blurb": BLURBS[_kind(b)],
                "entry": b.entry, "entry_text": fmt_money(b.entry), "purse": b.purse, "purse_text": fmt_money(b.purse),
                "foes": b.enemies + (len(arena.RIBBIT_SLUGS) if b.boss else 0), "cap": b.player_cap,
                "levels": arena.bout_level_range(b, self.picked), "max_level": arena.bout_max_combat_level(b),
                "picked": i == self.at}

    def _member(self, u):
        lvl = f"C{u.combat_level}" + (f"/W{u.work_level}" if u.work_xp or u.work_level else "") + f"/R{u.racial_level}"
        n, faces = u.weapon["damage"] if u.weapon else u.unarmed_damage
        flags = []
        if u.incapacitated:
            flags.append({"text": "Collapsed from hunger", "tone": "bad"})
        elif u.hunger_level:
            flags.append({"text": f"Hunger: {u.hunger_label}", "tone": "bad" if u.hunger_level >= 2 else "warn"})
        if u.sick:
            flags.append({"text": "Sick", "tone": "bad"})
        if u.combat_level > arena.bout_max_combat_level(self.offer):
            flags.append({"text": f"No combat XP: the foes stop at level {arena.bout_max_combat_level(self.offer)}",
                          "tone": "warn"})
        if u.pending_picks:
            flags.append({"text": "Talent pick ready", "tone": "good"})
        return {"uid": u.uid, "name": u.name, "race": u.race["name"], "occupation": u.occupation["name"],
                "portrait": _portrait(u), "hp": [max(0, u.hp), u.hp_max], "ac": u.ac, "md": u.mental_defense,
                "speed": u.speed, "weapon": u.weapon_name or "Unarmed", "dmg": f"{n}d{faces}",
                "money": u.money, "money_text": fmt_money(u.money), "level": lvl, "flags": flags,
                "unfit": u.incapacitated, "picked": u in self.picked,
                "title": bool(getattr(u, "arena_title", False))}

    def _recruit(self):
        r = RECRUITS[self.offered]
        if self.offered == "adelio":
            faces = [arena.load_champion()]
        else:
            faces = arena.load_ribbit_brothers()
        return {**r, "who": self.offered,
                "faces": [{"name": u.name, "portrait": _portrait(u), "race": u.race["name"]} for u in faces]}
