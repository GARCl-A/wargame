"""The title screen: the menu beside the last guild played (its charter and the map it has walked),
the guilds kept, and one guild's saves. CONTINUE and LOAD open the map on that save; with no guild
yet, the invitation shows a face of each of `INVITE_RACES`."""

import time
from typing import ClassVar

from .. import art_files, i18n, persist, recorder, vocations, world
from ..guild import DEFAULT_BANNER_COLOR, DEFAULT_BANNER_ICON
from .credits_session import CreditsSession
from .map_session import MapSession, _icon, _plural, _portrait
from .session import Session, asset_url
from .settings_session import SettingsSession
from .wiki_session import WikiSession

CHARTER_FACES = 4    # the charter's roster row; the rest are a count
INVITE_RACES = ("Human", "Orc", "Elf", "Dwarf", "Goblin", "Grippli", "Centaur", "Kenku")
MAX_FACES = 12
KIND = {k: f"title_session.kind.{k}" for k in ("current", "auto", "manual")}


def _stamp(ts, seconds=False):
    return time.strftime("%d %b, %H:%M:%S" if seconds else "%d %b, %H:%M", time.localtime(ts)) if ts else ""


def _emblem(slug):
    return _icon(next(((c, s) for c, s, _ in art_files.BANNER_ICONS if s == slug), None))


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
        "wiki": lambda s, b: s.aside(WikiSession(s._return, i18n.t("title_session.back_to_title"))),
        "settings": lambda s, b: s.aside(SettingsSession(s._return, i18n.t("title_session.back_to_title"))),
        "credits": lambda s, b: s.aside(CreditsSession(s._return, i18n.t("title_session.back_to_title"))),
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
        self._broken = None
        if self.latest:
            try:
                self._last = persist.load_game(self.latest["world"])
            except persist.SaveVersionError as e:
                self._broken = str(e)

    # ------------------------------------------------------------------ #
    # verbs                                                              #
    # ------------------------------------------------------------------ #
    def page(self, mode, world_id=None):
        if mode not in ("home", "guilds", "saves"):
            raise ValueError(i18n.t("title_session.no_page_called", mode=mode))
        if mode == "saves" and not any(w["world"] == world_id for w in self.worlds):
            raise ValueError(i18n.t("title_session.no_such_guild"))
        self.mode, self.world = mode, world_id if mode == "saves" else None
        return self.state()

    def load(self, world_id, save_id=persist.CURRENT):
        """Open the map on `save_id` of `world_id`; a snapshot becomes the live state, as in pygame."""
        if world_id is None:
            raise ValueError(i18n.t("title_session.there_is_no_guild_to"))
        try:
            self.game.load(world_id, save_id)
        except persist.SaveVersionError as e:
            raise ValueError(str(e)) from None
        except FileNotFoundError:
            raise ValueError(i18n.t("title_session.that_save_is_gone")) from None
        return {"screen": self.game.session.screen}

    def new_guild(self):
        from .draft_session import DraftSession
        self.game.open(DraftSession())
        return {"screen": DraftSession.screen}

    def aside(self, session):
        """The wiki, the settings or the credits, which come back here."""
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
            raise ValueError(i18n.t("title_session.live_state_cannot_be_deleted"))
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
        out = {"mode": self.mode, "notice": self.notice, "menu": self._menu()}
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
            {"key": "continue", "label": i18n.t("title_session.menu.continue"), "primary": True, "enabled": latest is not None,
             "hint": i18n.t("title_session.day", name=latest['name'] or i18n.t("title_session.unnamed_guild"), day=latest.get('day') or 1) if latest else None,
             "emblem": _banner(latest)["emblem"] if latest else None},
            {"key": "new", "label": i18n.t("title_session.new_guild"), "enabled": True},
            {"key": "load", "label": i18n.t("title_session.load_game"), "enabled": n > 0, "hint": _plural(n, "guild") if n else None},
            None,
            {"key": "wiki", "label": i18n.t("title_session.menu.wiki"), "enabled": True},
            {"key": "settings", "label": i18n.t("title_session.menu.settings"), "enabled": True},
            {"key": "credits", "label": i18n.t("title_session.menu.credits"), "enabled": True},
            {"key": "editor", "label": i18n.t("title_session.menu.editor"), "enabled": False, "hint": i18n.t("title_session.characters_maps_combat_lab")},
            None,
            {"key": "quit", "label": i18n.t("title_session.menu.quit"), "enabled": True, "quiet": True},
        ]

    def _charter(self):
        w, g = self.latest, self._last
        voc = vocations.get(w.get("vocation"))
        out = {"world": w["world"], "name": w["name"] or i18n.t("title_session.unnamed_guild"), "saved": _stamp(w.get("saved_at", 0)),
               "vocation": voc.name if voc else None, "motto": voc.motto if voc else None, **_banner(w),
               "ledger": [(w.get("day") or 1, i18n.t("title_session.ledger.day")), (len(w.get("squad", [])), i18n.t("title_session.ledger.members")),
                          (w.get("battles_won", 0), i18n.t("title_session.ledger.wins"))]}
        if g is None:
            out["faces"] = self._faces(w)[:CHARTER_FACES]
            out["more"] = max(0, len(w.get("faces", [])) - CHARTER_FACES)
            out["where"] = None
            out["broken"] = self._broken
            return out
        bands = [b for b in g.groups if not b.empty]
        out["ledger"].append((len(bands), i18n.t("title_session.ledger.bands")))
        out["faces"] = [{"name": u.name, "portrait": _portrait(u),
                         "what": i18n.t("title_session.lvl", race=u.race_label, combat_level=u.combat_level), "hurt": u.hp < u.hp_max}
                        for u in g.roster[:CHARTER_FACES]]
        out["more"] = max(0, len(g.roster) - CHARTER_FACES)
        lead = max(bands, key=len) if bands else None
        out["where"] = ({"place": world.node(lead.node).name,
                         "rest": i18n.t("title_session.abroad", plural=_plural(len(bands) - 1, i18n.t("title_session.other_band"))) if len(bands) > 1 else None}
                        if lead else None)
        return out

    def _faces(self, w):
        return [{"name": f["name"], "portrait": asset_url(art_files.portrait_path(f["race"], f["portrait"])),
                 "what": f["race"] or "", "hurt": False} for f in w.get("faces", [])[:MAX_FACES]]

    def _map(self):
        """The known world of the last guild, its bands where they stand, for the sheet."""
        g = self._last
        known = {n.id for n in world.known(g)}
        m = MapSession(g)
        return {"meta": {"name": g.name or i18n.t("title_session.guild"), "day": g.clock.day},
                "nodes": [m._node(n) for n in world.NODES if n.id in known],
                "edges": [[a, b, d] for a, b, d in world.EDGES if a in known and b in known],
                "groups": [{"gid": b.gid, "at": b.node, "trip": None} for b in g.groups if not b.empty]}

    def _invite(self):
        return [{"name": r, "portrait": asset_url(art_files.portrait_path(r, 0))}
                for r in INVITE_RACES if art_files.portrait_path(r, 0)]

    def _guild_row(self, w):
        voc = vocations.get(w.get("vocation"))
        n = len(w.get("squad", []))
        return {"world": w["world"], "name": w["name"] or i18n.t("title_session.unnamed_guild"), "vocation": voc.name if voc else None,
                "day": w.get("day") or 1, "members": n, "wins": w.get("battles_won", 0),
                "saves": w["saves"], "saved": _stamp(w.get("saved_at", 0)), **_banner(w),
                "faces": self._faces(w)[:6]}

    def _saves(self):
        rows = persist.list_saves(self.world)
        name = next((s["name"] for s in rows if s["name"]), "") or i18n.t("title_session.unnamed_guild")
        return {"world": self.world, "name": name,
                "rows": [{"id": s["id"], "kind": s["kind"], "kind_label": i18n.t(KIND.get(s["kind"], KIND["current"])),
                          "label": s["label"] or (i18n.t("title_session.live_state_saved_on_every") if s["kind"] == "current" else ""),
                          "saved": _stamp(s["saved_at"], seconds=True), "day": s["day"],
                          "wins": s["battles_won"], "members": len(s["squad"])} for s in rows]}
