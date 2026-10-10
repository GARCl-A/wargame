"""The loadout column of a group's own storage -- a wagon or an animal's back.

Shared by `group_screen` and `market_screen`: both show a wagon or an animal
beside the members as one more pack, in `ui.loadout_panel.column`'s dict shape.
"""

from . import items
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
              "kg": kg, "cap": cap,
              "pack": [(name, store.pack_tag(name), items.item_weight(name), qty, False, idx in selected)
                       for idx, (name, qty) in enumerate(store._base_inventory)]}
    if isinstance(store, Animal):
        pulled = group.pulling(store)
        job = (f"pulls {pulled.kind.lower()}" if pulled else "unhitched" if store.role == "draft"
               else store.role or "no tack")
        member["name"] = f"{store.species}  ·  {job}"
        member["tack"] = {"name": store.tack, "note": store.role,
                          "sel": "tack" in selected,
                          "accepts": any(store.can_wear(n) for n in carried)}
        if store.role == "draft" and group.wagons:
            member["action"] = {"label": f"PULLS {pulled.kind.upper()}  ·  NEXT" if pulled else "UNHITCHED  ·  HITCH",
                                "enabled": True}
    else:
        drawn_by = " + ".join(a.species for a in store.draft) or "no animals"
        aboard = f"  ·  {len(store.passengers)} riding" if store.passengers else ""
        member["name"] = f"{store.kind}  ·  {'broken' if store.broken else drawn_by}{aboard}"
        riders = (f"  ·  riding: {', '.join(u.name for u in store.passengers)} ({store.passenger_weight:.1f} kg)"
                  if store.passengers else "")
        member["status"] = {"text": f"HP {store.hp} / {store.hp_max}{riders}" + ("  ·  BROKEN" if store.broken else ""),
                            "danger": store.broken}
        if store.needs_repair:
            have = sum(u.count_of(wagon_mod.REPAIR_ITEM) for u in group.members)
            member["action"] = {"label": (f"REPAIR  ·  {store.repair_cost} {wagon_mod.REPAIR_ITEM}"
                                          f"  ·  {wagon_mod.REPAIR_HOURS} h"),
                                "enabled": have >= store.repair_cost}
    return member
