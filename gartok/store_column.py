"""The loadout column of a group's own storage -- a wagon or an animal's back.

A wagon or an animal shows beside the members as one more pack; the web's shop and vault
tabs read `store_dict`.
"""

from . import i18n, items
from . import wagon as wagon_mod
from .animals import Animal
from .wagon import Wagon


def is_store(owner):
    """The group's own storage (an animal's back, a wagon) -- not a person."""
    return isinstance(owner, (Animal, Wagon))


def store_dict(group, store, selected, carried):
    """A column with no sheet and no hands, just a pack (and, for an animal,
    the tack slot). `selected` is the set of this store's picked locs."""
    kg, cap = store.load, store.carry_normal
    if isinstance(store, Wagon):
        kg, cap = kg + store.passenger_weight, store.budget
    member = {"role": "wagon", "pending_picks": False, "no_sheet": True,
              "kg": kg, "normal": cap, "max": cap,
              "pack": [(name, store.pack_tag(name), items.item_weight(name), qty,
                        store.locked_of(name) > 0, idx in selected)
                       for idx, (name, qty) in enumerate(store._base_inventory)]}
    if isinstance(store, Animal):
        pulled = group.pulling(store)
        job = (i18n.t("store_column.pulls", lower=pulled.kind.lower()) if pulled else i18n.t("animals.unhitched") if store.role == "draft"
               else store.role or i18n.t("store_column.no_tack"))
        member["name"] = f"{store.species}  ·  {job}"
        member["tack"] = {"name": store.tack, "note": store.role,
                          "sel": "tack" in selected,
                          "accepts": any(store.can_wear(n) for n in carried)}
        if store.role == "draft" and group.wagons:
            member["action"] = {"label": i18n.t("store_column.pulls_next", upper=pulled.kind.upper()) if pulled else "UNHITCHED  ·  HITCH",
                                "enabled": True}
    else:
        drawn_by = " + ".join(a.species for a in store.draft) or i18n.t("store_column.no_animals")
        aboard = i18n.t("store_column.riding", len=len(store.passengers)) if store.passengers else ""
        member["name"] = f"{store.kind}  ·  {'broken' if store.broken else drawn_by}{aboard}"
        riders = (i18n.t("store_column.riding_kg", join=', '.join(u.name for u in store.passengers), passenger_weight=store.passenger_weight)
                  if store.passengers else "")
        member["status"] = {"text": i18n.t("store_column.hp", hp=store.hp, hp_max=store.hp_max, riders=riders) + ("  ·  BROKEN" if store.broken else ""),
                            "danger": store.broken}
        if store.needs_repair:
            have = sum(u.count_of(wagon_mod.REPAIR_ITEM) for u in group.members)
            member["action"] = {"label": (f"REPAIR  ·  {store.repair_cost} {wagon_mod.REPAIR_ITEM}"
                                          f"  ·  {wagon_mod.REPAIR_HOURS} h"),
                                "enabled": have >= store.repair_cost}
    return member
