"""Shared press / drag / drop plumbing for the item screens.

The guild and market screens both let you click an item to pick it up (click
again to drop it) or drag it straight onto a target, with shift/ctrl to gather
several first. This mixin owns the mechanical half -- telling a click from a
drag past a few pixels of slop, and pulling a batch of picks off their owners --
and calls back into the screen for the layout-specific parts:

- `_source_at(pos)` -> the pick under the cursor, or None
- `_begin_drag(src)` -> a press just became a drag (optional; default no-op)
- `_drop(pos, dragging, src)` -> resolve the release (the click / drop logic)

`_collect(picks)` pulls every ``(owner, loc)`` pick off its owner and returns
``(names, owners touched)``; pack rows come off highest index first so an earlier
removal doesn't shift the ones still to come. It needs ``self._take(owner, loc)``.

Mix in before `Screen` so this `handle_event` wins:
``class GuildScreen(DragSelectMixin, Screen)``.
"""

import pygame


class DragSelectMixin:
    DRAG_SLOP = 5                             # pixels of travel that turn a click into a drag

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._press = None                   # window pos of the current left-button press
        self._press_src = None               # the pick that press landed on, or None
        self._dragging = False               # promoted from a press once the mouse travels

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._press = event.pos
            self._press_src = self._source_at(event.pos)
            self._dragging = False
        elif (event.type == pygame.MOUSEMOTION and self._press is not None
              and self._press_src is not None and not self._dragging):
            if (abs(event.pos[0] - self._press[0])
                    + abs(event.pos[1] - self._press[1]) > self.DRAG_SLOP):
                self._dragging = True
                self._begin_drag(self._press_src)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self._press is None:
                return                       # release of a press we never saw
            dragging, src = self._dragging, self._press_src
            self._press = self._press_src = None
            self._dragging = False
            self._drop(event.pos, dragging, src)

    def _begin_drag(self, src):
        """A press just crossed the slop and became a drag. Screens override to
        narrow the selection to what's under the cursor."""

    def _collect(self, picks):
        by_owner = {}
        for owner, loc in picks:
            by_owner.setdefault(id(owner), (owner, []))[1].append(loc)
        names, touched = [], []
        for owner, locs in by_owner.values():
            touched.append(owner)
            ordered = [l for l in locs if isinstance(l, str)]
            ordered += sorted((l for l in locs if not isinstance(l, str)), reverse=True)
            for loc in ordered:
                got = self._take(owner, loc)
                if got is not None:
                    names.append(got)
        return names, touched
