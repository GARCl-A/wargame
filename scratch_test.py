import pygame
from gartok.app import App
from gartok.apothecary_hub_screen import ApothecaryHubScreen
from gartok.group import Group

pygame.init()
pygame.display.set_mode((800, 600))
app = App()

# Setup a fake group
group = next(iter(app.guild.groups))

# Instantiate screen
screen = ApothecaryHubScreen(app.fonts, app.guild, group, lambda: None)
screen.mouse = (0, 0)
screen.draw(app.window)
print("Draw succeeded without crashing!")
pygame.quit()
