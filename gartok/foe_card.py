"""Adapter: what `intel.known_fields` says of a foe, as the plain dict `ui/foe_panel` draws."""

from . import i18n, intel, wiki_terms


def _row(label, value, tip=None):
    return {"label": label, "value": value, "tip": tip}


def _talents_tip(talents):
    """One line per talent, then each keyword they name once, so twenty talents stay a short note."""
    glosses = dict.fromkeys(g for _, effect in talents for g in wiki_terms.glosses(effect))
    return "\n".join([i18n.t("foe_card.talents"), *(f"{n}: {e}" for n, e in talents), *glosses])


def _format(name, value):
    """-> `(text, tip)` for one learned field."""
    if name == "racial_ability":
        return value[0], wiki_terms.ability_tip(i18n.t("foe_card.racial_ability"), *value)
    if name == "attrs":
        return "  ".join(f"{abbr} {v}" for abbr, v in value), None
    if name in ("hp", "morale"):
        return f"{value[0]} / {value[1]}", None
    if name == "talents":
        shown = ", ".join(n for n, _ in value) or i18n.t("foe_card.none")
        return shown, _talents_tip(value) if value else None
    if name == "spells":
        return ", ".join(value) or i18n.t("foe_card.none"), None
    if name == "artifact":
        return value, "\n".join([value, i18n.t("foe_card.artifact")])
    if name == "damage_bonus":
        return f"{value:+}", None
    if name == "level":
        return f"{value}", None
    return str(value), None


def foe_card(known):
    """`known` is an `intel.Known`."""
    v = known.visible
    equipment = []
    if v["armor"]:
        equipment.append((i18n.lab("armour"), i18n.name("item", v["armor"])))
    if v["artifact"]:
        equipment.append((i18n.lab("artefact"), i18n.name("item", v["artifact"])))
    bands = []
    for label, need in intel.BANDS:
        rows = []
        for name, band_need in intel.FIELDS.items():
            if band_need != need or name not in known.fields:
                continue
            value = known.fields[name]
            shown, tip = (None, None) if value is None else _format(name, value)
            rows.append(_row(intel.label(name), shown, tip))
        bands.append({"label": label, "open": any(r["value"] is not None for r in rows), "rows": rows})
    read = (i18n.t("foe_card.not_read_yet") if known.margin is None
            else i18n.t("foe_card.int_read_on_dc", margin=known.margin, dc=known.dc))
    return {"name": v["name"], "race": v["race"], "size": v["size"], "alignment": v["alignment"],
            "conditions": v["conditions"], "steps": known.steps, "steps_max": intel.STEPS,
            "weapon": {"name": i18n.name("item", v["weapon"]), "tip": wiki_terms.item_tip(v["weapon"]), "action": v["weapon_action"],
                       "action_tip": wiki_terms.action_tip(v["weapon_action"])},
            "equipment": equipment, "read": read, "bands": bands}
