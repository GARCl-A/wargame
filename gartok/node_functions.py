"""What a map node can offer: one entry per function, declared once.

A `world.Node` lists the ids it offers (`Node.functions`). Each entry here carries
what the rest of the game reads about that function: the interactive order kind
the map issues (`orders.INTERACTIVE_KINDS`; the group walks there, then `app`
opens the screen that plays it), the map button's label and an optional note
under it. `app.App._FUNCTION_OPENERS` holds the opener of each id -- it builds a
screen, so it cannot live in this pure module; a test keeps the two in step.
Adding a place that offers something already built is a line in `world.NODES`;
a new kind of service is one entry here plus its opener.

`absorbs` names functions this one hosts inside its own screen: the Library's
hub carries the shop as a tab, so a node with both gets one button, not two.
`label=None` is a function with no map button of its own (`work` draws a shift
picker, `trust` is reached through the Bankers' hub).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class NodeFunction:
    id: str
    order_kind: str | None = None
    label: str | None = None
    note: str | None = None
    absorbs: tuple = ()


FUNCTIONS = {f.id: f for f in (
    NodeFunction("shop", "market", "ENTER THE MARKET"),
    NodeFunction("recruit", "recruit", "ENTER THE TAVERN"),
    NodeFunction("prison", "prison", "VISIT THE PRISON"),
    NodeFunction("work"),
    NodeFunction("hunt", "hunt", "GO HUNTING",
                 note="spend the day hunting or foraging  ·  a pack may find you first"),
    NodeFunction("bank", "bank", "VISIT THE BANK"),
    NodeFunction("trust", "trust"),
    NodeFunction("tanner", "tanner", "VISIT THE TANNER"),
    NodeFunction("forge", "forge", "VISIT THE FORGE"),
    NodeFunction("apothecary", "apothecary", "VISIT THE APOTHECARY"),
    NodeFunction("stable", "stable", "VISIT THE STABLES"),
    NodeFunction("library", "library", "VISIT THE LIBRARY", absorbs=("shop",)),
    NodeFunction("property", "property", "VISIT THE PROPERTY"),
    NodeFunction("claim", "claim", "THE WILDS CLAIM"),
    NodeFunction("ledger", "ledger", "VISIT THE OUTPOST",
                 note="hand over what you're carrying, if anything's owed"),
    NodeFunction("ancient_ruins", "ancient_ruins", "ENTER THE ANCIENT RUINS",
                 note="Delve into the sunken library chambers (Lethal tactical battle)"),
)}


def offered(node):
    """The functions `node` offers, in registry order, minus those another one hosts."""
    present = [FUNCTIONS[f] for f in FUNCTIONS if f in node.functions]
    hosted = {a for f in present for a in f.absorbs}
    return [f for f in present if f.id not in hosted]


def order_kinds():
    return frozenset(f.order_kind for f in FUNCTIONS.values() if f.order_kind)
