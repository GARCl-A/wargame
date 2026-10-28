"""`python -m gartok`: the game in a browser window (`gartok.web`). `--pygame` opens the pygame window
instead, where the Editor (characters, maps, the combat lab) still lives."""

import sys


def _pygame():
    # Windows treats an unmanifested process as DPI-unaware, so on a scaled display (125%/150%/...) the
    # compositor bitmap-stretches the whole window. Must run before pygame.init() (App.__init__).
    if sys.platform == "win32":
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)   # PROCESS_PER_MONITOR_DPI_AWARE
        except (AttributeError, OSError):    # missing (Win7/8), or already set (e.g. by a manifest)
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except OSError:
                pass
    from .app import App
    App().run()


def main():
    if "--pygame" in sys.argv[1:]:
        _pygame()
        return
    from .web.__main__ import main as web
    web()


if __name__ == "__main__":
    main()
