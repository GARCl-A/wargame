"""A node's screens behind one row of tabs: the shop beside whatever else the place does.

`TabbedHubScreen` holds `(key, label, screen)` tabs and owns the frame they sit in
(`ui.hub_frame`): the keeper's header with the cards of the tab in view, the tab row, and --
for a tab drawn for the frame (`framed = True`) -- the back button; the tab draws only its body,
on a subsurface, with the mouse and the events moved into it. A tab not yet redrawn for the
frame keeps its own header and footer, drawn under the tab row. `ShopHubScreen` is the Smith's,
the Tanner's and the Apothecary's: the node's shop first, then the rest.
"""

import pygame

from . import world
from .market_screen import MarketScreen
from .screen import Screen
from .ui.hub_frame import draw_footer, draw_header, draw_tabs, hub_layout
from .ui.tokens import T
from .ui.tokens import fonts as ui_fonts

# which keeper a tab shows when the node has one per function
_TAB_FUNCTION = {"shop": "shop", "forge": "forge", "craft": "forge", "carpenter": "carpenter",
                 "jobs": "tanner", "library": "library", "study": "library", "initiation": "shrine"}
BACK_LABEL = "← back to guild"
HINTS = "Esc · back    Tab · next service"


def _can_frame(screen):
    """A tab whose class offers a plain `framed = False` switch (a property, like the Tavern's,
    decides for itself)."""
    for klass in type(screen).__mro__:
        if "framed" in klass.__dict__:
            return klass.__dict__["framed"] is False
    return False


class TabbedHubScreen(Screen):
    native = True

    def __init__(self, fonts, tabs, first=None, node=None, on_done=None):
        super().__init__()
        self.fonts = fonts
        self._F = ui_fonts()
        self.tabs = list(tabs)
        self.tab = first or self.tabs[0][0]
        self.node = node
        self.on_done = on_done
        for _key, _label, screen in self.tabs:
            if _can_frame(screen):
                screen.framed = True             # a tab that can draw for the frame does so here
        self._tab_hits = []
        self._back = None
        self._help = pygame.Rect(0, 0, 0, 0)
        self._body = pygame.Rect(0, 0, 0, 0)

    @classmethod
    def for_node(cls, fonts, guild, group, node, on_done, first=None):
        """Constructs a TabbedHubScreen dynamically from node.functions."""
        from . import world
        tabs = []
        if node.has("shop"):
            shop_label = "FOOD & DRINK" if node.id == "tavern" else "FARM" if node.id == "farm" else "SHOP"
            shop = MarketScreen(fonts, guild, list(group.members), node, on_done)
            tabs.append(("shop", shop_label, shop))
        if node.has("recruit") and node.id == "tavern":
            from .taverna_screen import TavernaScreen
            tavern = TavernaScreen(fonts, guild, list(group.members), node, on_done, group=group, hide_tabs=True)
            tabs.append(("recruits", "RECRUIT", tavern))
            tabs.append(("rooms", "STUDY", tavern))
            tabs.append(("perform", "PERFORM", tavern))
        elif node.has("recruit"):
            from .taverna_screen import TavernaScreen
            tavern = TavernaScreen(fonts, guild, list(group.members), node, on_done, group=group)
            tabs.append(("tavern", "TAVERN", tavern))
        if node.has("stable"):
            from .stables_screen import StablesScreen
            stables = StablesScreen(fonts, guild, group, on_done)
            tabs.append(("stable", "STABLES", stables))
        if node.has("forge"):
            from .crafting_screen import CraftingScreen
            craft = CraftingScreen(fonts, guild, group, on_done, vendor=world.vendor(node.id, "forge"))
            tabs.append(("forge", "FORGE", craft))
        if node.has("carpenter"):
            from .crafting_screen import CraftingScreen
            craft = CraftingScreen(fonts, guild, group, on_done,
                                   title="CARPENTRY",
                                   subtitle="craft wooden bows, crossbows and tools  ·  needs recipes and materials",
                                   station="carpenter",
                                   vendor=world.vendor(node.id, "carpenter"))
            tabs.append(("carpenter", "CARPENTRY", craft))
        if node.has("tanner"):
            from .tanner_screen import TannerScreen
            jobs = TannerScreen(fonts, guild, group, on_done)
            tabs.append(("jobs", "JOBS", jobs))
        if node.has("apothecary"):
            from .apothecary_mission_screen import ApothecaryMissionScreen
            from .medic_screen import MedicScreen
            medic = MedicScreen(fonts, guild, group, on_done)
            jobs = ApothecaryMissionScreen(fonts, guild, group, on_done)
            tabs.append(("medic", "MEDIC", medic))
            tabs.append(("jobs", "JOBS", jobs))
        if node.has("library"):
            from .library_mission_screen import LibraryMissionScreen
            from .library_screen import LibraryScreen
            study = LibraryScreen(fonts, guild, list(group.members), node, on_done)
            jobs = LibraryMissionScreen(fonts, guild, group, on_done)
            tabs.append(("study", "STUDY", study))
            tabs.append(("jobs", "JOBS", jobs))
        if node.has("shrine"):
            from .initiation_screen import InitiationScreen
            from .shrine_screen import ShrineMissionScreen
            tabs.append(("jobs", "JOBS", ShrineMissionScreen(fonts, guild, group, on_done)))
            tabs.append(("initiation", "INITIATION", InitiationScreen(fonts, guild, group, on_done)))
        from . import gather
        if node.has("work"):
            from .work_screen import WorkScreen
            tabs.append(("work", "WORK", WorkScreen(fonts, guild, group, node, on_done)))
        if node.has("work") and gather.can_gather(node.id):
            from .gather_screen import GatherScreen
            gathering = GatherScreen(fonts, guild, group, node, on_done)
            tabs.append(("gather", "GATHERING", gathering))

        if not tabs:
            tabs.append(("shop", "SHOP", MarketScreen(fonts, guild, list(group.members), node, on_done)))
        if first in ("tavern", "recruit"):
            first = "recruits"
        elif first == "study" and node.id == "tavern":
            first = "rooms"
        chosen = first if (first and any(k == first for k, _, _ in tabs)) else tabs[0][0]
        return cls(fonts, tabs, first=chosen, node=node, on_done=on_done)

    def active_screen(self):
        screen = next(s for k, _label, s in self.tabs if k == self.tab)
        if hasattr(screen, "sync_group"):
            screen.sync_group()
        if hasattr(screen, "hide_tabs") and screen.hide_tabs:
            if self.tab in ("recruits", "rooms", "perform"):
                screen.tab = self.tab
        return screen

    def tutorial_key(self):
        return self.active_screen().tutorial_key()

    def tutorial_badge_rect(self, size):
        return self._help

    def _framed(self):
        return getattr(self.active_screen(), "framed", False)

    def keeper(self):
        """The header's keeper: the vendor behind the tab in view, else the node's first."""
        node = self.node
        if node is None:
            return {"place": ""}
        vendor = world.vendor(node.id, _TAB_FUNCTION.get(self.tab, self.tab))
        if vendor is None and getattr(node, "vendors", None):
            vendor = next(iter(node.vendors.values()))
        if vendor is None:
            return {"place": node.name}
        bent = ""
        if node.alignment:
            law, moral = node.alignment.split(" and ")
            bent = law if law == moral else f"{law} {moral}"
        return {"place": node.name, "name": vendor.name, "caption": f"{vendor.race} {vendor.role}",
                "bent": bent, "line": vendor.line, "portrait": vendor.portrait}

    def _leave(self):
        done = self.on_done or getattr(self.active_screen(), "on_done", None)
        if done:
            done()

    def handle_escape(self):
        if self.active_screen().handle_escape():
            return True
        if self._framed():
            self._leave()
            return True
        return False

    def _local(self, event):
        """`event` with its position moved into the tab's body."""
        if not hasattr(event, "pos"):
            return event
        d = dict(event.dict)
        d["pos"] = (event.pos[0] - self._body.x, event.pos[1] - self._body.y)
        return pygame.event.Event(event.type, d)

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_TAB and len(self.tabs) > 1:
            keys = [k for k, _l, _s in self.tabs]
            step = -1 if event.mod & pygame.KMOD_SHIFT else 1
            self.tab = keys[(keys.index(self.tab) + step) % len(keys)]
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for rect, key in self._tab_hits:
                if rect.collidepoint(event.pos):
                    self.tab = key
                    return
            if self._back is not None and self._back.collidepoint(event.pos):
                self._leave()
                return
        active = self.active_screen()
        active.mouse = (self.mouse[0] - self._body.x, self.mouse[1] - self._body.y)
        active.handle_event(self._local(event))

    def update(self, dt):
        self.active_screen().update(dt)

    def draw(self, screen):
        F = self._F
        size = screen.get_size()
        lay = hub_layout(size)
        screen.fill(T.TABLE)
        active = self.active_screen()
        cards = active.hub_cards() if hasattr(active, "hub_cards") else []
        self._help = draw_header(screen, F, lay["header"], self.keeper(), cards)
        self._tab_hits = draw_tabs(screen, F, lay["tabs"], [(k, label) for k, label, _s in self.tabs],
                                   self.tab, self.mouse)
        framed = self._framed()
        self._body = lay["body"] if framed else pygame.Rect(0, lay["tabs"].bottom, size[0],
                                                             max(1, size[1] - lay["tabs"].bottom))
        active.mouse = (self.mouse[0] - self._body.x, self.mouse[1] - self._body.y)
        active.draw(screen.subsurface(self._body))
        self._back = draw_footer(screen, F, lay["footer"], BACK_LABEL, HINTS, self.mouse) if framed else None
        self._hot = getattr(active, "_hot", False) or any(r.collidepoint(self.mouse) for r, _k in self._tab_hits)


class ShopHubScreen(TabbedHubScreen):
    """The node's shop as the first tab, then `others` (`(key, label, screen)`)."""

    def __init__(self, fonts, guild, group, node, others, on_done, first=None):
        shop = MarketScreen(fonts, guild, list(group.members), node, on_done)
        super().__init__(fonts, [("shop", "SHOP", shop), *others], first=first, node=node, on_done=on_done)
