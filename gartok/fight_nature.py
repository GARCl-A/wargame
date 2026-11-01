"""What kind of fight a fight is, declared by the code that starts it, for the rules only some
fights get (the win-chance check of an ambush). The test: *if the group were twice as strong, would
this attacker still come?* The table of every fight and its nature is in `RULES.md`, *Where fights
come from*."""

SOUGHT = "sought"              # the group went in: the player chose the risk
OPPORTUNIST = "opportunist"    # the pack picks its prey by the odds, so a strong group may be let be
DETERMINED = "determined"      # it comes whatever the odds: the law, the land, a quest's foe

NATURES = (SOUGHT, OPPORTUNIST, DETERMINED)
