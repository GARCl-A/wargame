"""A hub's JOBS tab in the browser (the Tanner, the Apothecary, the Library, a sanctuary): the board on
paper (each job the giver has, what it asks and pays, its state and its button) and, on leather, who signs
for the band and what the packs already carry toward each goal.

The reads, labels and verbs are pygame's own board (`MissionOfferScreen` and the giver's subclass, held
headless as `shop_tab` holds a `MarketScreen`), so the offers, the turn-ins and their notices stay one
source until step 10 of `docs/plans/web_frontend.md` moves them here.
"""

from .. import item_icon, missions
from ..apothecary_mission_screen import ApothecaryMissionScreen
from ..library_mission_screen import LibraryMissionScreen
from ..shrine_screen import ShrineMissionScreen
from ..tanner_screen import TannerScreen
from ..ui.mission_offer_screen import TAG_TONE
from .shop_tab import _portrait

# a node's function -> its giver's board, in the order `TabbedHubScreen.for_node` checks them
BOARDS = (("tanner", TannerScreen), ("apothecary", ApothecaryMissionScreen), ("library", LibraryMissionScreen),
          ("shrine", ShrineMissionScreen))


def _glyph(t):
    if t.fight_at:
        return "item/broadsword"
    if t.goal_captive:
        return "item/crossed-chains"
    return item_icon.glyph(t.goal_item)


class JobsTab:
    def __init__(self, guild, group, node):
        board = next(cls for fn, cls in BOARDS if node.has(fn))
        self.b = board(None, guild, group, lambda: None)
        self.guild, self.group, self.node = guild, group, node

    def _template(self, tid):
        t = missions.TEMPLATES.get(tid)
        if t is None or t not in self.b.get_templates():
            raise ValueError(f"no job {tid!r} on this board")
        return t

    def accept(self, tid):
        if not self.b.accept(self._template(tid)):
            self.b.notice = "that job is not on offer to this band"

    def turn_in(self, tid):
        t = self._template(tid)
        if not self.b.turn_in(t):
            self.b.notice = (f"{t.name}: not ready to hand over" if self.b._mission_of(t)
                             else f"{t.name}: this band does not hold the job")

    def sell_egg(self):
        if self.b.footer_action() is None:
            raise ValueError("nothing to sell here")
        self.b.notice = self.b.run_footer_action() or "the egg is the Cult's job here, not a sale"

    def _job(self, t):
        b = self.b
        m = b._mission_of(t)
        lay = {}
        if m is None:
            detail = b.get_req_str(t)
        else:
            lay["progress"] = missions.progress(self.guild, m)
            lay["ready"] = lay["progress"] >= t.goal_qty
            detail = b.get_status_str(t, lay["progress"], lay["ready"], missions.days_left(self.guild, m))
        (verb, _), label, on = b._job_button(t, m, lay)
        if t.fight_at and verb == "turn_in":
            on = False                # the fight is the turn-in: it happens on the map, not here
        return {"id": t.id, "name": t.name, "glyph": _glyph(t), "blurb": t.blurb or "",
                "tags": [{"label": g.lower(), "tone": TAG_TONE.get(g.lower(), "")} for g in t.tags],
                "detail": [p.removeprefix("goal: ") for p in detail.split("  ·  ")],
                "taken": m is not None, "ready": bool(lay.get("ready")),
                "out": m is None and b._active_of(t) is not None,
                "button": {"verb": verb, "label": label, "on": on}}

    def _carried(self, templates):
        """Who in the band carries how much of each item a job it can take or hand over asks for."""
        out = []
        for t in templates:
            if t.fight_at or t.goal_captive or t.goal_item == "Any Dictionary":
                continue
            if not (self.b._is_offered(t) or self.b._mission_of(t)):
                continue
            who = [(u.name, missions._held(u, t.goal_item)) for u in self.group.members]
            who += [(s.name, s.count_of(t.goal_item)) for s in self.group.stores]
            who = [(n, q) for n, q in who if q]
            out.append({"item": t.goal_item, "glyph": item_icon.glyph(t.goal_item), "goal": t.goal_qty,
                        "have": sum(q for _, q in who), "who": [f"{n} {q}" for n, q in who]})
        return out

    def state(self):
        b = self.b
        templates = b.get_templates()
        leader = self.group.leader
        extra = b.footer_action()
        notice, b.notice = b.notice, None
        return {"cards": b.hub_cards(), "line": b.subtitle_text.strip('"'),
                "jobs": [self._job(t) for t in templates],
                "signer": {"name": leader.name, "portrait": _portrait(leader),
                           "sub": f"{leader.race['name']} {leader.occupation['name'].lower()} · leads the band"},
                "carried": self._carried(templates),
                "egg": None if extra is None else {"label": extra[0], "on": extra[1]},
                "notice": notice}
