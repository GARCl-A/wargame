"""What pygame's map inspector adds to `map_view.MapView`: the blocks painted in the palette,
the auto-win of an ambush, the REST rows and the bottom buttons (`MapInspectorMixin`, mixed into
`MapScreen`)."""

from . import economy, rest
from .map_view import STANCE_NOTES, MapView
from .ui.tokens import T

TONE_COLORS = {"bad": T.BLOOD, "warn": T.BRASS, "good": T.GREEN, "faint": T.TX_FAINT}


class MapInspectorMixin(MapView):
    def _inspector_content(self, g, here):
        blocks = super()._inspector_content(g, here)
        if self._group_blocked(g) and self.autowin_estimator.result and self.autowin_estimator.result.eligible:
            blocks.append({"type": "section", "label": "swift resolution"})
            blocks.append({"type": "button", "key": "autowin_ambush",
                           "label": "AUTO-WIN (100% - NO XP)", "primary": True})
        return blocks

    @staticmethod
    def _painted(blocks):
        return [{**b, "color": TONE_COLORS[b["tone"]]} if "tone" in b else b for b in blocks]

    @staticmethod
    def _rest_row(key, label, plan, eaters=1):
        """One REST row: what it takes and what it costs (`eaters` mouths), or why it is off."""
        if not plan.available:
            return {"type": "button", "key": key, "label": label, "sub": plan.reason,
                    "tooltip": plan.reason, "enabled": False, "gap_before": 2, "height": 32}
        rations = plan.meals * eaters
        meals = "no meal" if rations == 0 else f"{rations} meal{'s' * (rations != 1)} in all"
        if key != "rest:full":
            return {"type": "button", "key": key, "label": f"{label}  ·  {meals}", "gap_before": 2, "height": 26}
        who = f"{plan.worst[0]} {plan.worst[1]}/{plan.worst[2]}"
        head = "UNTIL RATIONS HIT THE FLOOR" if plan.capped else label
        tooltip = None
        if plan.capped:
            who += f"  ·  {plan.short_days} more day{'s' * (plan.short_days != 1)} of rations to be full"
            tooltip = f"Rations run out before full health ({plan.short_days} more day{'s' * (plan.short_days != 1)} needed)"
        return {"type": "button", "key": key, "gap_before": 2, "height": 32,
                "label": f"{head}  ·  {rest.format_hours(plan.hours)}",
                "sub": f"{meals}  ·  {who}", "tooltip": tooltip}

    def _inspector_bottom(self, g):
        """MANAGE GEAR/REST only apply to a band that's actually here to act on
        them; the CTA (`_footer_cta`) is the map's own "what's next" pointer,
        not about `g` specifically, so it's always appended regardless."""
        items = []
        if not (g.busy or self._group_blocked(g)):
            items.append({"type": "button", "key": "manage_group", "label": "MANAGE GEAR & QUESTS", "height": 32})
            if self.on_cook is not None:
                if g.has_campfire(self.guild.clock.seconds):
                    left = g.campfire_hours_left(self.guild.clock.seconds)
                    items.append({"type": "button", "key": "campfire_cook",
                                  "label": f"CAMPFIRE COOKING ({left:g}h)", "primary": True,
                                  "gap_before": 2, "height": 32})
                else:
                    missing = []
                    if not any(u.has_item(economy.FIELD_CAMPFIRE_TOOL) for u in (*g.members, *g.stores)):
                        missing.append(economy.FIELD_CAMPFIRE_TOOL)
                    if sum(u.unlocked_of(economy.FIELD_CAMPFIRE_LUMBER) for u in g.members) < 1:
                        missing.append("1 Lumber")
                    if sum(u.unlocked_of(economy.FIELD_CAMPFIRE_COAL) for u in g.members) < 1:
                        missing.append("1 Coal")
                    sub = "burns 4h · " + (f"needs {', '.join(missing)}" if missing else "ready to light")
                    items.append({"type": "button", "key": "campfire_cook",
                                  "label": "LIGHT CAMPFIRE & COOK", "enabled": not missing,
                                  "sub": sub, "gap_before": 2, "height": 32})
            hurt = [u for u in g.members if u.hp < u.hp_max or u.sick or u.poisoned]
            if hurt:
                items.append({"type": "wrapped_text", "color": T.BRASS, "gap_before": T.S,
                              "text": f"{len(hurt)} wounded, sick or poisoned: REST, or the Medic "
                                      "at the Apothecary treats them at once."})
            items.append({"type": "button", "key": "stance", "gap_before": 2, "height": 32,
                          "label": f"TRAVEL: {g.stance.upper()}",
                          "sub": STANCE_NOTES[g.stance]})
            # nothing may move the clock past an unresolved event
            paused = self._pending_event is not None
            starving = g.rations == 0 and not paused
            items.append({"type": "button", "key": "rest_menu",
                          "label": "REST (OPEN)  ▴" if self._rest_open else "REST  ▾",
                          "gap_before": T.S,
                          "primary": (self._rest_urgent(g) or self._rest_open) and not paused,
                          "danger": starving, "enabled": not paused, "height": 32})
            if self._rest_open and not paused:
                items += [self._rest_row(k, label, plan, len(g.members)) for k, label, plan in self._rest_plans(g)]
        key, label, danger, enabled = self._footer_cta()
        items.append({"type": "button", "key": key, "label": label, "gap_before": T.S,
                     "primary": enabled, "danger": danger, "enabled": enabled, "height": 36})
        return items
