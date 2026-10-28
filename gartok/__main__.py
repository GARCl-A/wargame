"""`python -m gartok`: the game in a browser window (`gartok.web`). `--editor` opens the Editor
(characters, maps, the combat lab) in a pygame window instead."""

import sys


def _editor():
    # Windows treats an unmanifested process as DPI-unaware, so on a scaled display (125%/150%/...) the
    # compositor bitmap-stretches the whole window. Must run before pygame.init() (EditorApp.__init__).
    if sys.platform == "win32":
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)   # PROCESS_PER_MONITOR_DPI_AWARE
        except (AttributeError, OSError):    # missing (Win7/8), or already set (e.g. by a manifest)
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except OSError:
                pass
    from .editor_app import EditorApp
    EditorApp().run()


def main():
    if "--editor" in sys.argv[1:]:
        _editor()
        return
    from .web.__main__ import main as web
    web()


if __name__ == "__main__":
    main()
