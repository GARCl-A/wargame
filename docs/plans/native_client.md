# Native client (Electron shell)

The game stops opening in the player's browser and ships as its own window: an Electron shell that starts
the Python server as a child process, shows it, and closes it on exit. This is item 1 of gate 3 in
[go_to_market.md](go_to_market.md).

Scope: the game runs in its own client on Windows and the release ships it. Out of scope, each for a later
plan: Steam (depot, overlay, Steamworks), an installer, auto-update, code signing, Linux and macOS, and the
in-game settings for window size, full screen and interface scale (gate 3 item 5).

## Decisions

- **Electron, not pywebview or Tauri.** It ships its own Chromium, so every player gets the same rendering.
  The other two use the system's browser engine, which is the dependency being removed.
- **The shell is a wrapper, not a port.** The game stays the Python server plus the web client. The shell
  has no game logic and no `preload` bridge; the page only talks to the server over HTTP, as today.
- **`python main.py` stays as it is** (Edge or Chrome app window). It is the development path and what the
  tests cover. The shell is what ships.
- **The player's files leave the install folder.** Saves, `settings.json`, `errors.jsonl` and `log-export`
  go to `%APPDATA%\GARTOK\`. Today they sit beside the exe; in the packaged client that would be deep inside
  `resources\`, and an update that replaces the folder would delete them.
- **The server is a PyInstaller folder (`--onedir`), not one file.** One file unpacks itself to a temp folder
  on every start.
- **The release is a zip of a folder**, not a single exe. No installer.
- **`@electron/packager`, not `electron-builder`.** It only produces the folder, which is all this needs.
  `electron-builder` downloads signing tools on Windows that need symlink rights and often fail without
  Developer Mode.

## How it fits together

```
GARTOK.exe (Electron main, shell/main.js)
  └─ spawns  gartok-server.exe --shell      (PyInstaller onedir of main.py)
       stdin   a pipe the shell holds open: when it closes, the server stops
       stdout  one line "GARTOK web: http://127.0.0.1:<port>/", then the shell loads that URL
       stderr  appended by the shell to %APPDATA%\GARTOK\server.log
       env     GARTOK_DATA_DIR=%APPDATA%\GARTOK
```

Who ends whom:

| What happens | Result |
|---|---|
| The player closes the window | The shell closes the server's stdin, waits up to 3 s, kills it if still alive, quits |
| The player clicks QUIT in the game | The server shuts down as today and exits 0; the shell sees the exit and quits |
| The shell crashes or is killed | stdin reaches end of file; the server stops by itself (no orphan process) |
| The server dies with a non-zero code | The shell shows an error box naming `server.log` and quits |
| The server prints no URL within 30 s | Same error box |

Packaged layout (`dist/GARTOK-win32-x64/`):

```
GARTOK.exe
resources/app.asar                         shell/main.js and package.json
resources/gartok-server/gartok-server.exe  the Python server
resources/gartok-server/_internal/...      Python, locales, maps, npcs, gartok/assets, gartok/web/client
```

## Steps

One commit per step. Every step leaves `main` playable and the hard gate green.

### Step 1: the server learns to run under a shell (Python only)

1. `gartok/persist.py`: replace `_BASE_DIR` with a public `DATA_DIR` computed by a small pure function
   (arguments: the environment, whether the program is frozen, the executable's path), in this order:
   `GARTOK_DATA_DIR` when set and not empty; else the executable's folder when frozen; else the repo root.
   `SAVE_DIR = os.path.join(DATA_DIR, "saves")`. Translate the Portuguese comment above it or delete it.
2. `gartok/settings.py` (`PATH`) and `gartok/guild_log.py` (the `log-export` folder) read
   `persist.DATA_DIR` instead of `os.path.dirname(persist.SAVE_DIR)`. Tests that monkeypatch `SAVE_DIR`
   may rely on the old derivation: run the suite and fix what breaks, keeping the tests' isolation.
3. `gartok/web/__main__.py`:
   - A `--shell` flag. With it: no browser window, no `_stop_when_closed` thread, and a daemon thread that
     blocks on `sys.stdin.read()` and calls `game.quit()` when it returns (factor it as
     `_stop_on_eof(stream, stop)` so a test can pass a `io.StringIO`).
   - The URL line is the contract with the shell: print it with `flush=True` (stdout is a pipe there, so
     it is block-buffered otherwise and the shell would wait forever). Keep the text
     `GARTOK web: http://127.0.0.1:<port>/`.
   - Update the module docstring.
4. Tests in `tests/test_web.py`:
   - the data folder function: the three cases;
   - `_stop_on_eof` calls `stop` once the stream ends;
   - one end-to-end test of the contract: start `python -m gartok --shell` as a subprocess with stdin a
     pipe and `GARTOK_DATA_DIR` a temp folder, read the URL line from stdout, `GET /api/screen`, close
     stdin, assert the process exits within 10 s, and assert nothing was written outside the temp folder
     that should be in it (`settings.json` appears there once a setting is changed; skip that half if it
     needs a session).

Check: `python -m pytest tests/ -n auto -m "not balance"`, and `python main.py` still opens the browser
window with the repo's own `saves/`.

### Step 2: the shell, running from the repo

1. New folder `shell/`:
   - `package.json`: `name` `gartok`, `productName` `GARTOK`, `main` `main.js`, `private` true, `electron`
     and `@electron/packager` as `devDependencies` pinned to exact versions (the latest stable when this is
     built), no runtime dependencies. Scripts: `start` (`electron .`) and `smoke`
     (`electron . --smoke=<path>`).
   - `package-lock.json` is committed. `shell/node_modules/` goes in `.gitignore` (ruff follows
     `.gitignore`, so it also keeps the lint hook out of it).
   - `main.js`, plain JavaScript, one file. No framework, no bundler, no TypeScript.
2. `main.js` does, in order:
   - `app.setPath("userData", <appData>/GARTOK/client)` before `ready`, so Chromium's profile does not mix
     with the saves. The game's data folder is `<appData>/GARTOK`.
   - `app.requestSingleInstanceLock()`; a second launch focuses the first window and exits (two instances
     would write the same save files).
   - `app.commandLine.appendSwitch("autoplay-policy", "no-user-gesture-required")` (the title has music
     before any click, as the app window does today).
   - `Menu.setApplicationMenu(null)`.
   - Spawn the server with `stdio: ["pipe", "pipe", "pipe"]` and `windowsHide: true`:
     - packaged (`app.isPackaged`): `<process.resourcesPath>/gartok-server/gartok-server.exe --shell`, with
       `GARTOK_DATA_DIR` set;
     - from the repo: `python -m gartok --shell` with `cwd` the repo root and `GARTOK_DATA_DIR` not set,
       so development uses the repo's `saves/`.
     Arguments after the shell's own are passed on to the server (`npm start -- --fight fortress`).
   - Read stdout by line until the URL line matches `http://127.0.0.1:(\d+)/`; append stderr to
     `server.log` in the data folder (truncated at each start).
   - Create the `BrowserWindow`: `backgroundColor` `#0b0a09` (the host page's), `show: false` until
     `ready-to-show`, `autoHideMenuBar`, `webPreferences` with `contextIsolation: true`,
     `nodeIntegration: false`, `sandbox: true`, no preload. Load the URL.
   - Window state in `client/window.json` (bounds, maximized, full screen), saved on close and restored on
     start; first run opens maximized. F11 toggles full screen through `before-input-event` and
     `win.setFullScreen` (not the HTML full screen API, so Esc stays the game's). F12 opens the developer
     tools only when not packaged.
   - `setWindowOpenHandler` denies every new window and sends `http(s)` links to `shell.openExternal`;
     `will-navigate` cancels anything outside the server's origin.
   - The exits in the table above. The two error boxes are English literals in `main.js`: they show when the
     Python side, which owns `locales/`, did not start. This is a stated exception to the `en` key rule.
   - `--smoke=<png>`: window at 1920x1080 content size, wait for the page and 3 s more, write
     `webContents.capturePage()` to the path, quit with 0; quit with 1 if the URL never came.
3. Things to verify by running it, and fix in the shell if they fail (do not assume):
   - QUIT on the title and on the map closes the app (the client calls `window.close()` from inside the
     iframe; the server's exit is what the shell relies on).
   - Settings, *export playtest zip* (`GET /api/settings/export`, sent as an attachment) opens a save
     dialog and writes the file. If it does not, handle `session.on("will-download")`.
   - Music plays on the title with no click.
   - Closing the window leaves no `python` process behind; killing `electron.exe` from the Task Manager
     leaves none either.
   - Look at the smoke PNG: the title screen, full frame, no scrollbars, no white flash border.

Check: `cd shell && npm ci && npm start` plays a guild from the repo's saves; `npm run smoke` writes the PNG.

### Step 3: the build

1. New `scripts/build_client.py`, called by `build_exe.bat` in place of the PyInstaller line (after
   `version_check.py --build`, which is unchanged). It stops at the first failing command with that
   command's output. It does:
   - PyInstaller: `--onedir --console --name gartok-server --distpath build/server --workpath build/pyi
     --noconfirm`, the same five `--add-data` pairs as today **with absolute source paths**, `main.py`.
     Console subsystem on purpose: a windowed exe has no usable stdout for the URL line, and the shell
     hides the console with `windowsHide`.
   - `npm ci` in `shell/` (fail with a clear message when `npm` is not on PATH).
   - `npx electron-packager . GARTOK --platform=win32 --arch=x64 --out=<repo>/dist --overwrite --asar
     --app-version=<GAME_VERSION> --extra-resource=<repo>/build/server/gartok-server` run in `shell/`.
     The version comes from `gartok/version.py`; `package.json` keeps a placeholder version.
   - Zip `dist/GARTOK-win32-x64/` to `dist/GARTOK-<version>-win64.zip`, with the folder as the zip's root
     entry. Delete a stale `dist/GARTOK.exe` if one is there.
2. Delete `GARTOK.spec` (the build never read it; PyInstaller rewrote it on each run). Add `*.spec` to
   `.gitignore`.
3. `build_exe.bat` keeps its name (the release skill and `release.py` name it) and its last line says where
   the zip is.
4. Run the build and test the result **from a copy outside the repo** (so it cannot find the repo's files
   by accident): extract the zip to a temp folder, run `GARTOK.exe`, start a guild, save, quit, start again
   and continue. Confirm `%APPDATA%\GARTOK\saves\` has the save and the extracted folder has no new files.
   Both exports must follow the data folder: the guild log export lands in `%APPDATA%\GARTOK\log-export\`
   and any path the game shows for it is that one; the playtest zip from Settings contains those saves.
   Run `GARTOK.exe --smoke=<png>` and look at the image.

Check: the zip exists, the test above passes, the hard gate is green.

### Step 4: the release

1. `scripts/release.py`: the asset is `dist/GARTOK-<row version>-win64.zip` (the name carries the version,
   so a zip from another version is refused by not existing); `SHIPPED` gains `shell/` so a shell change
   appears in the notes; the *Como jogar* text says to download the zip, extract it anywhere and run
   `GARTOK.exe` (the SmartScreen sentence stays: nothing is signed). For the first release with the client,
   the notes also say that saves now live in `%APPDATA%\GARTOK\saves` and that an old `saves` folder beside
   the old exe can be copied there; make that a one-off line the next release does not repeat.
2. `.claude/skills/release/SKILL.md`: step 4 expects the zip instead of `dist/GARTOK.exe`, and the build
   needs Node on PATH; step 6 says it uploads the zip.
3. `python scripts/release.py --dry-run` prints the new notes with no error other than the ones about an
   unpublished state.

### Step 5: the client keeps what it already loaded

Why: every screen change reloads the game's page, and every static file is served `no-cache`, so the page
asks the server for each one again. Measured on 2026-11-12 (headless Edge, 1920x1080, a day-4 guild): a
screen change makes about 108 requests on the map and 63 on the guild screen, and the 26 sounds and the
icons come back whole each time. Served as cacheable, the same change makes 6 requests and the map opens in
0.24 s instead of 0.41 s. On a CPU slowed 4 times the gain is small (the time there is the page being
rebuilt, which this step does not touch). A loading screen at start was considered and dropped: the first
load takes under a second and nothing it loads survives the next screen change.

1. `gartok/web/server.py`: the server takes a "static files do not change while I run" switch (a
   `--cache-static` flag in `gartok/web/__main__.py`, off by default). With it, files under `/client/` and
   `/assets/` are sent with `Cache-Control: max-age=31536000, immutable`. `/`, `/game` and every `/api/`
   answer keep what they send today. Without the flag nothing changes, so `python main.py` still shows an
   edited file on the next reload.
2. `shell/main.js`: the packaged client passes `--cache-static`; the shell run from the repo does not
   (pass it by hand to try it: `npm start -- --cache-static`). Before loading the URL the shell calls
   `session.defaultSession.clearCache()`: the cache then lives for one session, so a new build never shows
   an old file and the server's port changing between runs leaves nothing behind.
3. Tests: with the switch, a `/client/` file and an `/assets/` file carry the immutable header and an
   `/api/` answer does not; without it, the headers are today's.
4. Check in the client, with the developer tools' network tab open (F12, from the repo with the flag):
   moving map → guild → map makes only the `/game` and `/api/` requests the second time, every sound still
   plays, and the tutorial cards and a language change in Settings still show the right text.

Not in this step: the sounds are still decoded again on every screen change (their bytes come from the
cache, the decoding is repeated), and the page is still rebuilt. Both would need the game to stop reloading
on a screen change, which is a change to every screen and is not planned here.

### Step 6: the docs

- `README.md`: the run lines (`python main.py` for development, `cd shell && npm start` for the client),
  the build line, `shell/` in the code map, Node as a build requirement.
- `docs/web_ui/web_client.md`: the first paragraph and the autoplay note (the shell lifts the policy too).
- `AGENTS.md`: the first paragraph ("The game is the web client") names the shell in one clause; the
  *Saves* rule's build sentence names the zip. No description of the shell there.
- `docs/plans/backlog.md`: delete this plan's entry under *Large*. `docs/plans/go_to_market.md`: gate 3
  item 1 becomes one line saying it is done, or is deleted with the list renumbered.
- Delete this file when the last step lands, as the backlog's rule says.

## Not decided here (the author's)

- **The window icon.** No `.ico` exists in the repo. Until one does, the client ships with Electron's
  default icon; when it exists, it is one `--icon` argument in `scripts/build_client.py`.
- **Old saves.** This plan only tells the player where to copy them. An automatic import on first run is
  possible but the shell cannot know where the old exe was.

## What this leaves ready for Steam

Nothing here is Steam work, and nothing here has to be redone for it: a folder build is what a depot
uploads, the player's files are already outside the install folder (cloud saves need that), and the server
is a child of the launched exe.
