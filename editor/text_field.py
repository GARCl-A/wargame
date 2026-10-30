"""A one-line text box's buffer and caret: typing, Backspace / Delete, the arrows, Home / End."""
import pygame

from editor.ui.primitives import with_caret


class TextField:
    def __init__(self, cap, allow=str.isprintable, text=""):
        self.cap, self.allow = cap, allow
        self.set(text)

    def set(self, text=""):
        self.text = text[:self.cap]
        self.caret = len(self.text)

    def key(self, event):
        """Apply one KEYDOWN; True when it was a typing key (Enter / Esc are the screen's)."""
        k, t, c = event.key, self.text, self.caret
        if k == pygame.K_LEFT:
            self.caret = max(0, c - 1)
        elif k == pygame.K_RIGHT:
            self.caret = min(len(t), c + 1)
        elif k in (pygame.K_HOME, pygame.K_UP):
            self.caret = 0
        elif k in (pygame.K_END, pygame.K_DOWN):
            self.caret = len(t)
        elif k == pygame.K_BACKSPACE:
            if c:
                self.text, self.caret = t[:c - 1] + t[c:], c - 1
        elif k == pygame.K_DELETE:
            self.text = t[:c] + t[c + 1:]
        elif event.unicode and event.unicode.isprintable() and self.allow(event.unicode):
            if len(t) < self.cap:
                self.text, self.caret = t[:c] + event.unicode + t[c:], c + 1
        else:
            return False
        return True

    def shown(self):
        return with_caret(self.text, self.caret)
