"""The arena in the browser: the bouts on offer, who fights and the stake, as pygame's `SquadScreen` in
arena mode (`App._open_arena`); a due title defense goes straight to the board, as
`App._start_title_defense`. The bout is a campaign fight (`campaign_fight._enter`) whose report pays the
purse; a boss's lines come first the guild's first time (`dialogue_session.boss_talk`).

Won against Adelio or the Ribbit Brothers, the report ends on the same screen with the offer to recruit
them (`AdelioPromptScreen`, `RibbitPromptScreen`), which opens the Tavern's RECRUIT with them alone."""

from typing import ClassVar

from .. import arena, art_files, economy, i18n, matchup, objectives, orders, world
from ..battle import Battle
from ..constants import fmt_money
from .campaign_fight import _enter
from .map_session import _portrait, _when
from .session import Session, asset_url


def _recruit_card(who):
    return {"title": i18n.t(f"arena_session.recruit.{who}.title"), "button": i18n.t(f"arena_session.recruit.{who}.button"),
            "leave": i18n.t(f"arena_session.recruit.{who}.leave"), "lines": i18n.t(f"arena_session.recruit.{who}.lines")}


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
    return _bout(map_session, group, [champ], battle, node, offer, arena.DEFENSE_NATURE)


def _bout(map_session, group, squad, battle, node, offer, nature):
    guild = map_session.guild

    def settle(outcome):
        objectives.complete(guild, "obj_arena_bout")
        note = outcome.arena_title_event
        return [note] if note and outcome.arena_reward is None else []

    def after(outcome):
        from .dialogue_session import _to_map
        recruit = None
        if outcome.won and offer.champion and not any(u.bio_slug == arena.CHAMPION_SLUG for u in guild.roster):
            recruit = "adelio"
        elif outcome.won and offer.boss:
            recruit = "ribbits"
        if recruit is None:
            return _to_map(map_session, group)
        session = ArenaSession(map_session, group, recruit=recruit)
        map_session.game.open(session)
        return {"screen": session.screen}

    return _enter(map_session, group, battle, node, offer.name, offer.name, settle,
                  squad=squad, offer=offer, after=after, nature=nature)


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

    def tutorial_key(self):
        return "squad"

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
            return i18n.t("arena_session.pick_who_fights")
        if len(self.picked) > self.offer.player_cap:
            return i18n.t("arena_session.at_most_may_fight_this", player_cap=self.offer.player_cap)
        if self.group.money < self.cost:
            return i18n.t("arena_session.band_holds_of_stake", held=fmt_money(self.group.money), stake=fmt_money(self.cost))
        return None

    # ------------------------------------------------------------------ #
    def _bouts_open(self):
        if self.offered is not None:
            raise ValueError(i18n.t("arena_session.bout_is_over"))

    def pick_bout(self, i):
        self._bouts_open()
        if not 0 <= i < len(self.bouts):
            raise ValueError(i18n.t("arena_session.no_such_bout"))
        self.at = i
        del self.picked[self.offer.player_cap:]     # a smaller bout drops the overflow
        return self.state()

    def toggle(self, uid):
        self._bouts_open()
        u = next((m for m in self.group.members if m.uid == uid), None)
        if u is None:
            raise ValueError(i18n.t("arena_session.no_such_member_in_band"))
        if u in self.picked:
            self.picked.remove(u)
        elif u.incapacitated:
            raise ValueError(i18n.t("arena_session.has_collapsed_from_hunger_and", name=u.name))
        elif len(self.picked) >= self.offer.player_cap:
            raise ValueError(i18n.t("arena_session.at_most_may_fight_this_2", player_cap=self.offer.player_cap))
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
        def go():
            return _bout(self.map, self.group, squad, battle, node, offer, arena.BOUT_NATURE)

        if talk is None:
            return go()
        from .dialogue_session import boss_talk
        guild.boss_talks_seen.add(arena.boss_talk_key(offer))
        session = boss_talk(self.map, self.group, talk, go)
        self.map.game.open(session)
        return {"screen": session.screen}

    def recruit(self):
        """Talk them round: the Tavern's RECRUIT with them as the only strangers."""
        if self.offered is None:
            raise ValueError(i18n.t("arena_session.nobody_to_recruit_here"))
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
            raise ValueError(i18n.t("arena_session.nobody_to_leave_here"))
        from .dialogue_session import _to_map
        return _to_map(self.map, self.group)

    # ------------------------------------------------------------------ #
    def state(self):
        g, n = self.group, self.node
        day, at = _when(self.guild, 0)
        v = world.vendor(n.id, "arena")
        out = {"place": n.name, "band": g.display_name, "day": day, "at": at,
               "keeper": None if v is None else {
                   "name": v.shown, "caption": v.caption, "line": v.said(),
                   "portrait": asset_url(art_files.portrait_path(None, v.portrait)) if v.portrait else None}}
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
                    "line": i18n.t("arena_session.must_come_to_pit_to", name=champ.name, defense_deadline=arena.defense_deadline(self.guild))}}

    def _bout(self, i, b):
        return {"i": i, "name": b.name, "kind": _kind(b), "blurb": i18n.t(f"arena_session.blurb.{_kind(b)}"),
                "entry": b.entry, "entry_text": fmt_money(b.entry), "purse": b.purse, "purse_text": fmt_money(b.purse),
                "foes": b.enemies + (len(arena.RIBBIT_SLUGS) if b.boss else 0), "cap": b.player_cap,
                "levels": arena.bout_level_range(b, self.picked), "max_level": arena.bout_max_combat_level(b),
                "picked": i == self.at}

    def _member(self, u):
        lvl = f"C{u.combat_level}" + (f"/W{u.work_level}" if u.work_xp or u.work_level else "") + f"/R{u.racial_level}"
        n, faces = u.weapon["damage"]
        flags = []
        if u.incapacitated:
            flags.append({"text": i18n.t("arena_session.collapsed_from_hunger"), "tone": "bad"})
        elif u.hunger_level:
            flags.append({"text": i18n.t("arena_session.hunger", hunger_label=u.hunger_label), "tone": "bad" if u.hunger_level >= 2 else "warn"})
        if u.sick:
            flags.append({"text": "Sick", "tone": "bad"})
        if u.combat_level > arena.bout_max_combat_level(self.offer):
            flags.append({"text": i18n.t("arena_session.no_combat_xp_foes_stop", bout_max_combat_level=arena.bout_max_combat_level(self.offer)),
                          "tone": "warn"})
        if u.pending_picks:
            flags.append({"text": i18n.t("arena_session.talent_pick_ready"), "tone": "good"})
        return {"uid": u.uid, "name": u.name, "race": u.race_label,                 "portrait": _portrait(u), "hp": [max(0, u.hp), u.hp_max], "ac": u.ac, "md": u.mental_defense,
                "speed": u.speed, "weapon": u.weapon.name, "dmg": f"{n}d{faces}",
                "money": u.money, "money_text": fmt_money(u.money), "level": lvl, "flags": flags,
                "unfit": u.incapacitated, "picked": u in self.picked,
                "title": bool(getattr(u, "arena_title", False))}

    def _recruit(self):
        r = _recruit_card(self.offered)
        if self.offered == "adelio":
            faces = [arena.load_champion()]
        else:
            faces = arena.load_ribbit_brothers()
        return {**r, "who": self.offered,
                "faces": [{"name": u.name, "portrait": _portrait(u), "race": u.race_label} for u in faces]}
