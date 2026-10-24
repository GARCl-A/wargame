"""The map, opened on a save: for now only the guild and where its groups stand, enough for the
shell to route a second screen. Step 8 of `docs/plans/web_frontend.md` fills it in."""

from typing import ClassVar

from .. import artwork, world
from .session import Session, asset_url


class MapSession(Session):
    screen = "map"
    GET: ClassVar[dict] = {"state": lambda s, q: s.state()}

    def __init__(self, guild, world_id=None):
        self.guild = guild
        self.world_id = world_id

    def state(self):
        g, clock = self.guild, self.guild.clock
        return {
            "meta": {"world": self.world_id, "name": g.name or "The Guild", "day": clock.day,
                     "hour": clock.hour_of_day, "banner": list(g.banner_color) if g.banner_color else None},
            "groups": [self._group(gr) for gr in g.groups],
        }

    def _group(self, gr):
        order = gr.order
        return {
            "name": gr.display_name,
            "node": world.node(gr.node).name,
            "order": None if order is None else {"kind": order.kind,
                                                 "dest": order.dest and world.node(order.dest).name},
            "members": [{"name": u.name, "leader": u is gr.leader,
                         "portrait": asset_url(artwork.portrait_path(u.race["name"],
                                                                     getattr(u, "portrait_id", None)))}
                        for u in gr.members],
        }
