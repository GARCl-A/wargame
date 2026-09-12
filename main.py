"""Ponto de entrada do GARTOK Tactical."""

import sys

# Windows treats an unmanifested process as DPI-unaware, so on a scaled display
# (125%/150%/...) the compositor bitmap-stretches the whole window -- soft text,
# soft everything. Must run before pygame.init() (gartok.app.App.__init__), so
# it has to sit here, above the import, not inside the app itself.
if sys.platform == "win32":
    import ctypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)   # PROCESS_PER_MONITOR_DPI_AWARE
    except (AttributeError, OSError):    # missing (Win7/8), or already set (e.g. by a manifest)
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except OSError:
            pass                          # cosmetic only -- never worth blocking startup over

from gartok.app import App

if __name__ == "__main__":
    App().run()
