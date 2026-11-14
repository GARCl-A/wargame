"""A headless browser for the layout tests, driven over the DevTools protocol with the standard library
alone: the Edge (or Chrome) the machine already has, one page, `eval` and `screenshot`."""

import base64
import json
import os
import shutil
import socket
import struct
import subprocess
import tempfile
import time
import urllib.request

CANDIDATES = (
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "/usr/bin/microsoft-edge", "/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
)


def find():
    """The browser's path, or None when the machine has none (`GARTOK_BROWSER` names one)."""
    named = os.environ.get("GARTOK_BROWSER")
    if named:
        return named if os.path.exists(named) else None
    return next((p for p in CANDIDATES if os.path.exists(p)), None)


class _Socket:
    """Just enough WebSocket for DevTools: masked text frames out, whole messages in."""

    def __init__(self, url):
        host, _, path = url.removeprefix("ws://").partition("/")
        name, _, port = host.partition(":")
        self.sock = socket.create_connection((name, int(port)), timeout=30)
        key = base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall((f"GET /{path} HTTP/1.1\r\nHost: {host}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                           f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
        self.buf = b""
        while b"\r\n\r\n" not in self.buf:
            self.buf += self._more()
        head, _, self.buf = self.buf.partition(b"\r\n\r\n")
        if b" 101 " not in head.split(b"\r\n")[0]:
            raise ConnectionError(head.decode(errors="replace"))

    def _more(self):
        data = self.sock.recv(1 << 16)
        if not data:
            raise ConnectionError("the browser closed the connection")
        return data

    def _take(self, n):
        while len(self.buf) < n:
            self.buf += self._more()
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def send(self, text):
        data = text.encode()
        mask = os.urandom(4)
        n = len(data)
        head = bytes([0x81]) + (bytes([0x80 | n]) if n < 126 else bytes([0x80 | 126]) + struct.pack(">H", n) if n < 1 << 16
                                else bytes([0x80 | 127]) + struct.pack(">Q", n))
        self.sock.sendall(head + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

    def recv(self):
        message = b""
        while True:
            first, second = self._take(2)
            n = second & 0x7F
            if n == 126:
                n = struct.unpack(">H", self._take(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", self._take(8))[0]
            payload = self._take(n)
            opcode = first & 0x0F
            if opcode == 8:
                raise ConnectionError("the browser closed the connection")
            if opcode in (0, 1, 2):
                message += payload
                if first & 0x80:
                    return message.decode()

    def close(self):
        self.sock.close()


class Browser:
    """One headless page of `width`x`height`. `open(url)` loads it, `eval(js)` returns the expression's
    value (a promise is awaited), `screenshot(path)` writes a PNG."""

    def __init__(self, width=1920, height=1080, path=None):
        path = path or find()
        if path is None:
            raise FileNotFoundError("no Edge or Chrome on this machine")
        self.ws = None
        self.profile = tempfile.mkdtemp(prefix="gartok-browser-")
        self.proc = subprocess.Popen(
            [path, "--headless=new", "--remote-debugging-port=0", f"--user-data-dir={self.profile}",
             f"--window-size={width},{height}", "--no-first-run", "--no-default-browser-check", "--mute-audio",
             "--disable-extensions", "--force-device-scale-factor=1", "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.ws = _Socket(self._page_url())
        self.seq = 0
        self.resize(width, height)

    def _page_url(self):
        port_file = os.path.join(self.profile, "DevToolsActivePort")
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            try:
                with open(port_file) as f:
                    port = int(f.read().split()[0])
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list") as r:
                    pages = [p for p in json.load(r) if p.get("type") == "page"]
                if pages:
                    return pages[0]["webSocketDebuggerUrl"]
            except (OSError, ValueError, IndexError):
                pass
            time.sleep(0.05)
        self.close()
        raise TimeoutError("the browser never opened its DevTools port")

    def call(self, method, **params):
        self.seq += 1
        self.ws.send(json.dumps({"id": self.seq, "method": method, "params": params}))
        while True:
            answer = json.loads(self.ws.recv())
            if answer.get("id") == self.seq:
                if "error" in answer:
                    raise RuntimeError(f"{method}: {answer['error']}")
                return answer["result"]

    def resize(self, width, height):
        self.call("Emulation.setDeviceMetricsOverride", width=width, height=height, deviceScaleFactor=1, mobile=False)

    def open(self, url):
        self.call("Page.navigate", url=url)

    def eval(self, js):
        r = self.call("Runtime.evaluate", expression=js, awaitPromise=True, returnByValue=True)
        if "exceptionDetails" in r:
            detail = r["exceptionDetails"]
            raise RuntimeError(detail.get("exception", {}).get("description") or detail.get("text"))
        return r["result"].get("value")

    def wait(self, js, timeout=20):
        """Until the expression is truthy; its value."""
        deadline = time.monotonic() + timeout
        while True:
            value = self.eval(js)
            if value:
                return value
            if time.monotonic() > deadline:
                raise TimeoutError(f"never true: {js}")
            time.sleep(0.05)

    def screenshot(self, path):
        with open(path, "wb") as f:
            f.write(base64.b64decode(self.call("Page.captureScreenshot", format="png")["data"]))

    def close(self):
        if self.ws:
            try:
                self.call("Browser.close")
            except (OSError, RuntimeError):
                pass
            self.ws.close()
        else:
            self.proc.terminate()
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        shutil.rmtree(self.profile, ignore_errors=True)
