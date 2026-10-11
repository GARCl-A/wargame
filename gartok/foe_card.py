"""Adapter: what `intel.known_fields` says of a foe, as the plain dict `ui/foe_panel` draws."""

from . import intel


def _row(label, value, tip=None):
    return {"label": label, "value": value, "tip": tip}


def _format(name, value):
    """-> `(text, tip)` for one learned field."""
    if name == "racial_ability":
        return value[0], value
    if name == "attrs":
        return "  ".join(f"{abbr} {v}" for abbr, v in value), None
    if name == "hp":
        return f"{value[0]} / {value[1]}", None
    if name == "talents":
        shown = ", ".join(n for n, _ in value) or "none"
        return shown, (("Talents", "\n".join(f"{n}: {e}" for n, e in value)) if value else None)
    if name == "spells":
        return ", ".join(value) or "none", None
    if name == "artifact":
        return value, ("Artefact", value)
    if name == "damage_bonus":
        return f"{value:+}", None
    if name == "level":
        return f"{value}", None
    return str(value), None


def foe_card(known):
    """`known` is an `intel.Known`."""
    v = known.visible
    equipment = [("weapon", v["weapon"] or "unarmed")]
    if v["armor"]:
        equipment.append(("armour", v["armor"]))
    if v["artifact"]:
        equipment.append(("artefact", v["artifact"]))
    bands = []
    for label, need in intel.BANDS:
        rows = []
        for name, band_need in intel.FIELDS.items():
            if band_need != need or name not in known.fields:
                continue
            value = known.fields[name]
            shown, tip = (None, None) if value is None else _format(name, value)
            rows.append(_row(intel.LABELS[name], shown, tip))
        bands.append({"label": label, "open": any(r["value"] is not None for r in rows), "rows": rows})
    read = ("not read yet" if known.margin is None
            else f"INT read {known.margin:+} on DC {known.dc}")
    return {"name": v["name"], "race": v["race"], "size": v["size"], "alignment": v["alignment"],
            "conditions": v["conditions"], "steps": known.steps, "steps_max": intel.STEPS,
            "equipment": equipment, "read": read, "bands": bands}
