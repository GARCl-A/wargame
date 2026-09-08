"""Things that sit on the board but are not units.

`GroundObject` replaces the old dict-with-a-`tipo`-key: a dropped weapon or a
torch lying on a cell. `Creature` is a neutral, non-controllable body (the
Shepherd's sheep) that only blocks its cell and gets drawn.

A new kind of ground object = a new `kind` string plus wherever the rules react
to it; consumers ask `obj.kind` / `obj.is_weapon` / `obj.is_torch` instead of
`o.get("tipo", "arma")`.
"""


class GroundObject:
    WEAPON = "weapon"
    TORCH = "torch"

    def __init__(self, kind, pos, weapon_name=None):
        self.kind = kind
        self.pos = pos
        self.weapon_name = weapon_name

    @classmethod
    def weapon(cls, pos, weapon_name):
        return cls(cls.WEAPON, pos, weapon_name)

    @classmethod
    def torch(cls, pos):
        return cls(cls.TORCH, pos)

    @property
    def is_weapon(self):
        return self.kind == self.WEAPON

    @property
    def is_torch(self):
        return self.kind == self.TORCH

    def __repr__(self):
        extra = f" {self.weapon_name}" if self.weapon_name else ""
        return f"<GroundObject {self.kind}{extra} @ {self.pos}>"


class Creature:
    """Neutral body on the field: no turn, not a target, does not count for victory."""

    def __init__(self, name, token, pos, footprint=1):
        self.name = name
        self.token = token
        self.pos = pos
        self.footprint = footprint

    def __repr__(self):
        return f"<Creature {self.name} @ {self.pos}>"
