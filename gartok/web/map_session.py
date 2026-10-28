"""The campaign map in the browser: the bands, the known world, what the picked band can do where it
stands, and the clock. Orders and the clock run as `MapScreen` and `App` run them; what the map
shows of a band and its node is `map_view.MapView`, which pygame's map reads too.
"""

import dataclasses
from itertools import pairwise
from typing import ClassVar

from .. import (
    arena,
    artwork,
    campaign,
    clock,
    economy,
    forced,
    gather,
    missions,
    orders,
    persist,
    recruit,
    rest,
    vocations,
    world,
)
from ..constants import fmt_money
from ..group import CAUTIOUS, NORMAL
from ..map_view import ADVANCE_HOURS, STANCE_NOTES, MapView, node_icon, position
from .session import Session, asset_url

REST_ROWS = (("rest:1", "1 h"), ("rest:8", "8 h"), ("rest:full", "Until full"))


def _icon(slug):
    return f"{slug[0]}/{slug[1]}" if slug else None


def _portrait(u):
    return asset_url(artwork.portrait_path(u.race["name"], getattr(u, "portrait_id", None)))


def _when(guild, hours):
    """`(day, "HH:MM")` `hours` from now."""
    at = clock.Clock(guild.clock.seconds + round(hours * clock.SECONDS_PER_HOUR))
    return at.day, f"{at.hour_of_day:02d}:{at.minute_of_hour:02d}"


def _plural(n, word):
    return f"{n} {word}{'s' * (n != 1)}"


class MapSession(MapView, Session):
    screen = "map"
    GET: ClassVar[dict] = {
        "state": lambda s, q: s.state(),
        "preview": lambda s, q: s.preview(q["gid"], q["node"]),
    }
    POST: ClassVar[dict] = {
        "travel": lambda s, b: s.travel(b["gid"], b["node"]),
        "act": lambda s, b: s.act(b["gid"], b["key"]),
        "split": lambda s, b: s.split(b["gid"], b["uids"]),
        "merge": lambda s, b: s.merge(b["gid"], b["other"]),
        "advance": lambda s, b: s.advance_world(),
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
        self.wiped = False
        due = self._pending_event              # a save taken with a fight due opens on that band
        self.focus = due[0].gid if due else None

    # ------------------------------------------------------------------ #
    # what pygame's map reads call                                        #
    # ------------------------------------------------------------------ #
    def _group_blocked(self, g):
        return g.fight_due

    @property
    def _pending_event(self):
        g = next((g for g in self.guild.groups if g.fight_due and not g.empty), None)
        return None if g is None else (g, g.pending)

    def _is_idle(self, g):
        return not g.busy and not g.empty and not g.fight_due

    def _group(self, gid):
        g = next((g for g in self.guild.groups if g.gid == gid), None)
        if g is None:
            raise ValueError("no such band")
        return g

    def _free(self, gid):
        """The band, when it may take an order now."""
        g = self._group(gid)
        if g.fight_due:
            raise ValueError(f"{g.display_name} has a fight to face first")
        if g.busy:
            raise ValueError(f"{g.display_name} is busy")
        return g

    # ------------------------------------------------------------------ #
    # the screen                                                          #
    # ------------------------------------------------------------------ #
    def state(self):
        g = self.guild
        notices, self.notices = self.notices, []
        focus, self.focus = self.focus, None
        known = {n.id for n in world.known(g)}
        return {
            "meta": self._meta(),
            "alerts": self._alerts(),
            "ledger": [("Members", str(len(g))), ("Rations", str(g.rations)),
                       ("Purse", fmt_money(g.money)), ("Reputation", str(g.arena_reputation))],
            "nodes": [self._node(n) for n in world.NODES if n.id in known],
            "edges": [[a, b, d] for a, b, d in world.EDGES if a in known and b in known],
            "groups": [self._band(gr) for gr in g.groups if not gr.empty],
            "hours": self._hours(),
            "cta": self._cta(),
            "notices": notices,
            "focus": focus,
            "wiped": self.wiped,
        }

    def _meta(self):
        g, c = self.guild, self.guild.clock
        h = c.hour_of_day
        part = ("night" if not c.is_daylight else "morning" if h < 12 else "afternoon" if h < 15 else "evening")
        turn = clock.NIGHT_START if c.is_daylight else clock.DAY_START
        voc = vocations.VOCATIONS.get(g.vocation)
        bands = len([gr for gr in g.groups if not gr.empty])
        pending = sum(1 for u in g.roster if u.pending_picks)
        return {"world": self.world_id, "name": g.name or "The Guild", "day": c.day,
                "time": f"{h:02d}:{c.minute_of_hour:02d}", "daylight": c.is_daylight, "hour": h + c.minute_of_hour / 60,
                "part": part, "turn": f"{'light' if c.is_daylight else 'dark'} till {turn:02d}:00",
                "subtitle": f"{voc.name if voc else 'A guild'} · {_plural(len(g), 'member')} in {_plural(bands, 'band')}",
                "banner": list(g.banner_color) if g.banner_color else None,
                "emblem": _icon(next(((c, s) for c, s, _ in artwork.BANNER_ICONS if s == g.banner_icon), None)),
                "level_ups": pending, "slots_free": g.free_slots}

    def _alerts(self):
        out = []
        food = self.guild.food_alert()
        if food:
            out.append({"title": food[2], "text": food[1], "icon": "action/eating", "tone": "bad"})
        if arena.defense_due(self.guild):
            out.append({"title": "Title defense", "icon": "body/sword-tie", "tone": "bad",
                        "text": f"{arena.champion_of(self.guild).name} must defend the Champion of the Pit "
                                f"by day {arena.defense_deadline(self.guild)}"})
        hungry = self.guild.hungry
        if hungry and not food:
            out.append({"title": f"{len(hungry)} hungry", "icon": "action/eating", "tone": "warn",
                        "text": ", ".join(u.name for u in hungry)})
        return out

    def _node(self, n):
        return {"id": n.id, "name": n.name, "x": n.pos[0], "y": n.pos[1], "kind": n.kind,
                "icon": _icon(node_icon(n.id)), "blurb": n.blurb,
                "alert": self._node_alert(n), "ethereal": world.is_ethereal(n.id)}

    def _node_alert(self, n):
        return (any(n.has(fn) and recruit.has_new_faces(self.guild, key) for fn, key in recruit.SEEN_FUNCTIONS.items())
                or bool(missions.offers_at(self.guild, n.id)))

    def _chip(self, g):
        if g.fight_due:
            return "Ambushed" if g.pending.kind == "ambush" else "Fight due", "bad"
        o = g.order
        if o is None or o.kind == "idle":
            return "No orders", "idle"
        label = ("gather" if o.kind == "work" and o.gather else "search" if o.task in campaign.SEARCHES
                 else o.task if o.kind == "solo" else "travelling" if o.kind == "travel" else o.kind)
        return label.replace("_", " "), "go" if o.kind == "travel" else "busy"

    def _band(self, g):
        chip, tone = self._chip(g)
        at = position(g)
        kit = [_plural(len(g.members), "soul")]
        kit += [f"a {w.kind.lower()}" for w in g.wagons] + [f"a {a.species.lower()}" for a in g.herd]
        return {
            "gid": g.gid, "name": g.display_name, "lead": g.leader.name if g.leader else "",
            "node": g.node, "at": at if isinstance(at, str) else list(at),
            "chip": chip, "tone": tone, "detail": self._order_status(g),
            "kit": ", ".join(kit), "rations": g.rations, "money": fmt_money(g.money),
            "idle": self._is_idle(g), "blocked": g.fight_due, "busy": g.busy,
            "pace": world.hours(1, g.speed) * self._pace(g),
            "members": [self._member(u, g) for u in g.members],
            "trip": self._trip(g),
            "split": [{"uid": u.uid, "name": u.name, "sub": f"{u.race['name']} · {u.hp} / {u.hp_max} HP",
                       "portrait": _portrait(u)} for u in g.members]
                     + [{"uid": w.uid, "name": w.kind, "sub": "wagon"} for w in g.wagons]
                     + [{"uid": a.uid, "name": a.species, "sub": "animal"} for a in g.herd],
            "can_split": "" if self.guild.free_slots else "no free band slot",
            "mates": [{"gid": gid, "name": name} for gid, name in self._mates_for(g)],
            "inspector": self._inspector(g),
        }

    def _member(self, u, g):
        return {"uid": u.uid, "name": u.name, "portrait": _portrait(u), "lead": u is g.leader,
                "hp": u.hp, "hp_max": u.hp_max, "hungry": u.hunger_level > 0, "sick": bool(u.sick),
                "poisoned": bool(u.poisoned),
                "sub": f"{u.race['name']} · {u.occupation['name']} · lvl {u.racial_level}"}

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
                       "text": f"{_plural(n, 'foe')} stand in the way. There is no going on until it is faced."}]
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
        out = [{"value": fmt_money(day), "label": "A 16 h shift"}]
        if gather.can_gather(here.id):
            held = self.guild.has_licence(here.id)
            out.append({"value": "held" if held else "no licence", "label": "Gathering", "no": not held})
        out.append({"value": str(len(g.members)), "label": "Workers"})
        return out

    def _camp(self, g):
        now = self.guild.clock.seconds
        if g.has_campfire(now):
            fire = {"label": "Campfire", "sub": f"burning, {g.campfire_hours_left(now):g} h left", "enabled": True}
        else:
            missing = []
            if not any(u.has_item(economy.FIELD_CAMPFIRE_TOOL) for u in (*g.members, *g.stores)):
                missing.append(economy.FIELD_CAMPFIRE_TOOL)
            if sum(u.unlocked_of(economy.FIELD_CAMPFIRE_LUMBER) for u in g.members) < 1:
                missing.append("1 Lumber")
            if sum(u.unlocked_of(economy.FIELD_CAMPFIRE_COAL) for u in g.members) < 1:
                missing.append("1 Coal")
            fire = {"label": "Campfire", "enabled": not missing,
                    "sub": f"needs {', '.join(missing)}" if missing else "light it and cook · burns 4 h"}
        hurt = [u for u in g.members if u.hp < u.hp_max or u.sick or u.poisoned]
        urgent = self._rest_urgent(g)
        rows = []
        for (key, label), (_, _, plan) in zip(REST_ROWS, self._rest_plans(g)):
            if not plan.available:
                rows.append({"key": key, "label": label, "sub": plan.reason, "enabled": False})
                continue
            meals = plan.meals * len(g.members)
            sub = "no meal" if meals == 0 else _plural(meals, "meal")
            if key == "rest:full":
                sub = f"{rest.format_hours(plan.hours)} · {sub}"
            rows.append({"key": key, "label": "To the floor" if plan.capped else label, "sub": sub,
                         "enabled": True, "rec": key == "rest:full" and urgent,
                         "tip": (f"rations run out {_plural(plan.short_days, 'day')} short of full health"
                                 if plan.capped else None)})
        return {
            "fire": fire,
            "stance": [{"key": key, "label": key.capitalize(), "sub": sub, "tip": STANCE_NOTES[key], "on": g.stance == key}
                       for key, sub in ((NORMAL, "the usual odds"), (CAUTIOUS, "fewer ambushes, with a Scout"))],
            "rest": rows,
            "starving": g.rations == 0,
            "hurt": ([f"{hurt[0].name} is hurt."] if len(hurt) == 1 else
                     [f"{len(hurt)} are hurt, sick or poisoned."] if hurt else []),
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
            what = (f"{g.display_name} reaches {world.node(o.dest).name}" if o.kind == "travel"
                    else f"{g.display_name}: {self._order_status(g).split(' (')[0]} ends")
            rows.append((t, what))
        c = self.guild.clock
        now = c.hour_of_day + c.minute_of_hour / 60
        turn = clock.NIGHT_START if c.is_daylight else clock.DAY_START
        rows.append(((turn - now) % 24, "Dark falls" if c.is_daylight else "Dawn"))
        rows.sort()
        out = [{"at": _when(self.guild, 0)[1], "day": c.day, "text": self._now_line(), "now": True}]
        for t, text in rows[:4]:
            day, at = _when(self.guild, t)
            out.append({"at": at, "day": day, "text": text, "now": False})
        return out

    def _now_line(self):
        idle = [g for g in self.guild.groups if self._is_idle(g)]
        if self._pending_event:
            return f"{self._pending_event[0].display_name} must face a fight"
        if idle:
            return f"{idle[0].display_name} waits for orders" if len(idle) == 1 else f"{len(idle)} bands wait for orders"
        return "Every band is about its work"

    def _cta(self):
        due = self._pending_event
        if due is not None:
            return {"key": "resolve_event", "label": "Fight", "sub": f"{len(due[1].pack)} foes", "danger": True,
                    "enabled": True, "gid": due[0].gid,
                    "text": f"{due[0].display_name} is stopped. Nothing moves on until it is faced."}
        idle = [g for g in self.guild.groups if self._is_idle(g)]
        if not idle and self._everyone_garrisoned():
            return {"key": "advance_world", "label": f"Advance {ADVANCE_HOURS} h", "sub": "whole world",
                    "danger": False, "enabled": True, "text": "Every band holds a post. Let the day run."}
        return {"key": "cycle_idle", "label": "Next band", "danger": False, "enabled": len(idle) > 1,
                "sub": f"{len(idle)} waiting" if len(idle) > 1 else "none idle", "idle": [g.gid for g in idle],
                "text": (f"The clock waits on {idle[0].display_name}. Give it an order and the day runs on by itself."
                         if len(idle) == 1 else f"{len(idle)} bands wait. The seal steps to the next one."
                         if idle else "The clock runs.")}

    # ------------------------------------------------------------------ #
    # what the person does                                                #
    # ------------------------------------------------------------------ #
    def preview(self, gid, node_id):
        """The slip over a place: the walk there, its hours and when the band gets in."""
        g = self._group(gid)
        n = world.node(node_id)
        out = {"node": node_id, "name": n.name, "blurb": n.blurb, "path": [], "hours": 0.0}
        if node_id == g.node:
            out["why"] = f"{g.display_name} stands here"
            return out
        path, dist = world.route(g.node, node_id)
        if dist == float("inf"):
            out["why"] = "no road leads there"
            return out
        hours = sum(self._legs(g, path))
        day, at = _when(self.guild, hours)
        out.update(path=path, via=[world.node(p).name for p in path[1:-1]], hours=round(hours, 1),
                   day=day, at=at)
        if g.fight_due:
            out["why"] = "a fight must be faced first"
        elif g.busy:
            out["why"] = f"{g.display_name} is busy"
        elif any(w.broken for w in g.wagons):
            out["why"] = "a broken wagon must be mended first (leaving it behind is not in the browser yet)"
        return out

    def travel(self, gid, node_id):
        g = self._free(gid)
        if node_id == g.node:
            raise ValueError(f"{g.display_name} is already there")
        if any(w.broken for w in g.wagons):
            raise ValueError("a broken wagon must be mended first; leaving it behind is not in the browser yet")
        g.order = orders.travel(g, node_id, self._pace(g))
        self.focus = g.gid
        return self._after_order()

    def act(self, gid, key):
        g = self._group(gid)
        if key == "resolve_event":
            if not g.fight_due:
                raise ValueError(f"{g.display_name} has no fight to face")
            from .campaign_fight import forced_fight
            from .dialogue_session import forced_talk
            return self._talk(forced_talk(self, g)) or forced_fight(self, g, g.pending)
        if key == "guild":
            return self._sheet("members", g.gid)
        if g.fight_due:
            raise ValueError(f"{g.display_name} has a fight to face first")
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
            raise ValueError(f"{g.display_name} is busy")
        elif key.startswith("rest:"):
            which = key.split(":")[1]
            plan = rest.until_full(self.guild, g) if which == "full" else rest.fixed(self.guild, float(which))
            if not plan.available:
                raise ValueError(plan.reason)
            self.notices += self.guild.eat_now_pass(g.members)
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
                    raise ValueError("the band cannot light a campfire")
                self.notices.append(f"{g.display_name}: campfire lit. Burns for 4 hours.")
                self._save()
            from .hub_session import HubSession
            self.game.open(HubSession(self, g, orders.Order("campfire")))
            return {"screen": HubSession.screen}
        elif key in orders.INTERACTIVE_KINDS:
            return self._enter(g, orders.interactive(key, hours=0))
        else:
            raise ValueError(f"no such order: {key}")
        self.focus = g.gid
        return self._after_order()

    def split(self, gid, uids):
        g = self._group(gid)
        if g.fight_due:
            raise ValueError(f"{g.display_name} has a fight to face first")
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
            raise ValueError("a band with a fight to face cannot merge")
        self.guild.merge_groups(a, b)
        self.focus = a.gid
        self._save()
        return self.state()

    def advance_world(self):
        if self._pending_event is not None:
            raise ValueError("a fight must be faced first")
        if not self._everyone_garrisoned():
            raise ValueError("only when every band holds a post")
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
            self.notices += [f"{u.name} died." for u in result.casualties]
            dead += result.casualties
            for lu in result.level_ups:
                gains = ", ".join(f"{label} {a} → {b}" for label, a, b in lu.gains)
                self.notices.append(f"{lu.unit.name} grows: {gains}.")
            if result.wiped:
                self.wiped = True
                return set(), dead
            self.pending += result.pending
            idle = {g.gid for g in self.guild.groups if g.gid in busy_before and not g.busy}
            if dt is not None or result.pending:
                return idle, dead
            if idle or not any(g.busy for g in self.guild.groups):
                if idle:
                    self.focus = next(iter(idle))
                return idle, dead

    def tick_outside(self, hours, busy=()):
        """Hours spent off the map (a repair), run through `campaign.advance` as `App._tick_outside_map`
        does, so the other bands keep in step and what falls due waits for the map."""
        result = campaign.advance(self.guild, dt=hours, busy=busy)
        self.pending += result.pending
        self.notices += [f"{u.name} died." for u in result.casualties]
        self.wiped = self.wiped or result.wiped
        return result.events, result.casualties

    def _land(self):
        """Open the next screen the clock left due, or land on the map; the answer is the screen open."""
        if self.wiped:
            return {"screen": self.screen, **self.state()}
        while self.pending:
            group, order = self.pending.pop(0)
            if group.empty or group not in self.guild.groups:
                continue
            if order.kind in forced.EVENTS:
                self.focus = group.gid
                continue
            self._save()
            return self._enter(group, order)
        self.notices += arena.sync(self.guild)
        if self.guild.can_auto_advance:
            self._advance()
            return self._land()
        self._save()
        return {"screen": self.screen, **self.state()}

    def _enter(self, group, order):
        """The screen `order` plays: the arena, the hunt, a search's find, an errand's fight, else its hub."""
        from .hub_session import HUB_KINDS, HubSession
        if order.kind == "arena":
            from .arena_session import open_arena
            return open_arena(self, group)
        if order.kind in ("hunt", "ox_hunt"):
            from .hunt_session import open_hunt
            return open_hunt(self, group, "ox" if order.kind == "ox_hunt" else "meat")
        if order.kind in ("ancient_ruins", "serpents_nest", "dragon_lair"):
            from .campaign_fight import delve
            return delve(self, group, order.kind)
        if order.kind in ("skirmish", "camp_fight", "ogre_fight"):
            from .campaign_fight import errand
            return errand(self, group, order.kind)
        if order.kind not in HUB_KINDS:
            raise ValueError(f"no screen plays {order.kind}")
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
        notice = "The guild was wiped out. Load an earlier save to try again." if self.wiped else None
        self.game.open(TitleSession(notice))
        return {"screen": "title"}

    def save_as(self, name):
        """A named snapshot on the guild's saves (pygame's pause menu, SAVE AS)."""
        if self.world_id is None or self.wiped:
            raise ValueError("there is nothing to save")
        name = str(name).strip()[:persist.MAX_SAVE_NAME] or "Manual save"
        persist.save_game(self.world_id, self.guild, kind="manual", label=name)
        return {"saved": name}

    def aside(self, which):
        """The wiki or the settings from the menu; back comes to the map as it was."""
        from .settings_session import SettingsSession
        from .wiki_session import WikiSession
        session = (WikiSession(self.back, "Back to the map") if which == "wiki"
                   else SettingsSession(self.back, "Back to the map", self.guild, self._save))
        self.game.open(session)
        return {"screen": session.screen}

    def quit(self):
        """QUIT from the menu, the world saved first."""
        self._save()
        self.game.quit()
        return {"quit": True}

    def tutorial_key(self):
        return "map"

    def tutorial_closed(self, key, first):
        """The map's card is the first after the draft: its first close opens the objectives, as pygame's."""
        return self._sheet("reputations", None) if first else None

    def back(self):
        """Back from a screen: on to whatever else the clock left due."""
        self.game.open(self)
        return self._land()

    def _save(self):
        if self.world_id is not None and not self.wiped:
            persist.save_game(self.world_id, self.guild)
