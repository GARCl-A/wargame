"""The Editor's pygame window: the character creator, the map editor and the combat lab, apart from the
game (which runs in the browser). `python main.py --editor` opens it."""

import pygame

from . import combat_lab, sound
from .battle_screen import BattleScreen
from .char_editor_screen import CharEditorScreen
from .combat_lab_screen import CombatLabScreen
from .combat_log import CombatLog
from .editor_menu_screen import EditorMenuScreen
from .map_editor_screen import MapEditorScreen
from .ui.tokens import T
from .ui.tokens import fonts as ui_fonts

START_SIZE = (1212, 832)


class EditorApp:
    def __init__(self):
        pygame.init()
        sound.enable()
        pygame.display.set_caption("GARTOK Editor")
        self.window = pygame.display.set_mode(START_SIZE, pygame.RESIZABLE | pygame.WINDOWMAXIMIZED)
        self.clock = pygame.time.Clock()
        self.ui_fonts = ui_fonts()
        self._running = True
        self._start_editor()

    def _start_editor(self):
        self.scene = EditorMenuScreen(self.ui_fonts,
                                      on_character=self._open_char_editor,
                                      on_scenario=self._open_map_editor,
                                      on_combat_lab=self._open_combat_lab,
                                      on_back=self._quit)

    def _open_combat_lab(self):
        self.scene = CombatLabScreen(self.ui_fonts, on_start=self._start_lab_fight,
                                     on_back=self._start_editor)

    def _start_lab_fight(self, setup):
        battle, meta = combat_lab.build(setup["fight"], setup["level"], setup["squad"])
        path = combat_lab.log_path(setup["name"])
        battle.record_to(CombatLog(path, {"source": "lab", "name": setup["name"], **meta}, setup["controllers"]))
        self.scene = BattleScreen(self.ui_fonts, battle, on_battle_end=lambda _b: self._open_combat_lab())

    def _open_char_editor(self):
        self.scene = CharEditorScreen(self.ui_fonts, on_back=self._start_editor)

    def _open_map_editor(self):
        self.scene = MapEditorScreen(self.ui_fonts, on_back=self._start_editor)

    def _quit(self):
        self._running = False

    def run(self):
        while self._running:
            dt = self.clock.tick(60)
            self.scene.mouse = pygame.mouse.get_pos()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self._running = False
                elif event.type == pygame.VIDEORESIZE:
                    self.window = pygame.display.set_mode(event.size, pygame.RESIZABLE)
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    if not self.scene.handle_escape() and isinstance(self.scene, EditorMenuScreen):
                        self._quit()
                else:
                    self.scene.handle_event(event)
            self.scene.update(dt)
            self.window.fill(T.TABLE)
            self.scene.draw(self.window)
            pygame.display.flip()
        pygame.quit()
