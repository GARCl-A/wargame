"""The title screen, as pygame's `StartScreen`, `MenuScreen` and `SavesScreen`: the menu beside the
last guild played (its charter and the map it has walked), the guilds kept, and one guild's saves.
CONTINUE and LOAD open the map on that save, as `App._continue_game` does."""

import time
from typing import ClassVar

from .. import artwork, persist, recorder, vocations, world
from ..guild import DEFAULT_BANNER_COLOR, DEFAULT_BANNER_ICON
from ..start_screen import INVITE_RACES, MAX_FACES, QUOTE
from .map_session import MapSession, _icon, _plural, _portrait
from .session import Session, asset_url
from .settings_session import SettingsSession
from .wiki_session import WikiSession

CHARTER_FACES = 4    # the charter's roster row; the rest are a count
KIND = {"current": "Current", "auto": "Auto", "manual": "Manual"}


def _stamp(ts, seconds=False):
    return time.strftime("%d %b, %H:%M:%S" if seconds else "%d %b, %H:%M", time.localtime(ts)) if ts else ""


def _emblem(slug):
    return _icon(next(((c, s) for c, s, _ in artwork.BANNER_ICONS if s == slug), None))


def _banner(row):
    """A save row's banner: the shield's colour and emblem."""
    color = row.get("banner_color") or DEFAULT_BANNER_COLOR
    return {"color": list(color), "emblem": _emblem(row.get("banner_icon") or DEFAULT_BANNER_ICON)}


class TitleSession(Session):
    screen = "title"
    GET: ClassVar[dict] = {"state": lambda s, q: s.state()}
    POST: ClassVar[dict] = {
        "page": lambda s, b: s.page(b["page"], b.get("world")),
        "continue": lambda s, b: s.load(s.latest["world"] if s.latest else None),
        "new": lambda s, b: s.new_guild(),
        "wiki": lambda s, b: s.aside(WikiSession(s._return, "Back to the title")),
        "settings": lambda s, b: s.aside(SettingsSession(s._return, "Back to the title")),
        "load": lambda s, b: s.load(b["world"], b.get("save", persist.CURRENT)),
        "delete_world": lambda s, b: s.delete_world(b["world"]),
        "delete_save": lambda s, b: s.delete_save(b["world"], b["save"]),
        "quit": lambda s, b: s.quit(),
    }

    def __init__(self, notice=None):
        recorder.detach()
        self.notice = notice
        self.mode = "home"          # home | guilds | saves
        self.world = None           # the guild whose saves are open
        self._refresh()

    def _refresh(self):
        self.worlds = persist.list_worlds()
        self.latest = self.worlds[0] if self.worlds else None
        self._last = None
        if self.latest:
            try:
                self._last = persist.load_game(self.latest["world"])
            except persist.SaveVersionError:
                pass

    # ------------------------------------------------------------------ #
    # verbs                                                              #
    # ------------------------------------------------------------------ #
    def page(self, mode, world_id=None):
        if mode not in ("home", "guilds", "saves"):
            raise ValueError(f"no page called {mode}")
        if mode == "saves" and not any(w["world"] == world_id for w in self.worlds):
            raise ValueError("no such guild")
        self.mode, self.world = mode, world_id if mode == "saves" else None
        return self.state()

    def load(self, world_id, save_id=persist.CURRENT):
        """Open the map on `save_id` of `world_id`; a snapshot becomes the live state, as in pygame."""
        if world_id is None:
            raise ValueError("there is no guild to continue")
        try:
            self.game.load(world_id, save_id)
        except persist.SaveVersionError as e:
            raise ValueError(str(e)) from None
        except FileNotFoundError:
            raise ValueError("that save is gone") from None
        return {"screen": self.game.session.screen}

    def new_guild(self):
        from .draft_session import DraftSession
        self.game.open(DraftSession())
        return {"screen": DraftSession.screen}

    def aside(self, session):
        """The wiki or the settings, which come back here."""
        self.game.open(session)
        return {"screen": session.screen}

    def _return(self):
        self.game.open(self)
        return {"screen": self.screen}

    def delete_world(self, world_id):
        persist.delete_world(world_id)
        self._refresh()
        self.mode, self.world = "guilds", None
        return self.state()

    def delete_save(self, world_id, save_id):
        if save_id == persist.CURRENT:
            raise ValueError("the live state cannot be deleted; delete the guild instead")
        persist.delete_save(world_id, save_id)
        self._refresh()
        return self.state()

    def quit(self):
        self.game.quit()
        return {"quit": True}

    # ------------------------------------------------------------------ #
    # the screen                                                         #
    # ------------------------------------------------------------------ #
    def state(self):
        out = {"mode": self.mode, "quote": QUOTE, "notice": self.notice, "menu": self._menu()}
        if self.mode == "home":
            out["charter"] = self._charter() if self.latest else None
            out["map"] = self._map() if self._last else None
            out["invite"] = None if self.latest else self._invite()
        elif self.mode == "guilds":
            out["guilds"] = [self._guild_row(w) for w in self.worlds]
        else:
            out["saves"] = self._saves()
        return out

    def _menu(self):
        n, latest = len(self.worlds), self.latest
        return [
            {"key": "continue", "label": "Continue", "primary": True, "enabled": latest is not None,
             "hint": f"{latest['name'] or 'Unnamed guild'} · day {latest.get('day') or 1}" if latest else None,
             "emblem": _banner(latest)["emblem"] if latest else None},
            {"key": "new", "label": "New guild", "enabled": True},
            {"key": "load", "label": "Load game", "enabled": n > 0, "hint": _plural(n, "guild") if n else None},
            None,
            {"key": "wiki", "label": "Wiki & compendium", "enabled": True},
            {"key": "settings", "label": "Settings", "enabled": True},
            {"key": "editor", "label": "Editor", "enabled": False, "hint": "characters, maps, combat lab"},
            None,
            {"key": "quit", "label": "Quit", "enabled": True, "quiet": True},
        ]

    def _charter(self):
        w, g = self.latest, self._last
        voc = vocations.get(w.get("vocation"))
        out = {"world": w["world"], "name": w["name"] or "Unnamed guild", "saved": _stamp(w.get("saved_at", 0)),
               "vocation": voc.name if voc else None, "motto": voc.motto if voc else None, **_banner(w),
               "ledger": [(w.get("day") or 1, "Day"), (len(w.get("squad", [])), "Members"),
                          (w.get("battles_won", 0), "Wins")]}
        if g is None:
            out["faces"] = self._faces(w)[:CHARTER_FACES]
            out["more"] = max(0, len(w.get("faces", [])) - CHARTER_FACES)
            out["where"] = None
            out["broken"] = "This save is from another version of the game and cannot be loaded."
            return out
        bands = [b for b in g.groups if not b.empty]
        out["ledger"].append((len(bands), "Bands"))
        out["faces"] = [{"name": u.name, "portrait": _portrait(u),
                         "what": f"{u.race['name']} · lvl {u.combat_level}", "hurt": u.hp < u.hp_max}
                        for u in g.roster[:CHARTER_FACES]]
        out["more"] = max(0, len(g.roster) - CHARTER_FACES)
        lead = max(bands, key=len) if bands else None
        out["where"] = ({"place": world.node(lead.node).name,
                         "rest": f"{_plural(len(bands) - 1, 'other band')} abroad" if len(bands) > 1 else None}
                        if lead else None)
        return out

    def _faces(self, w):
        return [{"name": f["name"], "portrait": asset_url(artwork.portrait_path(f["race"], f["portrait"])),
                 "what": f["race"] or "", "hurt": False} for f in w.get("faces", [])[:MAX_FACES]]

    def _map(self):
        """The known world of the last guild, its bands where they stand, for the sheet."""
        g = self._last
        known = {n.id for n in world.known(g)}
        m = MapSession(g)
        return {"meta": {"name": g.name or "The Guild", "day": g.clock.day},
                "nodes": [m._node(n) for n in world.NODES if n.id in known],
                "edges": [[a, b, d] for a, b, d in world.EDGES if a in known and b in known],
                "groups": [{"gid": b.gid, "at": b.node, "trip": None} for b in g.groups if not b.empty]}

    def _invite(self):
        return [{"name": r, "portrait": asset_url(artwork.portrait_path(r, 0))}
                for r in INVITE_RACES if artwork.portrait_path(r, 0)]

    def _guild_row(self, w):
        voc = vocations.get(w.get("vocation"))
        n = len(w.get("squad", []))
        return {"world": w["world"], "name": w["name"] or "Unnamed guild", "vocation": voc.name if voc else None,
                "day": w.get("day") or 1, "members": n, "wins": w.get("battles_won", 0),
                "saves": w["saves"], "saved": _stamp(w.get("saved_at", 0)), **_banner(w),
                "faces": self._faces(w)[:6]}

    def _saves(self):
        rows = persist.list_saves(self.world)
        name = next((s["name"] for s in rows if s["name"]), "") or "Unnamed guild"
        return {"world": self.world, "name": name,
                "rows": [{"id": s["id"], "kind": s["kind"], "kind_label": KIND.get(s["kind"], "Current"),
                          "label": s["label"] or ("the live state, saved on every stop" if s["kind"] == "current" else ""),
                          "saved": _stamp(s["saved_at"], seconds=True), "day": s["day"],
                          "wins": s["battles_won"], "members": len(s["squad"])} for s in rows]}
