// The music. It lives in the host page (`host.html`), which never reloads while the game inside its frame
// reloads on every screen change, so a track plays through all of them. A radio on every screen but the fight
// (one track, 30 to 60 seconds of quiet, the next), one battle track at random in a fight; a change between the
// two fades the old out and the new in. Files and timings come from `sound.py` through /api/sounds.
"use strict";

const Music = (() => {
  const modeOf = screen => screen === "battle" ? "battle" : "radio";
  let cfg = null, volume = 0, mode = null, el = null, ramp = null, wait = null, last = null, blocked = null, turn = 0;
  const gain = () => Math.min(1, volume * (cfg ? cfg.level : 1));
  const draw = (list, not) => { const rest = list.filter(u => u !== not); return rest[Math.floor(Math.random() * rest.length)] || list[0]; };
  const silence = () => (cfg.silence[0] + Math.random() * (cfg.silence[1] - cfg.silence[0])) * 1000;
  // the volume eases from where it is to `to` (a number, or a function read at every step so a change of the
  // setting mid-fade is followed) over `secs`; `done` runs once it lands. A fade is never cut short by a setting.
  function fadeTo(to, secs, done) {
    clearInterval(ramp);
    ramp = null;
    if (!el) { if (done) done(); return; }
    const a = el, from = a.volume, t0 = performance.now(), end = typeof to === "function" ? to : () => to;
    ramp = setInterval(() => {
      const k = Math.min(1, (performance.now() - t0) / (secs * 1000));
      a.volume = from + (end() - from) * k;
      if (k >= 1) { clearInterval(ramp); ramp = null; if (done) done(); }
    }, 40);
  }
  function play(url) {
    if (el) el.pause();
    const a = el = new Audio(url);
    a.volume = 0;
    last = url;
    a.addEventListener("ended", () => { if (el === a) mode === "battle" ? next() : rest(silence()); });
    const go = () => a.play().then(() => { blocked = null; if (el === a) fadeTo(gain, cfg.fade); })
      .catch(() => { blocked = go; });                 // the browser wants a click first: `poke` retries
    go();
  }
  const next = () => play(draw(cfg.tracks[mode], last));
  function rest(ms) {
    clearTimeout(wait);
    if (el) el.pause();
    el = null;
    wait = setTimeout(next, ms);
  }
  // the music of the mode in force fades out; then `then` starts the other one
  function change(then) {
    const mine = ++turn;
    clearTimeout(wait);
    fadeTo(0, cfg.fade, () => { if (mine !== turn) return; if (el) el.pause(); el = null; then(); });
  }
  return {
    set volume(v) { volume = v / 100; if (el && ramp === null) el.volume = gain(); },
    config(c) { cfg = c; if (mode) next(); },
    // the screen now open (or about to be): a change of mode changes the music
    enter(screen) {
      const m = modeOf(screen);
      if (m === mode) return;
      const first = mode === null;
      mode = m;
      if (!cfg) return;
      if (first) next();
      else change(() => (m === "battle" ? next() : rest(silence())));
    },
    poke() { if (blocked) blocked(); },
  };
})();

window.Music = Music;        // the game in the frame reaches it as `parent.Music`
fetch("/api/sounds").then(r => r.json()).then(r => Music.config(r.music)).catch(() => {});
