// The native window for GARTOK Tactical: starts the Python server (`python -m gartok --shell`, or the
// packaged gartok-server.exe), loads the page it serves, and stops it when the window closes.
// No game logic lives here; plan: docs/plans/native_client.md.
"use strict";

const { app, BrowserWindow, Menu, dialog, screen, shell } = require("electron");
const { spawn } = require("child_process");
const fs = require("fs");
const path = require("path");

const REPO = path.join(__dirname, "..");
const DATA_DIR = path.join(app.getPath("appData"), "GARTOK");
const LOG_PATH = path.join(DATA_DIR, "server.log");
const STATE_PATH = path.join(DATA_DIR, "client", "window.json");
const URL_LINE = /http:\/\/127\.0\.0\.1:(\d+)\//;
const URL_WAIT_MS = 30000;
const STOP_WAIT_MS = 3000;

const smokeArg = process.argv.find(a => a.startsWith("--smoke="));
const SMOKE = smokeArg ? path.resolve(smokeArg.slice("--smoke=".length)) : null;
const serverArgs = process.argv.slice(app.isPackaged ? 1 : 2).filter(a => !/^--(smoke|remote-debugging-port|inspect(-brk)?)(=|$)/.test(a));

fs.mkdirSync(path.join(DATA_DIR, "client"), { recursive: true });
app.setPath("userData", path.join(DATA_DIR, "client"));
app.commandLine.appendSwitch("autoplay-policy", "no-user-gesture-required");      // the title has music before any click

let win = null;
let server = null;
let serverExited = false;
let stopping = false;
let failing = false;

function fail(message) {
  if (failing) return;      // the error box runs a nested loop in which the server's exit can arrive
  failing = true;
  if (SMOKE) {
    console.error(message);
    app.exit(1);
    return;
  }
  dialog.showErrorBox("GARTOK", `${message}\n\nThe server log is ${LOG_PATH}`);
  app.exit(1);
}

function pythonCommand() {
  const venv = path.join(REPO, ".venv", "Scripts", "python.exe");
  return process.env.GARTOK_PYTHON || (fs.existsSync(venv) ? venv : "python");
}

function startServer() {
  const log = fs.createWriteStream(LOG_PATH, { flags: "w" });
  const env = { ...process.env, PYTHONUNBUFFERED: "1", PYTHONIOENCODING: "utf-8" };
  let command, args, cwd;
  if (app.isPackaged) {
    env.GARTOK_DATA_DIR = DATA_DIR;
    command = path.join(process.resourcesPath, "gartok-server", "gartok-server.exe");
    args = ["--shell", ...serverArgs];
    cwd = DATA_DIR;
  } else {
    command = pythonCommand();
    args = ["-m", "gartok", "--shell", ...serverArgs];
    cwd = REPO;
  }
  server = spawn(command, args, { cwd, env, stdio: ["pipe", "pipe", "pipe"], windowsHide: true });
  server.stdin.on("error", () => {});
  server.stderr.on("data", d => log.write(d));

  return new Promise((resolve, reject) => {
    let seen = "";
    let found = false;
    const timer = setTimeout(() => reject(new Error("The game server did not start in time.")), URL_WAIT_MS);
    // both streams are read for the server's whole life: a full pipe would freeze it inside a request
    server.stdout.on("data", d => {
      log.write(d);
      if (found) return;
      seen += d;
      const m = seen.match(URL_LINE);
      if (m) {
        found = true;
        clearTimeout(timer);
        resolve(m[0]);
      }
    });
    server.on("error", e => { clearTimeout(timer); reject(new Error(`Could not start the game server: ${e.message}`)); });
    server.on("exit", (code, signal) => {
      serverExited = true;
      clearTimeout(timer);
      if (stopping || code === 0) {          // QUIT in the game, or the stop this shell asked for
        app.quit();
      } else if (!found) {
        reject(new Error(`The game server stopped before it was ready (${signal || `code ${code}`}).`));
      } else {
        fail(`The game server stopped unexpectedly (${signal || `code ${code}`}).`);
      }
    });
  });
}

// closing the server's stdin is how it learns the window is gone; it is killed if it does not follow
function stopServer() {
  stopping = true;
  if (!server || serverExited) return Promise.resolve();
  return new Promise(resolve => {
    const kill = setTimeout(() => { try { server.kill(); } catch (e) { /* already gone */ } }, STOP_WAIT_MS);
    server.once("exit", () => { clearTimeout(kill); resolve(); });
    try { server.stdin.end(); } catch (e) { server.kill(); }
  });
}

function loadState() {
  try { return JSON.parse(fs.readFileSync(STATE_PATH, "utf8")); } catch (e) { return {}; }
}

function visible(b) {
  return b && screen.getAllDisplays().some(d => {
    const w = d.workArea;
    return b.x < w.x + w.width && b.x + b.width > w.x && b.y < w.y + w.height && b.y + b.height > w.y;
  });
}

function saveState() {
  if (!win || win.isDestroyed()) return;
  const state = { maximized: win.isMaximized(), fullScreen: win.isFullScreen() };
  if (!state.maximized && !state.fullScreen) state.bounds = win.getBounds();
  else state.bounds = loadState().bounds;
  try { fs.writeFileSync(STATE_PATH, JSON.stringify(state)); } catch (e) { /* the next close tries again */ }
}

function openWindow(url) {
  const origin = new URL(url).origin;
  const state = SMOKE ? {} : loadState();
  const bounds = visible(state.bounds) ? state.bounds : { width: 1920, height: 1080 };
  win = new BrowserWindow({
    ...bounds,
    ...(SMOKE ? { width: 1920, height: 1080, useContentSize: true, enableLargerThanScreen: true } : {}),
    minWidth: 960,
    minHeight: 540,
    backgroundColor: "#0b0a09",
    show: false,
    autoHideMenuBar: true,
    title: "GARTOK Tactical",
    webPreferences: { contextIsolation: true, nodeIntegration: false, sandbox: true, spellcheck: false },
  });
  win.once("ready-to-show", () => {
    if (!SMOKE && (state.maximized || !state.bounds)) win.maximize();      // first run opens maximized
    if (!SMOKE && state.fullScreen) win.setFullScreen(true);
    win.show();
    if (SMOKE) win.setContentSize(1920, 1080);      // the constructor's size is clamped to the screen
  });
  win.webContents.on("before-input-event", (event, input) => {
    if (input.type !== "keyDown") return;
    if (input.key === "F11") {          // the window's full screen, not the page's: Esc stays the game's
      win.setFullScreen(!win.isFullScreen());
      event.preventDefault();
    } else if (input.key === "F12" && !app.isPackaged) {
      win.webContents.toggleDevTools();
    }
  });
  win.webContents.setWindowOpenHandler(({ url: target }) => {
    if (/^https?:/i.test(target)) shell.openExternal(target);
    return { action: "deny" };
  });
  win.webContents.on("will-navigate", (event, target) => {
    if (new URL(target).origin !== origin) event.preventDefault();
  });
  win.on("close", saveState);
  win.loadURL(url);
  if (SMOKE) {
    win.webContents.once("did-finish-load", () => setTimeout(async () => {
      const image = await win.webContents.capturePage();
      fs.writeFileSync(SMOKE, image.toPNG());
      await stopServer();
      app.exit(0);
    }, 3000));
  }
}

if (!SMOKE && !app.requestSingleInstanceLock()) {      // two copies would write the same saves
  app.exit(0);
} else {
  app.on("second-instance", () => {
    if (!win) return;
    if (win.isMinimized()) win.restore();
    win.focus();
  });
  app.on("window-all-closed", () => { stopServer().then(() => app.quit()); });
  app.on("before-quit", () => { stopping = true; });
  process.on("exit", () => { if (server && !serverExited) server.kill(); });

  app.whenReady().then(async () => {
    Menu.setApplicationMenu(null);
    try {
      openWindow(await startServer());
    } catch (e) {
      if (server && !serverExited) server.kill();      // not stopServer(): a server that never started never exits
      fail(e.message);
    }
  });
}
