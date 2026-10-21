"""Manage Gear: shuffle the roster's loadouts side by side, two views on the
same band.

Built on the real `gartok.ui` component set and the drag/click plumbing the
pack screens share (`DragSelectMixin` / `LoadoutMoveMixin`,
`gartok/dragselect.py`): dragging an item onto a HAND/OFF/BODY slot (or
another member's column, or the rail) is how gear moves here.
Click-then-click-destination still works too (a click without dragging
"picks up" a source; shift/ctrl gathers several).

This file is the adapter + input/state layer only, same split as
`map_screen.py`: it turns real `Unit`/`Group` objects into the plain dicts
`gartok/ui/loadout_panel.py`'s `rail`/`column`/`cargo_table`/`send_menu`/
`split_prompt` draw from, and translates the rects they hand back into
`self.sources`/`self.zones` (which stay `Unit`-keyed -- that's the boundary
where "component" ends and "domain" begins, same seam `LoadoutMoveMixin`
already sits on).

  RAIL   left strip, every member, always -- a compact row per member and,
         since this is *also* a drop target whether or not that member's
         column is open, the fastest way to hand something to someone not
         currently pinned. Clicking a row (with nothing carried) pins/
         unpins its full column.
  BAGS   pinned members as full columns: HAND / OFF / (TONGUE) / BODY /
         PACK.
  CARGO  every stack across the whole band in one sortable table, with the
         same pick-up-and-place selection (a row is a `sources` pick, same
         as a BAGS pack row) so batch actions (send to.../split/drop) reuse
         `LoadoutMoveMixin._give_many` unchanged.

Right-click (or the send-to button in CARGO's bulk bar) opens the one send-to
menu, extended past the original with "split stack" (peels part of a stack
into its own row -- `Unit.split_pack`) and "open the chest" for a Bankers'
seal or a plain lockbox, same rules as before.

Locking a stack (`Unit.locked_items`/`toggle_lock`) only exempts it from
`distribute_load`'s automatic rebalance -- it was never a hard block on a
player picking it up by hand, so no gate is added here either.

It edits the same persistent `equipped_weapon` / `equipped_offhand` /
`equipped_tongue` / `equipped_armor` / `_base_inventory` the guild/gear
screens do, so the next battle re-seeds every `Combatant` from the new
loadout. `native = True`. `on_back()` returns to the map.
"""

import pygame

from . import captives, chest, data, items, magic, missions
from .animals import Animal
from .dragselect import DragSelectMixin, LoadoutMoveMixin
from .group_draw import GroupDrawMixin
from .packbox import ItemMenuMixin, PackColumnMixin
from .screen import Screen
from .sheet_panel import SheetModalMixin
from .ui.hscroll import ColumnScroll
from .ui.tokens import fonts as ui_fonts
from .wagon import Wagon


class GroupScreen(GroupDrawMixin, ItemMenuMixin, PackColumnMixin, DragSelectMixin, LoadoutMoveMixin,
                  SheetModalMixin, Screen):
    native = True

    def __init__(self, fonts, guild, group, on_back, on_tick=None, on_cook=None):
        super().__init__()
        self.fonts = fonts                 
        self.guild = guild
        self.group = group
        self.on_back = on_back
        self.on_tick = on_tick
        self.on_cook = on_cook
        self.tab = "gear"
        self.view = "bags"
        self.pinned = list(self.group.members)        # columns shown in BAGS, clamped to fit at draw time
        self.selected = []                   # [(unit, loc), ...]: loc is "hand"/"offhand"/"tongue"/"armor" or a pack index
        self.menu = None                     # send-to/context menu, see `_open_menu`
        self.notice = None                   # last action's result, shown in the footer
        self.zones = []                     # [(rect, unit, "hand"|"offhand"|"tongue"|"armor"|"pack")]
        self.sources = []                  # [(rect, unit, loc)]
        self._dots_hits = []              # [(rect, unit, loc)] -- the "..." button, opens the menu directly
        self.tab_hits = []              # [(rect, tab_id)]
        self.buttons = []                  # [(key, rect)]
        self._unit_by_uid = self._owners_by_uid()
        self._rail_hits = []              # [(rect, unit)] -- also the drop targets `_zone_at` reuses
        self.back_rect = None                # header's back arrow -- decorative in the mock, wired here
        self._rail_rect = None
        self._rail_scroll = 0
        self._rail_max_scroll = 0
        self._cargo_rect = None
        self._cargo_scroll = 0
        self._cargo_max_scroll = 0
        self._wagon_idx = 0
        self._cols = ColumnScroll()
        self.editing_name = False
        self.name_buf = ""
        self.cargo_search = ""
        self.editing_search = False
        self._search_rect = None
        self._search_clear_rect = None
        self._bulk_anchor = (0, 0)           # CARGO's "send to..." button center, set when it's drawn
        self._F = None                       # lazy: building pygame Fonts needs pygame.font initialised

    # ------------------------------------------------------------------ #
    def tutorial_key(self):
        return "group"

    def _owners(self):
        """Everything here that holds a pack: the members, the animals, the wagons."""
        return [*self.group.members, *self.group.herd, *self.group.wagons]

    def _owners_by_uid(self):
        return {o.uid: o for o in self._owners()}

    @staticmethod
    def _is_store(owner):
        """The group's own storage (an animal's back, a wagon) -- not a person."""
        return isinstance(owner, (Animal, Wagon))

    def _item_at(self, owner, loc):
        if loc == "tack":
            return owner.tack
        if loc == "hitch":                  # an animal picked up by its header: not an item
            return None
        return super()._item_at(owner, loc)

    def _take(self, src, loc):
        if loc == "tack":
            return src.take_tack(), 1
        return super()._take(src, loc)

    def _give_many(self, dst, zone):
        """An animal's back and the wagon have a hard room limit, unlike a
        member's soft overload; an animal's tack slot takes a saddle or harness."""
        if zone == "hitch":
            self._hitch_picked(dst)
            return
        if isinstance(dst, Animal) and zone == "tack":
            self._fit_tack(dst)
            return
        if self._is_store(dst) and zone == "pack":
            picks = [p for p in self.selected if p[0] is not dst and self._item_at(*p) is not None]
            add = sum(items.item_weight(self._item_at(*p)) * self._qty_at(*p) for p in picks)
            if not dst.stash.fits(add):
                self.notice = self._no_room_note(dst)
                return
        super()._give_many(dst, zone)

    @staticmethod
    def _no_room_note(store):
        if store.stash.capacity <= 0:
            return (f"the {store.kind.lower()} has no animal hitched to pull it." if isinstance(store, Wagon)
                    else f"the {store.species} wears no pack saddle.")
        return f"won't fit -- {store.stash.free:g} kg free on the {store.name.lower()}."

    def _hitch_picked(self, wagon):
        """Drop an animal picked up by its header onto a wagon's header."""
        animal = next((o for o, loc in self.selected if loc == "hitch"), None)
        self.selected = []
        if animal is None:
            return
        if self.group.pulling(animal) is wagon:
            self.notice = f"the {animal.species} already pulls the {wagon.kind.lower()}."
        elif self.group.hitch(animal, wagon, swap=True):
            self.notice = f"the {animal.species} now pulls the {wagon.kind.lower()}."
        else:
            self.notice = f"the {animal.species} needs a Harness to pull anything."

    def _fit_tack(self, animal):
        """Put the first picked saddle or harness on `animal`; whatever it wore
        goes back into the pack the new one came from."""
        pick = next((p for p in self.selected if animal.can_wear(self._item_at(*p))), None)
        if pick is None:
            return
        src, loc = pick
        name, qty = self._take(src, loc)
        if qty > 1:
            src.give_to_pack(name, qty - 1)
        old = animal.take_tack()
        animal.give_to_tack(name)
        self.group.hitch_idle()
        if old:
            src.give_to_pack(old)
        self.selected = [p for p in self.selected if p != pick]
        self.notice = f"the {animal.species} now wears the {name}."

    def _ui_fonts(self):
        if self._F is None:
            self._F = ui_fonts()
        return self._F

    # ------------------------------------------------------------------ #
    # input                                                              #
    # ------------------------------------------------------------------ #
    def _source_at(self, px):
        if self._lock_at(px) is not None or self._dots_at(px) is not None:
            return None
        for rect, unit, loc in self.sources:
            if rect.collidepoint(px):
                return (unit, loc)
        return None

    def _zone_at(self, px):
        for rect, unit, zone in self.zones:
            if rect.collidepoint(px):
                return (unit, zone)
        return None

    def _begin_drag(self, src):
        mods = pygame.key.get_mods()
        if mods & (pygame.KMOD_SHIFT | pygame.KMOD_CTRL):
            if src not in self.selected:
                self.selected.append(src)
            return
        if src not in self.selected:
            self.selected = [src]

    def handle_event(self, event):
        if self.editing_name and event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.group.name = self.name_buf.strip() or None
                self.editing_name = False
            elif event.key == pygame.K_ESCAPE:
                self.editing_name = False
            elif event.key == pygame.K_BACKSPACE:
                self.name_buf = self.name_buf[:-1]
            elif event.unicode and len(self.name_buf) < 24 and event.unicode.isprintable():
                self.name_buf += event.unicode
            return

        if self.editing_search and event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.editing_search = False
            elif event.key == pygame.K_ESCAPE:
                self.cargo_search = ""
                self.editing_search = False
                self._cargo_scroll = 0
            elif event.key == pygame.K_BACKSPACE:
                self.cargo_search = self.cargo_search[:-1]
                self._cargo_scroll = 0
            elif event.unicode and len(self.cargo_search) < 32 and event.unicode.isprintable():
                self.cargo_search += event.unicode
                self._cargo_scroll = 0
            return

        if (self.tab == "gear" and self.view == "cargo" and not self.editing_name
                and event.type == pygame.KEYDOWN and event.key == pygame.K_SLASH):
            self.editing_search = True
            return

        if event.type == pygame.MOUSEWHEEL:
            hy = getattr(event, 'y', 0)
            
            if self.tab == "gear" and self.view == "bags":
                if self._cols.wheel(event, over=False):
                    return

            if self.tab == "gear" and self._rail_rect and self._rail_rect.collidepoint(self.mouse):
                self._rail_scroll = max(0, min(self._rail_max_scroll,
                                               self._rail_scroll - hy * 40))
                return
            if (self.tab == "gear" and self.view == "cargo"
                    and self._cargo_rect and self._cargo_rect.collidepoint(self.mouse)):
                self._cargo_scroll = max(0, min(self._cargo_max_scroll,
                                                self._cargo_scroll - hy * 40))
                return

        if self._menu_event(event):
            return
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.close_sheet_on_click():
                return
            for rect, unit in getattr(self, "sheet_hits", []):
                if rect.collidepoint(event.pos):
                    self.open_sheet(unit)
                    return
        super().handle_event(event)

    def _click(self, pos):
        self._drop(pos, False, None)

    def _drop(self, px, dragging, src):
        if dragging:
            hit = self._zone_at(px)
            if hit is not None:
                self._give_many(*hit)
            return

        if self.tab == "gear" and self.view == "bags" and self._cols.click(px):
            return

        if self.back_rect is not None and self.back_rect.collidepoint(px):
            self.on_back()
            return

        if self._search_clear_rect is not None and self._search_clear_rect.collidepoint(px):
            self.cargo_search = ""
            self.editing_search = False
            self._cargo_scroll = 0
            return
        if self._search_rect is not None and self._search_rect.collidepoint(px):
            self.editing_search = True
            return
        elif self.view == "cargo" and not dragging:
            self.editing_search = False

        lock_hit = self._lock_at(px)
        if lock_hit is not None:
            lock_hit[0].toggle_lock(lock_hit[1])
            return

        dots_hit = self._dots_at(px)
        if dots_hit is not None:
            self._open_menu(px, self._menu_picks_for(dots_hit))
            return

        for rect, tab_id in self.tab_hits:
            if rect.collidepoint(px):
                self.tab, self.selected = tab_id, []
                return

        for key, rect in self.buttons:
            if rect.collidepoint(px):
                self._handle_button(key)
                return

        mods = pygame.key.get_mods()
        if not dragging and src is not None and mods & (pygame.KMOD_SHIFT | pygame.KMOD_CTRL):
            if src in self.selected:
                self.selected.remove(src)
            else:
                self.selected.append(src)
            return

        if self.selected:
            hit = self._zone_at(px)
            if hit is not None and dragging:
                self._give_many(*hit)
            elif not dragging:
                if src in self.selected:
                    self.selected.remove(src)
                elif src is not None:
                    self.selected = [src]
                else:
                    self.selected = []
            return

        # nothing carried -- a plain click on a rail row toggles its pin
        # instead of picking anything up (rail rows are drop zones, never
        # `sources`)
        for rect, unit in self._rail_hits:
            if rect.collidepoint(px):
                if unit in self.pinned:
                    self.pinned.remove(unit)
                else:
                    self.pinned.append(unit)
                return

        self.selected = [src] if src is not None else []

    def _toggle_ride(self, uid):
        unit = self._unit_by_uid.get(uid)
        if unit is None:
            return
        unit.afoot = not unit.afoot
        self.notice = (f"{unit.name} walks beside the wagon." if unit.afoot
                       else f"{unit.name} rides when there is room.")

    def _cycle_hitch(self, uid):
        animal = next((a for a in self.group.herd if a.uid == uid), None)
        if animal is None:
            return
        self.group.next_hitch(animal)
        pulled = self.group.pulling(animal)
        self.notice = (f"the {animal.species} pulls the {pulled.kind.lower()}." if pulled
                       else f"the {animal.species} is unhitched.")

    def _repair_wagon(self, uid):
        wagon = next((w for w in self.group.wagons if w.uid == uid), None)
        if wagon is None:
            return
        ok, events, _ = self.guild.repair_wagon(self.group.members, wagon, self.on_tick)
        if ok:
            self.group.hitch_idle()
        self.notice = "  ".join(events)

    def _release(self, uid):
        cap = next((c for c in self.group.captives if c.unit.uid == uid), None)
        if cap is not None:
            self.notice = captives.release(self.group, cap)

    def _handle_button(self, key):
        if key == "done":
            self.on_back()
        elif key.startswith("ride:"):
            self._toggle_ride(key.partition(":")[2])
        elif key.startswith("hitch:"):
            self._cycle_hitch(key.partition(":")[2])
        elif key.startswith("repair:"):
            self._repair_wagon(key.partition(":")[2])
        elif key.startswith("release:"):
            self._release(key.partition(":")[2])
        elif key == "distribute":
            self.group.distribute_load()
            self.notice = "Redistributed packs by carrying capacity."
        elif key == "clear_cargo_search":
            self.cargo_search = ""
            self.editing_search = False
            self._cargo_scroll = 0
        elif key == "treat_sickness":
            self._treat_sickness()
        elif key == "treat_poison":
            self._treat_poison()
        elif key == "campfire_cook":
            if self.group.has_campfire(self.guild.clock.seconds):
                if self.on_cook:
                    self.on_cook()
            elif self.group.can_light_campfire():
                self.group.light_campfire(self.guild.clock.seconds)
                self.notice = "Campfire lit! Burns for 4 hours."
                if self.on_cook:
                    self.on_cook()
            else:
                self.notice = "Campfire requires Flint and Steel, 1 Lumber and 1 Coal in the pack."
        elif key == "rename":
            self.editing_name = True
            self.name_buf = self.group.name or ""
        elif key == "view_bags":
            self.view, self.selected = "bags", []
        elif key == "view_cargo":
            self.view, self.selected = "cargo", []
        elif key == "send_to":
            self._open_menu(self._bulk_anchor, picks=list(self.selected))
        elif key == "split":
            self._open_split_prompt()
        elif key == "drop_selected":
            self._give_many(None, "discard")
            self.notice = "Thrown away."
        elif key == "wagon_prev":
            if self.group.wagons:
                self._wagon_idx = (self._wagon_idx - 1) % len(self.group.wagons)
        elif key == "wagon_next":
            if self.group.wagons:
                self._wagon_idx = (self._wagon_idx + 1) % len(self.group.wagons)

    def _poison_cases(self):
        """`(patient, giver)` pairs: a poisoned member who may take an Antidote now,
        and the member of the group (the patient first) holding one."""
        out = []
        for u in self.group.members:
            if u.can_take_antidote:
                giver = u.antidote_giver([m for m in self.group.members if m is not u])
                if giver:
                    out.append((u, giver))
        return out

    def _can_treat_poison(self):
        return bool(self._poison_cases())

    def _treat_poison(self):
        cases = self._poison_cases()
        if not cases:
            return
        patient, giver = cases[0]
        giver.remove_named(items.ANTIDOTE_ITEM)
        _, self.notice = patient.apply_antidote()

    def _can_treat_sickness(self):
        sick_members = [u for u in self.group.members if u.sick and not getattr(u, "medicine_attempted_today", False) and not getattr(u, "treated", False)]
        if not sick_members:
            return False
        
        for s in sick_members:
            healers = [u for u in self.group.members if u.first_aid_charges > 0 and u != s]
            if healers:
                return True
        return False

    def _treat_sickness(self):
        sick_members = [u for u in self.group.members if u.sick and not getattr(u, "medicine_attempted_today", False) and not getattr(u, "treated", False)]
        if not sick_members:
            return
        
        target = sick_members[0]
        healers = [u for u in self.group.members if u.first_aid_charges > 0 and u != target]
        if not healers:
            # If the only healer is the target, they can't treat themselves. But if there is another sick person, maybe we can treat them instead?
            # Find any sick member who is NOT the only healer.
            for s in sick_members:
                healers = [u for u in self.group.members if u.first_aid_charges > 0 and u != s]
                if healers:
                    target = s
                    break
            if not healers:
                self.notice = "No ally with a first-aid kit can treat this."
                return

        healer = max(healers, key=lambda u: u.mod_wisdom)
        healer.first_aid_charges -= 1
        target.medicine_attempted_today = True

        nat = data.d20()
        med_bonus = int(healer.talent_bonus("field_medic_bonus"))
        total = nat + healer.mod_wisdom + med_bonus
        
        if total >= data.FIRST_AID_DC:
            target.treated = True
            self.notice = f"{healer.name} successfully treated {target.name} (rolled {total})."
        else:
            self.notice = f"{healer.name} failed to treat {target.name} (rolled {total})."

    # ------------------------------------------------------------------ #
    # send-to / context menu                                             #
    # ------------------------------------------------------------------ #
    def _study_label(self, unit, target):
        verb = "stop studying" if unit.study_target == target.id else "study"
        return f"{verb} {target.name}"

    def _menu_picks_for(self, pick):
        return self.selected if pick in self.selected else [pick]

    def _menu_rows(self, picks):
        picks = [p for p in picks if self._item_at(*p) is not None]
        if not picks:
            return []
        self.selected = list(picks)

        rows = [("drop", "Drop", None)]
        solo_member = len(picks) == 1 and not self._is_store(picks[0][0])
        if solo_member and self._item_at(*picks[0]) in (data.CHEST_ITEM, data.MISSION_CHEST_ITEM):
            rows.append(("open", "OPEN THE CHEST", None))
        if solo_member and self._item_at(*picks[0]) == "Minor Healing Potion":
            rows.append(("drink", "Drink", None))
            
        if solo_member:
            unit, item = picks[0][0], self._item_at(*picks[0])
            spell = magic.spell_for_scroll(item) if item else None
            if spell and magic.can_study_spell(unit, spell):
                rows.append(("study", self._study_label(unit, spell), spell))
            lang = magic.language_for_dictionary(item) if item else None
            if lang and lang.name not in unit.languages:
                rows.append(("study", self._study_label(unit, lang), lang))

        # a member you'd only be handing their own pack items back to is a no-op
        owners = {id(p[0]) for p in picks}
        lift = len(owners) > 1 or any(isinstance(p[1], str) for p in picks)
        dests = [u for u in self._owners() if lift or id(u) not in owners]
        rows += [("member", f"to {u.name}", u.uid) for u in dests]

        return rows

    def _menu_run(self, picks, kind, arg):
        if kind == "open":
            unit, loc = picks[0]
            self._open_chest(unit, self._item_at(unit, loc))
        elif kind == "drink":
            self._drink_potion(picks[0][0])
        elif kind == "member":
            self.selected = list(picks)
            self._give_many(self._unit_by_uid[arg], "pack")
        elif kind == "study":
            unit = picks[0][0]
            if unit.study_target == arg.id:
                magic.end_study(unit)
            else:
                magic.begin_study(unit, arg.id, self.group.members)
            self.selected = []
        else:
            self.selected = list(picks)
            self._give_many(None, "discard")

    def _open_chest(self, unit, item):
        """Pick the lock right where the chest sits -- no move, no drop, just
        the roll. A miss costs nothing, so this never asks for confirmation.
        The Bankers' own sealed chest (`data.MISSION_CHEST_ITEM`) picks the
        same lock but fails its mission and marks a crime on a hit --
        `missions.open_mission_chest`, not `chest.try_open`."""
        sealed = item == data.MISSION_CHEST_ITEM
        opened, gems = (missions.open_mission_chest(self.guild, unit) if sealed
                       else chest.try_open(unit))
        if not opened:
            self.notice = f"{unit.name} can't pick the lock -- the chest is still there."
        elif sealed:
            self.notice = (f"{unit.name} breaks the Bankers' seal -- {gems} {data.GEM_ITEM} "
                           f"spill out, but the trust mission is ruined. Crime: {unit.crime}.")
        else:
            self.notice = f"{unit.name} picks the lock -- {gems} {data.GEM_ITEM} inside."
        self.selected = []

    def _drink_potion(self, unit):
        import random
        if unit.hp >= unit.hp_max:
            self.notice = f"{unit.name} is already at full health."
        else:
            unit.remove_named("Minor Healing Potion")
            heal = random.randint(1, 6)
            unit.hp = min(unit.hp_max, unit.hp + heal)
            self.notice = f"{unit.name} drinks a Minor Healing Potion, recovering {heal} HP."
        self.selected = []
