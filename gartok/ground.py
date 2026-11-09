"""Things that sit on the board but are not units.

`GroundObject` replaces the old dict-with-a-`kind`-key: a dropped weapon, shield or
torch lying on a cell. `Creature` is a neutral, non-controllable body (the
Shepherd's sheep) that only blocks its cell and gets drawn.

A new kind of ground object = a new `kind` string plus wherever the rules react
to it; consumers ask `obj.kind` / `obj.is_weapon` / `obj.is_torch`.
"""


class GroundObject:
    WEAPON = "weapon"
    TORCH = "torch"
    SHIELD = "shield"
    TRAP = "trap"
    RELIC = "relic"
    CHEST = "chest"
    DISK = "floating_disk"

    def __init__(self, kind, pos, weapon_name=None, trap_type=None, trap_owner_team=None,
                 item_name=None, contents=None, elevation=0, trap_group=None, owner=None):
        self.kind = kind
        self.owner = owner                  # the combatant that dropped it: it gets its kit back if it lives
        self.pos = pos
        self.weapon_name = weapon_name
        self.trap_type = trap_type
        self.trap_owner_team = trap_owner_team
        self.trap_group = trap_group        # cells of one big trap (a web) share this and spring together
        self.item_name = item_name
        self.contents = list(contents) if contents else []
        self.elevation = int(elevation)
        self.fixture = False                # part of the place (a dungeon's chest): taken by hand, never field loot

    @classmethod
    def weapon(cls, pos, weapon_name, owner=None):
        return cls(cls.WEAPON, pos, weapon_name, owner=owner)

    @classmethod
    def torch(cls, pos, owner=None):
        return cls(cls.TORCH, pos, owner=owner)

    @classmethod
    def shield(cls, pos, shield_name, owner=None):
        return cls(cls.SHIELD, pos, item_name=shield_name, owner=owner)

    @classmethod
    def trap(cls, pos, trap_type, trap_owner_team, group=None):
        return cls(cls.TRAP, pos, trap_type=trap_type, trap_owner_team=trap_owner_team,
                   trap_group=group)

    @classmethod
    def relic(cls, pos, item_name):
        return cls(cls.RELIC, pos, item_name=item_name)

    @classmethod
    def chest(cls, pos, contents):
        return cls(cls.CHEST, pos, contents=contents)

    @classmethod
    def disk(cls, pos, elevation=0):
        return cls(cls.DISK, pos, elevation=elevation)

    @property
    def is_weapon(self):
        return self.kind == self.WEAPON

    @property
    def is_torch(self):
        return self.kind == self.TORCH

    @property
    def is_shield(self):
        return self.kind == self.SHIELD

    @property
    def is_trap(self):
        return self.kind == self.TRAP

    @property
    def is_relic(self):
        return self.kind == self.RELIC

    @property
    def is_chest(self):
        return self.kind == self.CHEST

    @property
    def is_disk(self):
        return self.kind == self.DISK

    def __repr__(self):
        extra = f" {self.weapon_name or self.item_name or self.contents}" if (self.weapon_name or self.item_name or self.contents) else ""
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
