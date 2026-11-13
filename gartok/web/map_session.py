"""The campaign map in the browser: the bands, the known world, what the picked band can do where it
stands, and the clock. Orders and the clock run as `MapScreen` and `App` run them; what the map
shows of a band and its node is `map_view.MapView`, which pygame's map reads too.
"""

import dataclasses
from itertools import pairwise
from typing import ClassVar

from .. import (
    arena,
    art_files,
    campaign,
    clock,
    economy,
    forced,
    gather,
    hints,
    i18n,
    missions,
    node_functions,
    orders,
    persist,
    recruit,
    rest,
    routines,
    settings,
    stints,
    vocations,
    world,
)
from ..constants import fmt_money
from ..group import CAUTIOUS, NORMAL
from ..guild_log import KINDS as LOG_KINDS
from ..map_view import ADVANCE_HOURS, STANCE_NOTES, MapView, node_icon, position
from ..scenario import scenario_for
from .session import Session, asset_url
from .swift import Look

LOG_TAIL = 200                  # lines of the log the map carries; the search reads the whole of it

REST_ROWS = (("rest:1", "map_session.rest.hour_1"), ("rest:8", "map_session.rest.hours_8"), ("rest:full", "map_session.rest.full"))


def _icon(slug):
    return f"{slug[0]}/{slug[1]}" if slug else None


def _portrait(u):
    return asset_url(art_files.portrait_path(u.race["name"], getattr(u, "portrait_id", None)))


def _when(guild, hours):
    """`(day, "HH:MM")` `hours` from now."""
    at = clock.Clock(guild.clock.seconds + round(hours * clock.SECONDS_PER_HOUR))
    return at.day, f"{at.hour_of_day:02d}:{at.minute_of_hour:02d}"


def _plural(n, word):
    """`n` of a counted thing (`count.<word>.one` / `.other` in the catalog)."""
    return i18n.count(word.replace(" ", "_"), n)


class MapSession(MapView, Session):
    screen = "map"
    GET: ClassVar[dict] = {
        "state": lambda s, q: s.state(),
        "preview": lambda s, q: s.preview(q["gid"], q["node"]),
        "log": lambda s, q: s.log_search(q.get("q", ""), q.get("kind"), q.get("band")),
    }
    POST: ClassVar[dict] = {
        "travel": lambda s, b: s.travel(b["gid"], b["node"], bool(b.get("leave"))),
        "act": lambda s, b: s.act(b["gid"], b["key"]),
        "split": lambda s, b: s.split(b["gid"], b["uids"]),
        "merge": lambda s, b: s.merge(b["gid"], b["other"]),
        "advance": lambda s, b: s.advance_world(),
        "log_full": lambda s, b: s.log_full(b.get("choice")),
        "go_on": lambda s, b: s.go_on(),
        "title": lambda s, b: s.to_title(),
        "save_as": lambda s, b: s.save_as(b.get("name", "")),
        "wiki": lambda s, b: s.aside("wiki"),
        "settings": lambda s, b: s.aside("settings"),
        "quit": lambda s, b: s.quit(),
    }

    def __init__(self, guild, world_id=None):
        self.guild = guild
        self.world_id = world_id
        self.notices = []
        self.pending = []
        self.level_ups = []                      # aftermath.LevelUp the clock brought, each its own page
        self.wiped = False
        self.look = Look()
        self.turn = None                         # the hand-over card up: {"gid", "action", "danger", "go"}
        self.hunts = {}                          # gid -> the HuntSession whose stretch is out on the clock
        self._restore_hunts()
        self.seen = None                         # the band last in view
        self._wait_out_the_sentence()
        due = self._pending_event              # a save taken with a fight due opens on that band
        self.focus = due[0].gid if due else None

    def _restore_hunts(self):
        """A save taken mid-stretch: each `hunting` order carries its hunt, so its screen opens when it is up."""
        from .hunt_session import HuntSession
        for g in self.guild.groups:
            if g.order is not None and g.order.kind == "hunting":
                if g.order.state is None:        # a save from before the hunt rode in its order
                    g.order = None
                else:
                    self.hunts[g.gid] = HuntSession.restore(self, g)
            elif g.due_hunt is not None:         # saved with the stretch up, its screen not yet open
                self.hunts[g.gid] = HuntSession.restore(self, g, g.due_hunt)
                self.pending.append((g, g.due_hunt))

    def land_due(self):
        """After a load: open the screen a stretch that came due before the save was waiting for."""
        return self._land() if self.pending else None

    # ------------------------------------------------------------------ #
    # what pygame's map reads call                                        #
    # ------------------------------------------------------------------ #
    def _group_blocked(self, g):
        return g.fight_due

    @property
    def _pending_event(self):
        g = next((g for g in self.guild.groups if g.fight_due and not g.empty), None)
        if g is None:
            return None
        g = forced.fight_lead(self.guild, g)
        return g, g.pending

    def _is_idle(self, g):
        return not g.busy and not g.empty and not g.fight_due

    def _group(self, gid):
        g = next((g for g in self.guild.groups if g.gid == gid), None)
        if g is None:
            raise ValueError(i18n.t("map_session.no_such_band"))
        self.seen = g.gid
        return g

    def say(self, lines, kind, group=None):
        """Put `lines` in the guild's log, where they were born, and in `notices` for the screen asking."""
        lines = [lines] if isinstance(lines, str) else list(lines)
        self.guild.log.record(lines, self.guild.clock.seconds, kind, group.display_name if group else None)
        self.notices += lines

    def _free(self, gid):
        """The band, when it may take an order now."""
        g = self._group(gid)
        if g.fight_due:
            raise ValueError(i18n.t("map_session.has_fight_to_face_first", display_name=g.display_name))
        if g.busy:
            raise ValueError(i18n.t("map_session.is_busy", display_name=g.display_name))
        return g

    # ------------------------------------------------------------------ #
    # the screen                                                          #
    # ------------------------------------------------------------------ #
    def state(self):
        g = self.guild
        self.notices = []                        # what the screens asked for has been said; the log keeps it
        focus, self.focus = self.focus, None
        heard, g.heard = sorted(g.heard), set()
        known = {n.id for n in world.known(g)}
        return {
            "meta": self._meta(),
            "alerts": self._alerts(),
            "ledger": [(i18n.lab("Members"), str(len(g))), (i18n.lab("Rations"), str(g.rations)),
                       (i18n.lab("Purse"), fmt_money(g.money)), (i18n.lab("Reputation"), str(g.arena_reputation))],
            "nodes": [self._node(n) for n in world.NODES if n.id in known],
            "edges": [[a, b, d] for a, b, d in world.EDGES if a in known and b in known],
            "groups": [self._band(gr) for gr in g.groups if not gr.empty],
            "log": self._log(),
            "cta": self._cta(),
            "focus": focus,
            "turn": self._turn_card(),
            "wiped": self.wiped,
            "sounds": heard,
        }

    def _turn_card(self):
        """The hand-over card: whose turn it is, when the clock moved the person off the band in view."""
        t = self.turn
        group = next((g for g in self.guild.groups if t and g.gid == t["gid"]), None)
        if group is None:
            return None
        live = [g for g in self.guild.groups if not g.empty]
        return {"band": i18n.t("map_session.band_of_its_turn", index=live.index(group) + 1, total=len(live)), "name": group.display_name,
                "node": world.node(group.node).name, "action": t["action"], "danger": t["danger"],
                "members": [u.name for u in group.members]}

    def _hand_over(self, group, action, danger=False, go=None):
        """Put the hand-over card up for `group` when the clock moved the person off the band in view and
        the guild keeps more than one; True when it is up, `go` waiting for GO ON."""
        moved = self.seen is not None and group.gid != self.seen
        self.seen = group.gid
        if not moved or sum(1 for g in self.guild.groups if not g.empty) < 2:
            return False
        self.turn = {"gid": group.gid, "action": action, "danger": danger, "go": go}
        return True

    def go_on(self):
        """GO ON on the hand-over card: on to the screen the band's order was waiting to open."""
        t, self.turn = self.turn, None
        if t is None:
            raise ValueError(i18n.t("map_session.no_band_is_waiting"))
        if t["go"] is not None:
            return t["go"]()
        return {"screen": self.screen, **self.state()}

    @staticmethod
    def _activity_label(order):
        """The card's headline for an order about to open: the forced event's, the arena's, the node
        button's, or the kind itself."""
        if order.kind in forced.EVENTS:
            return forced.EVENTS[order.kind].label or order.kind.upper()
        if order.kind == "arena":
            return i18n.t("map_session.enter_arena")
        return next((f.label for f in node_functions.FUNCTIONS.values()
                     if f.order_kind == order.kind and f.label), order.kind.replace("_", " ").upper())

    def _meta(self):
        g, c = self.guild, self.guild.clock
        h = c.hour_of_day
        part = ("night" if not c.is_daylight else "morning" if h < 12 else "afternoon" if h < 15 else "evening")
        turn = clock.NIGHT_START if c.is_daylight else clock.DAY_START
        voc = vocations.VOCATIONS.get(g.vocation)
        bands = len([gr for gr in g.groups if not gr.empty])
        pending = sum(1 for u in g.roster if u.pending_picks)
        return {"world": self.world_id, "name": g.name or i18n.t("map_session.guild"), "day": c.day,
                "time": f"{h:02d}:{c.minute_of_hour:02d}", "daylight": c.is_daylight, "hour": h + c.minute_of_hour / 60,
                "part": part, "turn": i18n.t("map_session.till_light" if c.is_daylight else "map_session.till_dark", turn=turn),
                "subtitle": i18n.t("map_session.in", who=voc.name if voc else i18n.t("map_session.a_guild"), members=_plural(len(g), 'member'), bands=_plural(bands, 'band')),
                "banner": list(g.banner_color) if g.banner_color else None,
                "emblem": _icon(next(((c, s) for c, s, _ in art_files.BANNER_ICONS if s == g.banner_icon), None)),
                "level_ups": pending, "slots_free": g.free_slots}

    def _alerts(self):
        out = []
        food = self.guild.food_alert()
        if food:
            out.append({"title": food[2], "text": food[1], "icon": "action/eating", "tone": "bad"})
        if arena.defense_due(self.guild):
            out.append({"title": i18n.t("map_session.title_defense"), "icon": "body/sword-tie", "tone": "bad",
                        "text": i18n.t("map_session.must_defend_champion_of_pit", name=arena.champion_of(self.guild).name, defense_deadline=arena.defense_deadline(self.guild))})
        hungry = self.guild.hungry
        if hungry and not food:
            out.append({"title": i18n.t("map_session.hungry", len=len(hungry)), "icon": "action/eating", "tone": "warn",
                        "text": ", ".join(u.name for u in hungry)})
        return out

    def _node(self, n):
        return {"id": n.id, "name": n.name, "x": n.pos[0], "y": n.pos[1], "kind": n.kind,
                "icon": _icon(node_icon(n.id)), "blurb": n.blurb, "jurisdiction": n.jurisdiction,
                "alert": self._node_alert(n), "ethereal": world.is_ethereal(n.id)}

    def _node_alert(self, n):
        return (any(n.has(fn) and recruit.has_new_faces(self.guild, key) for fn, key in recruit.SEEN_FUNCTIONS.items())
                or bool(missions.offers_at(self.guild, n.id)))

    def _chip(self, g):
        if g.fight_due:
            return i18n.t("map_session.ambushed") if g.pending.kind in ("ambush", "fortress_ambush") else i18n.t("map_session.fight_due"), "bad"
        o = g.order
        if o is None or o.kind == "idle":
            return (i18n.t("map_session.routine_stopped"), "bad") if g.routine is not None and g.routine.paused else (i18n.t("map_session.no_orders"), "idle")
        label = (stints.doing(o) if stints.is_stint(o) else "gather" if o.kind == "work" and o.gather
                 else "search" if o.task in campaign.SEARCHES else o.task if o.kind == "solo"
                 else "travelling" if o.kind == "travel" else o.kind)
        return i18n.lab(label.replace("_", " ")), "go" if o.kind == "travel" else "busy"

    def _band(self, g):
        chip, tone = self._chip(g)
        at = position(g)
        kit = [_plural(len(g.members), "soul")]
        kit += [f"a {w.kind.lower()}" for w in g.wagons] + [f"a {a.species.lower()}" for a in g.herd]
        return {
            "gid": g.gid, "name": g.display_name, "lead": g.leader.name if g.leader else "",
            "node": g.node, "at": at if isinstance(at, str) else list(at),
            "chip": chip, "tone": tone, "detail": self._order_status(g),
            "kit": ", ".join(kit), "rations": g.rations, "rotten": g.rotten_rations, "money": fmt_money(g.money),
            "idle": self._is_idle(g), "blocked": g.fight_due, "busy": g.busy,
            "pace": world.hours(1, g.speed) * self._pace(g),
            "members": [self._member(u, g) for u in g.members],
            "trip": self._trip(g),
            "split": [{"uid": u.uid, "name": u.name, "sub": i18n.t("map_session.hp", race=u.race_label, hp=u.hp, hp_max=u.hp_max),
                       "portrait": _portrait(u)} for u in g.members]
                     + [{"uid": w.uid, "name": w.kind, "sub": "wagon"} for w in g.wagons]
                     + [{"uid": a.uid, "name": a.species, "sub": "animal"} for a in g.herd],
            "can_split": "" if self.guild.free_slots else i18n.t("map_session.no_free_band_slot"),
            "mates": [{"gid": gid, "name": name} for gid, name in self._mates_for(g)],
            "inspector": self._inspector(g),
        }

    def _member(self, u, g):
        return {"uid": u.uid, "name": u.name, "portrait": _portrait(u), "lead": u is g.leader,
                "hp": u.hp, "hp_max": u.hp_max, "hungry": u.hunger_level > 0, "sick": bool(u.sick),
                "poisoned": bool(u.poisoned), "encumbered": bool(u.encumbered),
                "sub": i18n.t("map_session.lvl", race=u.race_label, racial_level=u.racial_level)}

    def _pace(self, g):
        return vocations.travel_mult(self.guild, g)

    def _legs(self, g, path):
        """Hours of each leg along `path` (node ids, the start first) at the band's pace."""
        return [world.hours(next(w for v, w in world.neighbors(a) if v == b), g.speed) * self._pace(g)
                for a, b in pairwise(path)]

    def _trip(self, g):
        """A travelling band's way: each stop ahead with when it gets there, and how far along the
        current leg it is."""
        o = g.order if g.order is not None and g.order.kind == "travel" else g.pending
        if o is None or not o.dest or o.dest == g.node:
            return None
        ahead = [o.dest, *o.path]
        hours = [o.remaining + o.owed, *self._legs(g, ahead)]
        stops, t = [], 0.0
        for node_id, h in zip(ahead, hours):
            t += h
            day, at = _when(self.guild, t)
            stops.append({"node": node_id, "name": world.node(node_id).name, "day": day, "at": at, "hours": round(t, 1)})
        share = 0.0 if o.eta <= 0 else max(0.0, min(1.0, (o.eta - o.remaining - o.owed) / o.eta))
        return {"from": g.node, "from_name": world.node(g.node).name, "share": share, "stops": stops}

    # ------------------------------------------------------------------ #
    # the inspector                                                       #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _block(b):
        if b["type"] == "button":
            return {"t": "button", "key": b["key"], "label": b["label"], "sub": b.get("sub"),
                    "primary": bool(b.get("primary")), "danger": bool(b.get("danger")),
                    "enabled": b.get("enabled", True)}
        if b["type"] == "section":
            return {"t": "section", "label": b["label"]}
        return {"t": "note", "text": b["text"], "tone": b.get("tone", "faint")}

    def _inspector(self, g):
        here = world.node(g.node)
        place = {"id": here.id, "name": here.name, "blurb": here.blurb, "icon": _icon(node_icon(here.id)),
                 "stats": self._stats(g, here)}
        if g.fight_due:
            n = len(g.pending.pack)
            what = forced.EVENTS[g.pending.kind].label or g.pending.kind
            blocks = [{"t": "note", "tone": "bad", "text": what.capitalize() + "!"},
                      {"t": "note", "tone": "faint",
                       "text": i18n.t("map_session.stand_in_way_there_is", foes=_plural(n, 'foe'))}]
            return {"place": place, "blocks": blocks, "camp": None}
        blocks = [self._block(b) for b in self._inspector_content(g, here)
                  if b["type"] != "stats" and not (b["type"] == "text" and b["text"].startswith("Busy: "))]
        return {"place": place, "blocks": blocks, "camp": None if g.busy else self._camp(g)}

    def _work_line(self, g, here):
        return {"type": "stats"}             # the place card's numbers say it (`_stats`)

    def _stats(self, g, here):
        """A work node's numbers: what a 16 h shift pays the band, the licence, the hands."""
        if not here.has("work"):
            return []
        day = sum(economy.work_pay(here.id, 16, economy.work_level(u, here.id)) for u in g.members)
        out = [{"value": fmt_money(day), "label": i18n.lab("A 16 h shift")}]
        if gather.can_gather(here.id):
            held = self.guild.has_licence(here.id)
            out.append({"value": i18n.t("map_session.licence_held") if held else i18n.t("map_session.no_licence"), "label": i18n.t("map_session.gathering"), "no": not held})
            hands = len(gather.gatherers(g.members, here.id))
            out.append({"value": f"{hands}/{len(g.members)}", "label": i18n.t("map_session.own", tool=i18n.name("item", gather.tool(here.id))),
                        "no": hands < len(g.members)})
        out.append({"value": str(len(g.members)), "label": i18n.lab("Workers")})
        return out

    def _camp(self, g):
        now = self.guild.clock.seconds
        if g.has_campfire(now):
            fire = {"label": i18n.lab("Campfire"), "sub": i18n.t("map_session.burning_h_left", campfire_hours_left=g.campfire_hours_left(now)), "enabled": True}
        else:
            missing = []
            if not any(u.has_item(economy.FIELD_CAMPFIRE_TOOL) for u in (*g.members, *g.stores)):
                missing.append(i18n.name("item", economy.FIELD_CAMPFIRE_TOOL))
            if sum(u.unlocked_of(economy.FIELD_CAMPFIRE_LUMBER) for u in g.members) < 1:
                missing.append(f"{economy.FIELD_CAMPFIRE_UNITS} {i18n.name('item', economy.FIELD_CAMPFIRE_LUMBER)}")
            if sum(u.unlocked_of(economy.FIELD_CAMPFIRE_COAL) for u in g.members) < 1:
                missing.append(i18n.name("item", economy.FIELD_CAMPFIRE_COAL))
            fire = {"label": i18n.lab("Campfire"), "enabled": not missing,
                    "sub": i18n.t("map_session.needs", join=', '.join(missing)) if missing else i18n.t("map_session.light_it_and_cook_burns")}
        hurt = [u for u in g.members if u.hp < u.hp_max or u.sick or u.poisoned]
        urgent = self._rest_urgent(g)
        rows = []
        for (key, label), (_, _, plan) in zip(REST_ROWS, self._rest_plans(g)):
            if not plan.available:
                rows.append({"key": key, "label": i18n.t(label), "sub": plan.reason, "enabled": False})
                continue
            meals = plan.meals * len(g.members)
            sub = i18n.t("map_session.no_meal") if meals == 0 else _plural(meals, "meal")
            if key == "rest:full":
                sub = f"{rest.format_hours(plan.hours)} · {sub}"
            rows.append({"key": key, "label": i18n.t("map_session.to_floor") if plan.capped else i18n.t(label), "sub": sub,
                         "enabled": True, "rec": key == "rest:full" and urgent,
                         "tip": (i18n.t("map_session.rations_run_out_short_of", days=_plural(plan.short_days, 'day'))
                                 if plan.capped else None)})
        return {
            "fire": fire,
            "stance": [{"key": key, "label": i18n.t(f"map_session.stance.{key}"), "tip": i18n.t(STANCE_NOTES[key]), "on": g.stance == key}
                       for key in ((NORMAL), (CAUTIOUS))],
            "rest": rows,
            "starving": g.rations == 0,
            "hurt": ([i18n.t("map_session.is_hurt", name=hurt[0].name)] if len(hurt) == 1 else
                     [i18n.t("map_session.are_hurt_sick_or_poisoned", len=len(hurt))] if hurt else []),
        }

    # ------------------------------------------------------------------ #
    # the clock's row and the seal                                         #
    # ------------------------------------------------------------------ #
    def _hours(self):
        """What comes next, by the clock: each band's order ending, and the turn of light."""
        rows = []
        for g in self.guild.groups:
            o = g.order
            if g.empty or o is None or o.kind in ("idle", "garrison"):
                continue
            t = o.remaining + o.owed
            what = (i18n.t("map_session.reaches", display_name=g.display_name, name=world.node(o.dest).name) if o.kind == "travel"
                    else i18n.t("map_session.ends", display_name=g.display_name, split=self._order_status(g).split(' (')[0]))
            rows.append((t, what))
        c = self.guild.clock
        now = c.hour_of_day + c.minute_of_hour / 60
        turn = clock.NIGHT_START if c.is_daylight else clock.DAY_START
        rows.append(((turn - now) % 24, i18n.t("map_session.dark_falls") if c.is_daylight else i18n.t("map_session.dawn")))
        rows.sort()
        out = [{"at": _when(self.guild, 0)[1], "day": c.day, "text": self._now_line(), "now": True}]
        for t, text in rows[:4]:
            day, at = _when(self.guild, t)
            out.append({"at": at, "day": day, "text": text, "now": False})
        return out

    def _log(self):
        """The log panel: the last lines, the turn of the clock and what is due next."""
        log = self.guild.log
        rows = self._hours()
        return {"rows": log.tail(LOG_TAIL), "total": len(log.entries), "limit": log.limit,
                "near": log.near_full, "full": log.full, "prompt": log.prompt,
                "next_limit": settings.next_choice("log_lines"),
                "now": {"day": rows[0]["day"], "at": rows[0]["at"]}, "ahead": rows[1:],
                "kinds": list(LOG_KINDS), "bands": [g.display_name for g in self.guild.groups if not g.empty]}

    def log_search(self, q, kind, band):
        rows, found = self.guild.log.search(q, kind, band)
        return {"rows": rows, "found": found, "total": len(self.guild.log.entries)}

    def log_full(self, choice):
        """The answer to the full-log question, asked once the clock has stopped."""
        log, g = self.guild.log, self.guild
        if choice == "export":
            log.export_and_trim(g.name, g.clock.day)
        elif choice == "discard":
            log.discard_oldest()
        elif choice == "raise":
            if settings.next_choice("log_lines") is None:
                raise ValueError(i18n.t("map_session.log_is_already_at_its"))
            settings.step_up("log_lines")
        elif choice == "later":
            log.muted = True
        else:
            raise ValueError(i18n.t("map_session.no_such_answer", choice=choice))
        self._save()
        return self.state()

    def _now_line(self):
        idle = [g for g in self.guild.groups if self._is_idle(g)]
        if self._pending_event:
            return i18n.t("map_session.must_face_fight", display_name=self._pending_event[0].display_name)
        if idle:
            return i18n.t("map_session.waits_for_orders", display_name=idle[0].display_name) if len(idle) == 1 else i18n.t("map_session.bands_wait_for_orders", len=len(idle))
        return i18n.t("map_session.every_band_is_about_its")

    def _swift_look(self, group, order):
        node = world.node(group.node)
        return self.look.of((group.gid, id(order)), forced.fight_squad(self.guild, group, order), order.pack,
                            lambda: scenario_for(node),
                            self.guild.clock.is_daylight, True)

    def _cta(self):
        due = self._pending_event
        if due is not None:
            return {"key": "resolve_event", "label": i18n.lab("Fight"), "sub": i18n.t("map_session.foes", len=len(due[1].pack)), "danger": True,
                    "enabled": True, "gid": due[0].gid, "swift": self._swift_look(*due),
                    "text": i18n.t("map_session.is_stopped_nothing_moves_on", display_name=due[0].display_name)}
        idle = [g for g in self.guild.groups if self._is_idle(g)]
        if not idle and self._everyone_garrisoned():
            return {"key": "advance_world", "label": i18n.t("map_session.advance_h", advance_hours=ADVANCE_HOURS), "sub": i18n.t("map_session.whole_world"),
                    "danger": False, "enabled": True, "text": i18n.t("map_session.every_band_holds_post_let")}
        return {"key": "cycle_idle", "label": i18n.t("map_session.next_band"), "danger": False, "enabled": len(idle) > 1,
                "sub": i18n.t("map_session.waiting", len=len(idle)) if len(idle) > 1 else i18n.t("map_session.none_idle"), "idle": [g.gid for g in idle],
                "text": (i18n.t("map_session.clock_waits_on", display_name=idle[0].display_name)
                         if len(idle) == 1 else i18n.t("map_session.bands_wait_seal_steps_to", len=len(idle))
                         if idle else i18n.t("map_session.clock_runs"))}

    # ------------------------------------------------------------------ #
    # what the person does                                                #
    # ------------------------------------------------------------------ #
    def preview(self, gid, node_id):
        """The slip over a place: the walk there, its hours and when the band gets in."""
        g = self._group(gid)
        n = world.node(node_id)
        out = {"node": node_id, "name": n.name, "blurb": n.blurb, "path": [], "hours": 0.0}
        if node_id == g.node:
            out["why"] = i18n.t("map_session.stands_here", display_name=g.display_name)
            return out
        path, dist = world.route(g.node, node_id)
        if dist == float("inf"):
            out["why"] = i18n.t("map_session.no_road_leads_there")
            return out
        hours = sum(self._legs(g, path))
        day, at = _when(self.guild, hours)
        out.update(path=path, via=[world.node(p).name for p in path[1:-1]], hours=round(hours, 1),
                   day=day, at=at, food=self._food_for(g, day - self.guild.clock.day))
        if g.fight_due:
            out["why"] = i18n.t("map_session.fight_must_be_faced_first")
        elif g.busy:
            out["why"] = i18n.t("map_session.is_busy", display_name=g.display_name)
        elif any(w.broken for w in g.wagons):
            out["leave"] = self._left_behind(g)
        return out

    @staticmethod
    def _food_for(g, days):
        need = g.rations_for(days)
        return {"days": days, "need": need, "have": g.rations, "short": g.rations < need}

    def _left_behind(self, g):
        """What setting out with a broken wagon costs, told before the yes: each wagon and the
        cargo that goes with it, and the animals that walk on with the band."""
        wagons = [{"name": w.kind, "items": sum(q for _, q in w.stash.items),
                   "kg": round(w.stash.load, 1), "cargo": [f"{q} {n}" if q > 1 else n for n, q in w.stash.items]}
                  for w in g.wagons if w.broken]
        pulling = {a.uid for w in g.wagons if not w.broken for a in w.draft}
        walk = [a.name for a in g.herd if a.uid not in pulling]
        return {"wagons": wagons, "animals": walk}

    def travel(self, gid, node_id, leave=False):
        g = self._free(gid)
        if node_id == g.node:
            raise ValueError(i18n.t("map_session.is_already_there", display_name=g.display_name))
        if world.route(g.node, node_id)[1] == float("inf"):
            raise ValueError(i18n.t("map_session.no_road_leads_to", name=world.node(node_id).name))
        broken = [w for w in g.wagons if w.broken]
        if broken and not leave:
            raise ValueError(i18n.t("map_session.broken_wagon_cannot_move_mend"))
        for w in broken:
            self.guild.abandon_wagon(g, w)
            self.say(i18n.t("map_session.leaves_its_broken_behind", display_name=g.display_name, lower=w.ref(lower=True)), "travel", g)
        g.order = orders.travel(g, node_id, self._pace(g))
        self.focus = g.gid
        return self._after_order()

    def act(self, gid, key):
        g = self._group(gid)
        if key == "resolve_event":
            if not g.fight_due:
                raise ValueError(i18n.t("map_session.has_no_fight_to_face", display_name=g.display_name))
            from .campaign_fight import forced_fight
            from .dialogue_session import forced_talk
            return self._talk(forced_talk(self, g)) or forced_fight(self, g, g.pending)
        if key == "swift_win":
            if not g.fight_due:
                raise ValueError(i18n.t("map_session.has_no_fight_to_face", display_name=g.display_name))
            self._swift_look(g, g.pending)
            if self.look.result is None:
                raise ValueError(i18n.t("map_session.this_fight_is_not_clean"))
            from .campaign_fight import forced_fight
            result = self.look.result
            self.look.clear()
            return forced_fight(self, g, g.pending, swift=result)
        if key == "guild":
            return self._sheet("members", g.gid)
        if g.fight_due:
            raise ValueError(i18n.t("map_session.has_fight_to_face_first", display_name=g.display_name))
        if key in ("stop_rest", "recall_garrison"):
            g.order = orders.idle()
        elif key == "cancel_trip":
            g.order = dataclasses.replace(g.order, path=())
        elif key in (NORMAL, CAUTIOUS):
            g.stance = key
        elif key == "visit_tavern":
            return self._enter(g, orders.interactive("recruit", hours=0))
        elif key == "visit_claim":
            return self._enter(g, orders.interactive("claim", hours=0))
        elif g.busy:
            raise ValueError(i18n.t("map_session.is_busy", display_name=g.display_name))
        elif key == "continue_routine":
            if g.routine is None or not g.routine.paused:
                raise ValueError(i18n.t("map_session.has_no_stopped_routine", display_name=g.display_name))
            self.say(routines.resume(self.guild, g), "guild", g)
        elif key.startswith("rest:"):
            which = key.split(":")[1]
            plan = rest.until_full(self.guild, g) if which == "full" else rest.fixed(self.guild, float(which))
            if not plan.available:
                raise ValueError(plan.reason)
            self.say(self.guild.eat_now_pass(g.members), "food", g)
            g.order = orders.rest(plan.hours)
        elif key in campaign.SEARCHES:
            g.order = orders.search(key, campaign.SEARCHES[key][0])
        elif key == "wf_put_out":
            g.order = orders.put_out(self.guild, g)
        elif key == "wf_talk":
            from .dialogue_session import wildfire_talk
            return self._talk(wildfire_talk(self, g))
        elif key == "manage_group":
            return self._sheet("bands", g.gid)
        elif key == "campfire_cook":
            now = self.guild.clock.seconds
            if not g.has_campfire(now):
                if not g.light_campfire(now):
                    raise ValueError(i18n.t("map_session.band_cannot_light_campfire"))
                self.say(i18n.t("map_session.campfire_lit_burns_for_hours", display_name=g.display_name), "rest", g)
                self._save()
            from .hub_session import HubSession
            self.game.open(HubSession(self, g, orders.Order("campfire")))
            return {"screen": HubSession.screen}
        elif key in orders.INTERACTIVE_KINDS:
            return self._enter(g, orders.interactive(key, hours=0))
        else:
            raise ValueError(i18n.t("map_session.no_such_order", what=key))
        self.focus = g.gid
        return self._after_order()

    def split(self, gid, uids):
        g = self._group(gid)
        if g.fight_due:
            raise ValueError(i18n.t("map_session.has_fight_to_face_first", display_name=g.display_name))
        picks = set(uids)
        new = self.guild.split_group(g, [u for u in g.members if u.uid in picks],
                                     wagons=[w for w in g.wagons if w.uid in picks],
                                     herd=[a for a in g.herd if a.uid in picks])
        self.focus = new.gid
        self._save()
        return self.state()

    def merge(self, gid, other):
        a, b = self._group(gid), self._group(other)
        if a.fight_due or b.fight_due:
            raise ValueError(i18n.t("map_session.band_with_fight_to_face"))
        self.guild.merge_groups(a, b)
        self.focus = a.gid
        self._save()
        return self.state()

    def advance_world(self):
        if self._pending_event is not None:
            raise ValueError(i18n.t("map_session.fight_must_be_faced_first"))
        if not self._everyone_garrisoned():
            raise ValueError(i18n.t("map_session.only_when_every_band_holds"))
        self._advance(ADVANCE_HOURS)
        return self._land()

    # ------------------------------------------------------------------ #
    # the clock, as `App._advance` runs it                                #
    # ------------------------------------------------------------------ #
    def _after_order(self):
        if self.guild.can_auto_advance:
            self._advance()
        return self._land()

    def _advance(self, dt=None):
        """Run the clock to the next thing that needs the person: a band gone idle, a screen due,
        or (with `dt`) one jump of that many hours. -> `(idle gids, the dead)` of the last run."""
        dead = []
        while True:
            busy_before = {g.gid for g in self.guild.groups if g.busy}
            result = campaign.advance(self.guild, dt=dt)
            self.notices += result.events
            self.notices += [i18n.t("map_session.died", name=u.name) for u in result.casualties]
            dead += result.casualties
            self.level_ups += result.level_ups
            if result.wiped:
                self.wiped = True
                return set(), dead
            self.pending += result.pending
            idle = {g.gid for g in self.guild.groups if g.gid in busy_before and not g.busy}
            if dt is not None or result.pending:
                return idle, dead
            if idle or not any(g.busy and g.order.kind != "garrison" for g in self.guild.groups):
                if idle:
                    self.focus = next(iter(idle))
                return idle, dead

    def spend(self, group, order=None):
        """`group` takes `order` (or the one it was just given) on a screen off the map, and the clock
        runs as the map's would, every band's order with it. -> `(lines, None)` when the order's end is
        all that stopped the clock: the screen stays up with what it said. Else `(None, answer)`: another
        band idle or done, a screen or a fight due, a death, and the map takes over, the order still
        running there."""
        if order is not None:
            group.order = order
        self.focus = group.gid
        if self.guild.needs_orders:
            return None, self.back()
        before = len(self.notices)
        idle, dead = self._advance()
        running = group.busy and group.order.kind != "garrison"      # a shift that ended on its post is done
        if self.wiped or running or self.pending or dead or idle - {group.gid}:
            return None, self.back()
        lines = self.notices[before:]
        del self.notices[before:]
        self._save()
        return lines, None

    def _wait_out_the_sentence(self):
        """Every band went to the cells: no map to show, so the days pass (the daily upkeep runs
        `justice.release_due`) until the nearest release stands a band back up."""
        while not self.guild.groups and self.guild.jailed:
            self.notices += campaign.advance(self.guild, dt=24).events

    def _land(self):
        """Open the next screen the clock left due, or land on the map; the answer is the screen open."""
        self._wait_out_the_sentence()
        if self.wiped:
            return {"screen": self.screen, **self.state()}
        if self.level_ups:
            return self.open_level_ups(self.back)
        while self.pending:
            group, order = self.pending.pop(0)
            if group.empty or group not in self.guild.groups:
                continue
            if order.kind in forced.EVENTS:
                self.focus = group.gid
                continue
            self._save()
            if self._hand_over(group, self._activity_label(order), go=lambda g=group, o=order: self._enter(g, o)):
                return {"screen": self.screen, **self.state()}
            return self._enter(group, order)
        self.say(arena.sync(self.guild), "fight")
        if self.guild.can_auto_advance:
            self._advance()
            return self._land()
        self._save()
        due = self._pending_event
        band = next((g for g in self.guild.groups if g.gid == self.focus), None)
        if band is not None and self.turn is None:
            ambushed = due is not None and due[0] is band
            self._hand_over(band, i18n.t("map_session.ambushed_fight_when_ready") if ambushed else i18n.t("map_session.awaits_orders"), danger=ambushed)
        self._save()
        return {"screen": self.screen, **self.state()}

    def open_level_ups(self, then):
        """The level-ups the clock brought, a page each as after a fight, then `then`."""
        from .report_session import LevelUps
        self._save()
        self.game.open(LevelUps(self, self.level_ups, then))
        self.level_ups = []
        return {"screen": LevelUps.screen}

    def _enter(self, group, order):
        """The screen `order` plays: the arena, the hunt, a search's find, an errand's fight, else its hub."""
        from .hub_session import HUB_KINDS, HubSession
        if order.kind == "hunting":
            return self.hunts[group.gid].arrive()
        if order.kind == "arena":
            from .arena_session import open_arena
            return open_arena(self, group)
        if order.kind in ("hunt", "ox_hunt"):
            from .hunt_session import open_hunt
            return open_hunt(self, group, "ox" if order.kind == "ox_hunt" else "meat")
        if order.kind in ("ancient_ruins", "serpents_nest", "dragon_lair"):
            from .campaign_fight import delve
            return delve(self, group, order.kind)
        if order.kind == "demon_lair":
            from .campaign_fight import demon_lair
            return demon_lair(self, group)
        if order.kind == "cult_ritual":
            from .campaign_fight import cult_ritual
            return cult_ritual(self, group)
        if order.kind in ("skirmish", "camp_fight", "ogre_fight"):
            from .campaign_fight import errand
            return errand(self, group, order.kind)
        if order.kind not in HUB_KINDS:
            raise ValueError(i18n.t("map_session.no_screen_plays", kind=order.kind))
        self.game.open(HubSession(self, group, order))
        return {"screen": HubSession.screen}

    def _sheet(self, tab, gid):
        from .guild_session import GuildSession
        self.game.open(GuildSession(self, tab, gid))
        return {"screen": GuildSession.screen}

    def _talk(self, session):
        """Open the talk before a fight, or None when there is none to have."""
        if session is None:
            return None
        self.game.open(session)
        return {"screen": session.screen}

    def to_title(self):
        """To the title screen, the world saved first (pygame's pause menu, MAIN MENU)."""
        from .title_session import TitleSession
        self._save()
        notice = i18n.t("map_session.guild_was_wiped_out_load") if self.wiped else None
        self.game.open(TitleSession(notice))
        return {"screen": "title"}

    def save_as(self, name):
        """A named snapshot on the guild's saves (pygame's pause menu, SAVE AS)."""
        if self.world_id is None or self.wiped:
            raise ValueError(i18n.t("map_session.there_is_nothing_to_save"))
        name = str(name).strip()[:persist.MAX_SAVE_NAME] or i18n.t("map_session.manual_save")
        persist.save_game(self.world_id, self.guild, kind="manual", label=name)
        return {"saved": name}

    def aside(self, which):
        """The wiki or the settings from the menu; back comes to the map as it was."""
        from .settings_session import SettingsSession
        from .wiki_session import WikiSession
        session = (WikiSession(self.back, i18n.t("map_session.back_to_map")) if which == "wiki"
                   else SettingsSession(self.back, i18n.t("map_session.back_to_map"), self.guild, self._save))
        self.game.open(session)
        return {"screen": session.screen}

    def quit(self):
        """QUIT from the menu, the world saved first."""
        self._save()
        self.game.quit()
        return {"quit": True}

    def tutorial_key(self):
        key = "group_turn" if self.turn is not None else "map"
        seen = self.guild.tutorial.seen
        return key if key not in seen else hints.on_map(self.guild, seen) or key

    def tutorial_wiki(self, key):
        return hints.wiki_ref(key)

    def resume(self):
        return self.back()

    def tutorial_closed(self, key, first):
        """The map's card is the first after the draft: its first close opens the objectives, as pygame's."""
        return self._sheet("reputations", None) if first and key == "map" else None

    def back(self):
        """Back from a screen: on to whatever else the clock left due."""
        self.game.open(self)
        return self._land()

    def _save(self):
        if self.world_id is not None and not self.wiped:
            persist.save_game(self.world_id, self.guild)
