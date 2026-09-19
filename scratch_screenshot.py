import pygame
from gartok.loot_screen import LootScreen
from gartok.unit import Unit
from gartok.guild import Guild
from gartok.ui.tokens import fonts as Fonts
import sys

pygame.init()
screen = pygame.display.set_mode((1280, 800))
F = Fonts()

u = Unit("Adelio")
u.equipped_weapon = "Dagger"
u._base_inventory = [("Torch", 1), ("Rope", 2)]
g = Guild([u])

pool = ["Axe", "Axe", "Rope", "Bandage"]

ls = LootScreen(F, g, [u], pool, lambda: None)
ls.mouse = (100, 100)
ls.draw(screen)

pygame.image.save(screen, "loot_screen_shot.png")
sys.exit(0)
