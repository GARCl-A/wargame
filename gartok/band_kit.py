"""One band's kit, with no pygame: the moves between its members, animals and wagons (a hand,
the armour, a pack, an animal's tack, an animal hitched to a wagon), the item menu (drop, open
a chest, drink, study, hand to whom), the split, and the band's own buttons (ride, hitch, repair,
release, distribute, treat sickness and poison, the campfire). `web/guild_session.py` holds one
per picked band. An item moves only inside the band: a trade never crosses places.
"""

import random

from . import captives, chest, data, i18n, items, magic, missions, stints
from .animals import Animal
from .loadout_move import LoadoutMoveMixin
from .wagon import REPAIR_HOURS, Wagon


class BandKit(LoadoutMoveMixin):
    def __init__(self, guild, group):
        self.guild = guild
        self.group = group
        self.selected = []                   # [(owner, loc), ...]: loc is a slot name or a pack index
        self.notice = None
        self._unit_by_uid = self._owners_by_uid()

    def _owners(self):
        """Everything here that holds a pack: the members, the animals, the wagons."""
        return [*self.group.members, *self.group.herd, *self.group.wagons]

    def _owners_by_uid(self):
        return {o.uid: o for o in self._owners()}

    @staticmethod
    def _is_store(owner):
        """The group's own storage (an animal's back, a wagon) -- not a person."""
        return isinstance(owner, (Animal, Wagon))

    @staticmethod
    def _splittable(pick):
        """`(owner, idx)` when `pick` is a pack stack of two or more that splits."""
        owner, loc = pick
        if not isinstance(loc, int) or not hasattr(owner, "split_pack"):
            return None
        inv = owner._base_inventory
        return (owner, loc) if loc < len(inv) and inv[loc][1] > 1 else None

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
            return (i18n.t("band_kit.has_no_animal_hitched_to", lower=store.ref(lower=True)) if isinstance(store, Wagon)
                    else i18n.t("band_kit.wears_no_pack_saddle", species=store.ref()))
        return i18n.t("band_kit.won_t_fit_kg_free", free=store.stash.free, lower=store.name.lower())

    def _hitch_picked(self, wagon):
        """Drop an animal picked up by its header onto a wagon's header."""
        animal = next((o for o, loc in self.selected if loc == "hitch"), None)
        self.selected = []
        if animal is None:
            return
        if self.group.pulling(animal) is wagon:
            self.notice = i18n.t("band_kit.already_pulls", species=animal.ref(), lower=wagon.ref(lower=True))
        elif self.group.hitch(animal, wagon, swap=True):
            self.notice = i18n.t("band_kit.now_pulls", species=animal.ref(), lower=wagon.ref(lower=True))
        else:
            self.notice = i18n.t("band_kit.needs_harness_to_pull_anything", species=animal.ref())

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
        self.notice = i18n.t("band_kit.now_wears", species=animal.ref(), name=i18n.Ref("item", name))

    # ------------------------------------------------------------------ #
    # the band's buttons                                                  #
    # ------------------------------------------------------------------ #
    def _toggle_ride(self, uid):
        unit = self._unit_by_uid.get(uid)
        if unit is None:
            return
        unit.afoot = not unit.afoot
        self.notice = (i18n.t("band_kit.walks_beside_wagon", name=unit.name) if unit.afoot
                       else i18n.t("band_kit.rides_when_there_is_room", name=unit.name))

    def _cycle_hitch(self, uid):
        animal = next((a for a in self.group.herd if a.uid == uid), None)
        if animal is None:
            return
        self.group.next_hitch(animal)
        pulled = self.group.pulling(animal)
        self.notice = (i18n.t("band_kit.pulls", species=animal.ref(), lower=pulled.ref(lower=True)) if pulled
                       else i18n.t("band_kit.is_unhitched", species=animal.ref()))

    def _repair_wagon(self, uid):
        """-> the repair's stint for the band, or None when it cannot start (the notice says why)."""
        wagon = next((w for w in self.group.wagons if w.uid == uid), None)
        if wagon is None:
            return None
        if self.group.busy:
            self.notice = i18n.t("band_kit.is_busy_repair_waits_until", display_name=self.group.display_name)
            return None
        short = self.guild.repair_short(self.group.members, wagon)
        if short:
            self.notice = short
            return None
        self.guild.repair_lumber(self.group.members, wagon)
        return stints.order("repair", REPAIR_HOURS, self.group.members, wagon=wagon.uid)

    def _release(self, uid):
        cap = next((c for c in self.group.captives if c.unit.uid == uid), None)
        if cap is not None:
            self.notice = captives.release(self.group, cap)

    def _handle_button(self, key):
        if key.startswith("ride:"):
            self._toggle_ride(key.partition(":")[2])
        elif key.startswith("hitch:"):
            self._cycle_hitch(key.partition(":")[2])
        elif key.startswith("repair:"):
            return self._repair_wagon(key.partition(":")[2])
        elif key.startswith("release:"):
            self._release(key.partition(":")[2])
        elif key == "distribute":
            self.group.distribute_load()
            self.notice = i18n.t("band_kit.redistributed_packs_by_carrying_capacity")
        elif key == "treat_sickness":
            self._treat_sickness()
        elif key == "treat_poison":
            self._treat_poison()
        elif key == "campfire_cook":
            if self.group.has_campfire(self.guild.clock.seconds):
                return
            if self.group.can_light_campfire():
                self.group.light_campfire(self.guild.clock.seconds)
                self.notice = i18n.t("band_kit.campfire_lit_burns_for_hours")
            else:
                self.notice = i18n.t("band_kit.campfire_requires_flint_and_steel")

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

    def _sick(self):
        return [u for u in self.group.members if u.sick and not getattr(u, "medicine_attempted_today", False)
                and not getattr(u, "treated", False)]

    def _healers(self, patient):
        return [u for u in self.group.members if u.first_aid_charges > 0 and u != patient]

    def _can_treat_sickness(self):
        return any(self._healers(s) for s in self._sick())

    def _treat_sickness(self):
        """The first sick member someone else can tend; a member never treats themself."""
        target = next((s for s in self._sick() if self._healers(s)), None)
        if target is None:
            self.notice = i18n.t("band_kit.no_ally_with_first_aid")
            return
        healer = max(self._healers(target), key=lambda u: u.mod_wisdom)
        healer.first_aid_charges -= 1
        target.medicine_attempted_today = True
        total = data.d20() + healer.mod_wisdom + int(healer.talent_bonus("field_medic_bonus"))
        if total >= data.FIRST_AID_DC:
            target.treated = True
            self.notice = i18n.t("band_kit.successfully_treated_rolled", name=healer.name, patient=target.name, total=total)
        else:
            self.notice = i18n.t("band_kit.failed_to_treat_rolled", name=healer.name, patient=target.name, total=total)

    # ------------------------------------------------------------------ #
    # the item menu                                                       #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _study_label(unit, target):
        verb = i18n.t("band_kit.stop_studying") if unit.study_target == target.id else "study"
        return f"{verb} {target.name}"

    def _menu_rows(self, picks):
        picks = [p for p in picks if self._item_at(*p) is not None]
        if not picks:
            return []
        self.selected = list(picks)

        rows = [("drop", i18n.t("band_kit.drop"), None)]
        solo_member = len(picks) == 1 and not self._is_store(picks[0][0])
        if solo_member and self._item_at(*picks[0]) in (data.BOX_OF_GEMS_ITEM, data.MISSION_CHEST_ITEM):
            rows.append(("open", i18n.t("band_kit.open_chest"), None))
        if solo_member and self._item_at(*picks[0]) == "Minor Healing Potion":
            rows.append(("drink", i18n.t("band_kit.drink"), None))

        if solo_member:
            unit, item = picks[0][0], self._item_at(*picks[0])
            spell = magic.spell_for_scroll(item) if item else None
            if spell and magic.can_study_spell(unit, spell):
                rows.append(("study", self._study_label(unit, spell), spell))
            recipe = magic.recipe_for_paper(item) if item else None
            if recipe and magic.can_study(unit, recipe.id):
                rows.append(("study", self._study_label(unit, recipe), recipe))
            lang = magic.language_for_dictionary(item) if item else None
            if lang and lang.name not in unit.languages:
                rows.append(("study", self._study_label(unit, lang), lang))

        # a member you'd only be handing their own pack items back to is a no-op
        owners = {id(p[0]) for p in picks}
        lift = len(owners) > 1 or any(isinstance(p[1], str) for p in picks)
        dests = [u for u in self._owners() if lift or id(u) not in owners]
        rows += [("member", i18n.t("band_kit.to", name=u.name), u.uid) for u in dests]
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
        the roll. The Bankers' own sealed chest (`data.MISSION_CHEST_ITEM`) picks the
        same lock but fails its mission and marks a crime on a hit."""
        sealed = item == data.MISSION_CHEST_ITEM
        opened, gems = (missions.open_mission_chest(self.guild, unit) if sealed
                        else chest.try_open(unit))
        if not opened:
            self.notice = i18n.t("band_kit.can_t_pick_lock_chest", name=unit.name)
        elif sealed:
            self.notice = (i18n.t("band_kit.breaks_bankers_seal_spill_out", name=unit.name, gems=gems, gem_item=data.GEM_ITEM, crime=unit.crime))
        else:
            self.notice = i18n.t("band_kit.picks_lock_inside", name=unit.name, gems=gems, gem_item=data.GEM_ITEM)
        self.selected = []

    def _drink_potion(self, unit):
        if unit.hp >= unit.hp_max:
            self.notice = i18n.t("band_kit.is_already_at_full_health", name=unit.name)
        else:
            unit.remove_named("Minor Healing Potion")
            heal = random.randint(1, 6)
            unit.hp = min(unit.hp_max, unit.hp + heal)
            self.notice = i18n.t("band_kit.drinks_minor_healing_potion_recovering", name=unit.name, heal=heal)
        self.selected = []
