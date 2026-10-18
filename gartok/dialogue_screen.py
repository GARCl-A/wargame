"""The dialogue before a fight (`dialogue.py`): the foe's leader says their piece, the player
picks who answers and how, the dice say how it went.

One screen for every encounter that talks: an ambush on the road, at work or on a supply run,
the City guard, a Wildfire focus. `on_decided(result)` fires the moment a roll ends it (the
caller stores it on the pending order, so a reload cannot roll again); `on_done(result)` when
the player presses the result's button. A `decided` result opens the screen already showing it.
"""

import pygame

from . import world
from .screen import Screen
from .ui.dialogue_panel import draw_dialogue
from .ui.primitives import header, set_pointer
from .ui.tokens import T
from .ui.tokens import fonts as ui_fonts

_BUTTON_LABEL = {"peace": "GO ON", "fight": "FIGHT", "leave": "RUN", "surrender": "GO WITH THEM",
                 "next": "GO ON"}
_TONE = {"peace": "peace", "next": "next", "fight": "fight", "leave": "next", "surrender": "next"}


class DialogueScreen(Screen):
    native = True

    def __init__(self, fonts, guild, group, encounter, on_done, on_decided=None, decided=None):
        super().__init__()
        self.fonts = fonts
        self._F = None
        self.guild = guild
        self.group = group
        self.encounter = encounter
        self.on_done = on_done
        self.on_decided = on_decided
        self.result = decided
        members = self.members
        understood = [u for u in members if encounter.shared(u)] or members
        self.speaker = max(understood, key=lambda u: u.mod_charisma) if understood else None
        self.hits = {"speakers": [], "options": [], "button": None}

    @property
    def members(self):
        return list(self.group.members)

    def _ui_fonts(self):
        if self._F is None:
            self._F = ui_fonts()
        return self._F

    def tutorial_key(self):
        if self.encounter.kind == "boss":
            return None
        if self.encounter.kind == "guard":
            return "guard"
        return "dialogue"

    # ------------------------------------------------------------------ #
    def choose(self, verb, speaker=None):
        speaker = speaker or self.speaker
        result = self.encounter.choose(verb, speaker, self.members)
        self.result = result
        if result.over and self.on_decided is not None:
            self.on_decided(result)
        return result

    def go_on(self):
        result = self.result
        if result is None:
            return
        if result.over:
            self.on_done(result)
        else:
            self.result = self.encounter.advance()

    def handle_event(self, event):
        if (event.type == pygame.KEYDOWN and self.result is not None
                and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE)):
            self.go_on()
            return
        super().handle_event(event)

    def _click(self, pos):
        if self.result is not None:
            if self.hits["button"] is not None and self.hits["button"].collidepoint(pos):
                self.go_on()
            return
        for uid, rect in self.hits["speakers"]:
            if rect.collidepoint(pos):
                self.speaker = next((u for u in self.members if u.uid == uid), self.speaker)
                return
        for verb, rect in self.hits["options"]:
            if rect.collidepoint(pos):
                self.choose(verb)
                return

    # ------------------------------------------------------------------ #
    def _data(self):
        enc = self.encounter
        lead = enc.leader
        leader = None if lead is None else {
            "name": lead.name, "caption": enc.caption(lead),
            "race": lead.race["name"], "portrait": lead.portrait_file or lead.portrait_id}
        speakers = []
        for u in self.members if enc.offered() else ():
            langs = ", ".join(u.languages) or "no language"
            speakers.append({"id": u.uid, "name": u.name, "selected": u is self.speaker,
                             "caption": f"CHA {u.mod_charisma:+d} · INT {u.mod_intelligence:+d} · {langs}"})
        options = [] if self.speaker is None else [
            {"id": o.verb, "label": o.label, "note": o.note, "check": o.check, "odds": o.odds, "block": o.block}
            for o in enc.options(self.speaker, self.members)]
        result = None
        if self.result is not None:
            result = {"text": self.result.text, "tone": _TONE[self.result.kind],
                      "button": _BUTTON_LABEL[self.result.kind]}
        return {"leader": leader, "line": enc.line,
                "foes": [f"{u.name} · {u.race['name']}" for u in enc.foes],
                "speakers": speakers, "options": options, "result": result}

    def draw(self, screen):
        F = self._ui_fonts()
        W, H = screen.get_size()
        screen.fill(T.TABLE)
        head = pygame.Rect(0, 0, W, T.S * 9)
        place = world.node(self.group.node).name if world.exists(self.group.node) else ""
        sub = f"{self.group.display_name} · {place}" if place else self.group.display_name
        header(screen, F, head, self.encounter.title, sub, (), None, mpos=self.mouse, has_tutorial=True)
        m = T.S * 3
        body = pygame.Rect(m, head.bottom + m, W - 2 * m, H - head.bottom - 2 * m)
        self.hits = draw_dialogue(screen, F, body, self._data(), self.mouse)
        hot = [r for _, r in self.hits["speakers"]] + [r for _, r in self.hits["options"]]
        if self.hits["button"] is not None:
            hot.append(self.hits["button"])
        set_pointer(any(r.collidepoint(self.mouse) for r in hot))

