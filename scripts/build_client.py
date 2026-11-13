"""Build the native client: the Python server as a PyInstaller folder, the Electron shell around it, and a zip
of the result. Run by `build_exe.bat`, after `version_check.py --build`.

    build/server/gartok-server/      the server (PyInstaller --onedir; a console exe, the shell hides it)
    dist/GARTOK-win32-x64/           the client: GARTOK.exe + resources/gartok-server
    dist/GARTOK-<version>-win64.zip  what the release publishes

Stops at the first failing command, its output above the message. Plan: docs/plans/native_client.md."""

import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from gartok.version import GAME_VERSION

SHELL = os.path.join(ROOT, "shell")
SERVER = os.path.join(ROOT, "build", "server")
DIST = os.path.join(ROOT, "dist")
APP = "GARTOK-win32-x64"
DATA = ("locales", "maps", "npcs", "gartok/assets", "gartok/web/client")      # what the server reads at run time


def run(cmd, cwd=ROOT):
    print(f"\n> {' '.join(cmd)}", flush=True)
    if subprocess.run(cmd, cwd=cwd, check=False).returncode:
        sys.exit(f"FAILED: {' '.join(cmd)}")


def tool(name):
    found = shutil.which(name)
    if found is None:
        sys.exit(f"{name} is not on PATH: the client build needs Node (https://nodejs.org)")
    return found


def build_server():
    add = [arg for src in DATA for arg in ("--add-data", f"{os.path.join(ROOT, *src.split('/'))}{os.pathsep}{src}")]
    run([sys.executable, "-m", "PyInstaller", "--onedir", "--console", "--noconfirm", "--name", "gartok-server",
         "--distpath", SERVER, "--workpath", os.path.join(ROOT, "build", "pyi"),
         "--specpath", os.path.join(ROOT, "build", "pyi"), *add, os.path.join(ROOT, "main.py")])


def build_shell():
    run([tool("npm"), "ci"], cwd=SHELL)
    # node on the package's script, not npx: a .cmd goes through cmd.exe, which reads the ^ and | of --ignore
    packager = os.path.join(SHELL, "node_modules", "@electron", "packager", "bin", "electron-packager.mjs")
    run([tool("node"), packager, ".", "GARTOK", "--platform=win32", "--arch=x64",
         f"--out={DIST}", "--overwrite", "--asar", f"--app-version={GAME_VERSION}",
         r"--ignore=^/(run\.js|smoke\.png|package-lock\.json)$",
         f"--extra-resource={os.path.join(SERVER, 'gartok-server')}"], cwd=SHELL)


def zip_client():
    stale = os.path.join(DIST, "GARTOK.exe")
    if os.path.exists(stale):
        os.remove(stale)
    name = os.path.join(DIST, f"GARTOK-{GAME_VERSION}-win64")
    print(f"\nZipping {APP} ...", flush=True)
    return shutil.make_archive(name, "zip", root_dir=DIST, base_dir=APP)


def main():
    build_server()
    build_shell()
    print(f"\nDone: {zip_client()}")


if __name__ == "__main__":
    main()
