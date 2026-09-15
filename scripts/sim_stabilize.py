import sys
sys.path.append('c:/dev/wargame')
from gartok import battle, unit, campaign, guild, combatant, actions

# Mock the RNG to always succeed
from gartok import data
data.d20 = lambda: 20

# Create guild and units
g = guild.Guild(roster=[])
u1 = unit.Unit("player", name="Healer")
u2 = unit.Unit("player", name="DyingGuy")
from gartok import group
grp = group.Group([])
g.groups = [grp]
g.add_member(u1, grp)
g.add_member(u2, grp)

# Create a battle
b = battle.Battle([u1, u2], [])

# Down the second guy
c_healer = b.player_units[0]
c_dying = b.player_units[1]

c_dying.hp = 0
c_dying.status = "dying"

# Use stabilize action
print("Before:", c_dying.status)
actions.STABILIZE.execute(b, c_healer, c_dying)
print("After Stabilize:", c_dying.status)

# Check win condition
b._advance_turn()
print("Battle Winner:", b.winner)
print("After Advance Turn:", c_dying.status)

# Absorb battle
outcome = campaign.absorb_battle(g, [u1, u2], b)
print("Survived:", [u.name for u in outcome.survivors])
print("Fallen:", [u.name for u in outcome.fallen])
print("Guild Roster:", [u.name for u in g.roster])
print("Group Members:", [u.name for u in g.groups[0].members])

