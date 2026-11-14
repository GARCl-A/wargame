"""The layout harness: a game served to a headless browser (`tests/browser.py`) and audited there by
`tests/layout_audit.js`, which measures what the page drew. How to cover a screen: `tests/README.md`."""

import json
import os
import tempfile
import threading

from gartok.web.server import serve

HERE = os.path.dirname(os.path.abspath(__file__))
SHOTS = os.path.join(tempfile.gettempdir(), "gartok-layout")
STILL = "*,*::before,*::after{animation:none!important;transition:none!important}"

with open(os.path.join(HERE, "layout_audit.js"), encoding="utf-8") as _f:
    AUDIT = _f.read()


class Page:
    """`game` open in `browser`, its screen settled and standing still."""

    def __init__(self, browser, game):
        self.browser, self.game = browser, game
        self.server = serve(game)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.load()

    def load(self):
        """Again from the server: a new screen, or the same one in another language."""
        b = self.browser
        port = self.server.server_address[1]
        b.open(f"http://127.0.0.1:{port}/game")
        b.wait(f"location.port === '{port}' && document.readyState === 'complete' && document.body.classList.contains('ready')")
        b.eval(f"document.head.appendChild(Object.assign(document.createElement('style'), {{textContent: {json.dumps(STILL)}}})) && 1")
        self.still()

    def still(self):
        """Two frames on, so what the last call changed is laid out."""
        self.browser.eval("new Promise(r => requestAnimationFrame(() => requestAnimationFrame(() => r(1))))")

    def audit(self, root="#stage", fit=(), shot=None, **options):
        """What is broken under `root`, as lines to read; `fit` names the boxes that must show all they hold.
        `shot` names the picture written when something is (the offenders outlined in red)."""
        found = self.browser.eval(f"({AUDIT})({json.dumps({'root': root, 'fit': list(fit), 'mark': bool(shot), **options})})")
        if found and shot:
            os.makedirs(SHOTS, exist_ok=True)
            path = os.path.join(SHOTS, shot + ".png")
            self.browser.screenshot(path)
            found.append({"kind": "picture", "where": path, "text": "", "by": 0})
        return [f"{f['kind']:9} {f['by']:>4}px  {f['where']}  |  {f['text']}" if f["kind"] != "picture" else f"picture: {f['where']}"
                for f in found]

    def close(self):
        self.server.shutdown()
        self.server.server_close()
