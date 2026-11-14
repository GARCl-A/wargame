"""The layout harness: a game served to a headless browser (`tests/browser.py`) and audited there by
`tests/layout_audit.js`, which measures what the page drew. How to cover a screen: `tests/README.md`."""

import json
import os
import tempfile
import threading

from gartok import fault_log
from gartok.web.server import serve

HERE = os.path.dirname(os.path.abspath(__file__))
SHOTS = os.path.join(tempfile.gettempdir(), "gartok-layout")
STILL = "*,*::before,*::after{animation:none!important;transition:none!important}"

with open(os.path.join(HERE, "layout_audit.js"), encoding="utf-8") as _f:
    AUDIT = _f.read()

# the page says it could not reach the server (the shell's "lost" toast, a file it could not load, a request that failed)
DROPPED = r"""(() => /shell\.lost|could not load|Failed to fetch|NetworkError/.test(
  [...document.querySelectorAll("#failed, #fault, #shellnews")].map(e => e.textContent).join(" ")))()"""

# the tooltips' owners are the elements carrying a data-tip*; the first tooltip opens after a delay and the rest at once
TIPS = """(async (only, mark, audit) => {
  const SEL = "[data-tip],[data-tip-item],[data-tip-sum]", seen = new Set(), owners = [], out = [];
  for (const el of document.querySelectorAll(SEL)) {
    // only what a pointer can reach: on screen and not under a scrolled-away or covering box
    const c = el.getBoundingClientRect(), hit = document.elementFromPoint(c.left + c.width / 2, c.top + c.height / 2);
    if (!el.checkVisibility() || el.closest("#tip") || !hit || !(el === hit || el.contains(hit))) continue;
    const d = el.dataset, key = [d.tip, d.tipItem, d.tipSum, d.tipMore].join("|");
    if (!seen.has(key)) { seen.add(key); owners.push(el); }
  }
  const point = el => { const r = el.getBoundingClientRect();
    el.dispatchEvent(new PointerEvent("pointermove", {bubbles: true, composed: true, clientX: r.left + r.width / 2, clientY: r.top + r.height / 2})); };
  let first = true, shown = 0;
  for (const [i, el] of owners.entries()) {
    if (only !== null && i !== only) continue;
    point(el);
    if (first) { first = false; await new Promise(r => setTimeout(r, 480)); }
    if (!document.getElementById("tip") || document.getElementById("tip").hidden) continue;
    shown++;
    for (const f of audit({root: "#tip", mark})) out.push({...f, at: i, owner: (el.className || el.tagName) + " " + (el.textContent || "").trim().slice(0, 30)});
  }
  return {owners: owners.length, shown, found: out};
})(%s, %s, (%s))"""

OPEN_SHEET = """(() => {
  const el = [...document.querySelectorAll("[data-sheet]")].find(e => e.checkVisibility());
  if (!el) return false;
  const r = el.getBoundingClientRect(), at = {bubbles: true, button: 0, clientX: r.left + 5, clientY: r.top + 5};
  el.dispatchEvent(new PointerEvent("pointerdown", at));
  el.dispatchEvent(new PointerEvent("pointerup", at));
  el.dispatchEvent(new MouseEvent("click", at));
  return true;
})()"""

# resolves once the element has stood where it is for five frames (a sheet that is still sliding in is not yet drawn)
SETTLED = """new Promise(done => {
  const el = %s;
  let last = "", still = 0;
  const look = () => {
    const r = el.getBoundingClientRect(), now = [r.left, r.top, r.width, r.height].join();
    still = now === last ? still + 1 : 0;
    last = now;
    still >= 5 ? done(1) : requestAnimationFrame(look);
  };
  look();
})"""


class Page:
    """`game` open in `browser`, its screen settled and standing still."""

    def __init__(self, browser, game, ready="true"):
        """`ready` is a script that is true once the screen has nothing left to play (a fight's computer turns)."""
        self.browser, self.game, self.ready = browser, game, ready
        self.tips_shown = self.sheets_opened = 0
        self.server = serve(game)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.load()

    def load(self):
        """Again from the server: a new screen, or the same one in another language. A load the network dropped
        (a busy machine refuses a connection now and then, and a script that never came is a fault at once) is asked
        for again; a fault that stays through three tries is the screen's."""
        b = self.browser
        port = self.server.server_address[1]
        for attempt in range(3):
            try:
                os.remove(fault_log.path())
            except FileNotFoundError:
                pass
            b.open(f"http://127.0.0.1:{port}/game")
            try:
                b.wait(f"location.port === '{port}' && document.readyState === 'complete' && document.body.classList.contains('ready')")
                b.wait(self.ready)
                if not (b.eval(DROPPED) or self.faults()) or attempt == 2:
                    break
            except TimeoutError:
                if attempt == 2:
                    raise
        b.eval(f"document.head.appendChild(Object.assign(document.createElement('style'), {{textContent: {json.dumps(STILL)}}})) && 1")
        self.still()

    def still(self):
        """Two frames on, so what the last call changed is laid out."""
        self.browser.eval("new Promise(r => requestAnimationFrame(() => requestAnimationFrame(() => r(1))))")

    def faults(self):
        """What the screen's scripts and the server wrote to the fault log while it was open, one line each."""
        try:
            with open(fault_log.path(), encoding="utf-8") as f:
                return [f"fault: {line['where']}: {line['error']}" for line in map(json.loads, f)]
        except FileNotFoundError:
            return []

    def audit(self, root="#stage", fit=(), shot=None, **options):
        """What is broken under `root`, as lines to read; `fit` names the boxes that must show all they hold.
        `shot` names the picture written when something is (the offenders outlined in red)."""
        found = self.browser.eval(f"({AUDIT})({json.dumps({'root': root, 'fit': list(fit), 'mark': bool(shot), **options})})")
        shown = self.browser.eval("[...document.querySelectorAll('#fault, #shellnews, #failed')].map(e => e.textContent.trim())")
        faults = self.faults() + [f"the shell shows: {text}" for text in shown]
        if faults:
            return faults
        if found and shot:
            os.makedirs(SHOTS, exist_ok=True)
            path = os.path.join(SHOTS, shot + ".png")
            self.browser.screenshot(path)
            found.append({"kind": "picture", "where": path, "text": "", "by": 0})
        return [f"{f['kind']:9} {f['by']:>4}px  {f['where']}  |  {f['text']}" if f["kind"] != "picture" else f"picture: {f['where']}"
                for f in found]

    def tips(self, shot=None):
        """Each distinct tooltip the screen can show, opened by the pointer over its owner and audited: the lines
        of what is wrong, each with the tooltip's owner, the first one outlined in a picture."""
        def run(only):
            return self.browser.eval(TIPS % (json.dumps(only), json.dumps(only is not None), AUDIT))
        answer = run(None)
        found, self.tips_shown = answer["found"], answer["shown"]
        if found and shot:
            run(found[0]["at"])
            self.snap(shot)
        return [f"tooltip of {f['owner']}: {f['kind']} {f['by']}px {f['where']} | {f['text']}" for f in found]

    def sheet(self, shot=None):
        """The unit sheet over the screen (a click on its first portrait), audited inside its shadow root; none when
        the screen has no portrait to open it from."""
        b = self.browser
        if not b.eval(OPEN_SHEET):
            return []
        self.sheets_opened += 1
        # the book's own stylesheet is a link: until it has loaded the sheet is drawn bare
        b.wait("!!document.querySelector('#sheet-veil')?.shadowRoot?.querySelector('link')?.sheet")
        b.eval(f"document.getElementById('sheet-veil').shadowRoot.appendChild(Object.assign(document.createElement('style'), "
               f"{{textContent: {json.dumps(STILL)}}})) && document.fonts.ready.then(() => 1)")
        b.eval(SETTLED % "document.getElementById('sheet-veil').shadowRoot.querySelector('.book')")
        self.still()
        found = b.eval(f"({AUDIT})({json.dumps({'shadow': '#sheet-veil', 'mark': bool(shot)})})")
        if found and shot:
            self.snap(shot)
        b.eval("document.getElementById('sheet-veil')?.remove(), 1")
        return [f"unit sheet: {f['kind']} {f['by']}px {f['where']} | {f['text']}" for f in found]

    def snap(self, name):
        os.makedirs(SHOTS, exist_ok=True)
        self.browser.screenshot(os.path.join(SHOTS, name + ".png"))

    def close(self):
        self.server.shutdown()
        self.server.server_close()
