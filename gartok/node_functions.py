"""What a map node can offer: one entry per function, declared once.

A `world.Node` lists the ids it offers (`Node.functions`). Each entry here carries
what the rest of the game reads about that function: the interactive order kind
the map issues (`orders.INTERACTIVE_KINDS`; the group walks there, then `app`
opens the screen that plays it), the map button's label and an optional note
under it. `app.App._FUNCTION_OPENERS` holds the opener of each id -- it builds a
screen, so it cannot live in this pure module; a test keeps the two in step.
Adding a place that offers something already built is a line in `world.NODES`;
a new kind of service is one entry here plus its opener.

`absorbs` names functions this one hosts inside its own screen: the hubs of the Library,
Smithy, Tannery and Apothecary carry the shop as a tab, so a node with both gets one button, not two.
`label=None` is a function with no map button of its own (`work` draws a shift
picker, `trust` and `farmer` are reached through their hub).
"""

from dataclasses import dataclass

from . import i18n


@dataclass(frozen=True)
class NodeFunction:
    id: str
    order_kind: str | None = None
    absorbs: tuple = ()

    @property
    def label(self):
        return i18n.name("node_function", self.id) if i18n.has(f"name.node_function.{self.id}") else None

    @property
    def note(self):
        return i18n.desc("node_function", self.id) or None


FUNCTIONS = {f.id: f for f in (
    NodeFunction("shop", "market"),
    NodeFunction("recruit", "recruit", absorbs=("shop",)),
    NodeFunction("prison", "prison"),
    NodeFunction("work"),
    NodeFunction("hunt", "hunt"),
    NodeFunction("bank", "bank"),
    NodeFunction("trust", "trust"),
    NodeFunction("tanner", "tanner", absorbs=("shop",)),
    NodeFunction("forge", "forge", absorbs=("shop",)),
    NodeFunction("carpenter", "carpenter", absorbs=("shop",)),
    NodeFunction("apothecary", "apothecary", absorbs=("shop",)),
    NodeFunction("stable", "stable", absorbs=("shop",)),
    NodeFunction("farmer"),
    NodeFunction("library", "library", absorbs=("shop",)),
    NodeFunction("property", "property"),
    NodeFunction("claim", "claim"),
    NodeFunction("ledger", "ledger"),
    NodeFunction("ox_hunt", "ox_hunt"),
    NodeFunction("shrine", "shrine"),
    NodeFunction("ancient_ruins", "ancient_ruins"),
    NodeFunction("skirmish", "skirmish"),
    NodeFunction("camp_fight", "camp_fight"),
    NodeFunction("ogre_fight", "ogre_fight"),
    NodeFunction("serpents_nest", "serpents_nest"),
    NodeFunction("dragon_lair", "dragon_lair"),
    NodeFunction("cult_ritual", "cult_ritual"),
)}


def offered(node):
    """The functions `node` offers, in registry order, minus those another one hosts."""
    present = [FUNCTIONS[f] for f in FUNCTIONS if f in node.functions]
    hosted = {a for f in present for a in f.absorbs}
    return [f for f in present if f.id not in hosted]


def order_kinds():
    return frozenset(f.order_kind for f in FUNCTIONS.values() if f.order_kind)
