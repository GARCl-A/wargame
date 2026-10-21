"""Fog of war: what each side has seen during one fight.

A cell is `UNSEEN` (black), `SEEN` (seen before, out of sight now: terrain dimmed, no
units) or `VISIBLE`. The memory is the side's -- the squad shares what any of them saw --
and it is presentation only: it lives on the battle screen, starts empty on every board
and is never saved (a battle is never saved mid-fight). The ground objects of a seen cell
stay where they were last seen.
"""

UNSEEN, SEEN, VISIBLE = 0, 1, 2


class FogMemory:
    def __init__(self):
        self._seen = {}         # team -> {cell}
        self._ground = {}       # team -> {cell: [prop]} as last seen

    def seen(self, team):
        return self._seen.setdefault(team, set())

    def remember(self, team, visible, props=()):
        """`team` sees `visible` now; `props` are the ground objects on the board now."""
        self.seen(team).update(visible)
        ground = self._ground.setdefault(team, {})
        for cell in visible:
            ground.pop(cell, None)
        for p in props:
            if p["pos"] in visible:
                ground.setdefault(p["pos"], []).append(p)

    def reveal(self, team, cells):
        """Mark `cells` as seen without seeing them now (the squad walked its own half
        before a flag fight)."""
        self.seen(team).update(cells)

    def state(self, team, cell, visible):
        if cell in visible:
            return VISIBLE
        return SEEN if cell in self.seen(team) else UNSEEN

    def remembered_props(self, team, visible):
        """The ground objects last seen on cells that are out of sight now."""
        return [p for cell, props in self._ground.get(team, {}).items()
                if cell not in visible for p in props]
