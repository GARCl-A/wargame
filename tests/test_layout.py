"""What the browser draws fits where it is drawn, in every language: no card that must be scrolled, no
words cut, past their box, over each other or glued to the next. The game is opened in a headless Edge
and measured there (`tests/layout.py`); a machine with no browser skips these."""

import pathlib
import re
import urllib.parse

import pytest

from gartok import hints, i18n, persist, recorder, tutorial, vocations
from gartok.draft import TEAM_SIZE
from gartok.group import Group
from gartok.guild import Guild
from gartok.web import session as web_session
from gartok.web.battle_session import BattleSession
from gartok.web.credits_session import CreditsSession
from gartok.web.draft_session import DraftSession
from gartok.web.guild_session import TABS as GUILD_TABS
from gartok.web.guild_session import GuildSession
from gartok.web.map_session import MapSession
from gartok.web.server import Game
from gartok.web.settings_session import SettingsSession
from gartok.web.wiki_session import WikiSession
from tests import browser as browser_mod
from tests.helpers import standard_unit
from tests.layout import AUDIT, HERE, Page

pytestmark = pytest.mark.slow
LANGUAGES = sorted(i18n.LANGUAGES)


@pytest.fixture(scope="module")
def browser():
    if browser_mod.find() is None:
        pytest.skip("no Edge or Chrome on this machine")
    b = browser_mod.Browser()
    yield b
    b.close()


@pytest.fixture
def saves(tmp_path, monkeypatch):
    monkeypatch.setattr(persist, "SAVE_DIR", str(tmp_path))
    yield tmp_path
    recorder.detach()


BROKEN = """<body style="margin:0;font:16px/1.2 serif"><style>div{margin:8px}</style>
<div id="scroll" style="height:40px;overflow:auto">a<br>b<br>c<br>d</div>
<div id="clipped" style="width:60px;overflow:hidden;white-space:nowrap">words cut by their own box</div>
<div id="ellipsis" style="width:60px;overflow:hidden;white-space:nowrap;text-overflow:ellipsis">words ended by dots</div>
<div id="spill" style="width:60px;white-space:nowrap;border:1px solid">words past the edge of a plate</div>
<div id="offscreen" style="position:absolute;left:-30px;top:300px">words past the window</div>
<div id="overlap" style="position:relative;height:20px"><span style="position:absolute;left:0">first run</span><span style="position:absolute;left:20px">second run</span></div>
<div id="crowded" style="display:flex"><p style="margin:0">one</p><p style="margin:0">two</p></div>
<div id="fine" style="display:flex;gap:12px"><p style="margin:0">one</p><p style="margin:0">two</p></div>
<div id="meant" data-layout-ok="a ribbon that runs off the page" style="width:60px;white-space:nowrap;border:1px solid">words past on purpose</div>
</body>"""


def test_the_audit_sees_each_kind_of_break_and_nothing_in_a_sound_box(browser):
    browser.open("data:text/html," + urllib.parse.quote(BROKEN))
    browser.wait("document.readyState === 'complete'")
    found = browser.eval(f"({AUDIT})({{fit: ['#scroll'], ellipsis: true}})")
    seen = {(f["kind"], f["where"].split(" ")[0]) for f in found}
    assert seen == {("scroll", "#scroll"), ("clipped", "#clipped"), ("ellipsis", "#ellipsis"), ("spill", "#spill"),
                    ("offscreen", "#offscreen"), ("overlap", "#overlap"), ("crowded", "#crowded")}


def test_every_screen_of_the_client_is_audited_or_owed():
    source = (pathlib.Path(HERE).parent / "gartok" / "web" / "client" / "shell.js").read_text(encoding="utf-8")
    table = source[source.index("const SCREENS = {"):]
    client = set(re.findall(r"^  (\w+): \{", table[:table.index("};")], re.MULTILINE))
    audited = {name.split(".")[0] for name in SCREENS}
    assert audited | OWED == client and not audited & OWED, "a new screen joins SCREENS here; one audited leaves OWED"


def _draft(step="vocation"):
    game = Game.title()
    game.session.new_guild()
    d = game.session
    d.tutorial.enabled = False
    if step != "vocation":
        d.choose_vocation(next(iter(vocations.VOCATIONS)))
        d.next()
    if step == "charter":
        for i in range(TEAM_SIZE):
            d.pick(i)
        d.next()
    return game


def _guild():
    units = [standard_unit() for _ in range(2)]
    return Guild(None, groups=[Group(units, node="lumber_yard", leader=units[0])], name="Ink Hands")


def _card_rows():
    """The rows and the spot of each card whose session draws some, from that session."""
    fight = Game.fight("wilds", 2, 3, seed=4).session
    return {
        "draft.pick": (DraftSession.tutorial_rows(None, "draft.pick"), None),
        "battle": (fight.tutorial_rows("battle"), fight.tutorial_spot("battle")),
        hints.FLANK: (fight.tutorial_rows(hints.FLANK), None),
        hints.WILDS: (MapSession(_guild()).tutorial_rows(hints.WILDS), None),
    }


ROW_SESSIONS = {DraftSession, BattleSession, MapSession}


def test_every_session_that_draws_card_rows_is_in_the_card_test():
    def family(cls):
        return {cls}.union(*(family(c) for c in cls.__subclasses__()))
    drawing = {c for c in family(web_session.Session) if "tutorial_rows" in vars(c)} - {web_session.Session}
    assert drawing == ROW_SESSIONS, "a session draws rows on its tutorial card: give them to `_card_rows`"


@pytest.mark.parametrize("lang", LANGUAGES)
def test_every_tutorial_card_is_read_whole_without_scrolling(browser, saves, lang):
    i18n.set_language(lang)
    rows = _card_rows()
    game = _draft()
    d = game.session
    d.tutorial = tutorial.TutorialState()
    shown = {"key": None}
    d.tutorial_key = lambda: shown["key"]
    d.tutorial_rows = lambda key: rows.get(key, ((), None))[0]
    d.tutorial_spot = lambda key: rows.get(key, ((), None))[1]
    page = Page(browser, game)
    try:
        broken = {}
        for key in tutorial.TUTORIALS:
            shown["key"] = key
            title = tutorial.card(key)["title"]
            browser.eval("(document.getElementById('tut-veil')?.remove(), api('/api/screen').then(() => 1))")
            browser.wait(f"document.querySelector('#tut-card h2')?.textContent === {title!r}".replace("\\'", "\\u0027"))
            page.still()
            found = page.audit("#tut-veil", fit=["#tut-card"], shot=f"card-{key}-{lang}")
            if found:
                broken[key] = found
        assert not broken, "\n" + "\n".join(f"{key}\n  " + "\n  ".join(lines) for key, lines in broken.items())
    finally:
        page.close()


def _map():
    session = MapSession(_guild())
    session.guild.tutorial.enabled = False
    return session


def _aside(cls):
    return lambda: Game(cls(lambda: None))


SCREENS = {
    "title": Game.title,
    "draft.vocation": lambda: _draft("vocation"),
    "draft.pick": lambda: _draft("pick"),
    "draft.charter": lambda: _draft("charter"),
    "map": lambda: Game(_map()),
    **{f"guild.{tab}": (lambda tab=tab: Game(GuildSession(_map(), tab))) for tab, _ in GUILD_TABS},
    "wiki": _aside(WikiSession),
    "settings": _aside(SettingsSession),
    "credits": _aside(CreditsSession),
}


OWED = {"battle", "hub", "talk", "report", "talents", "arena", "hunt", "watch"}      # docs/plans/backlog.md


@pytest.mark.parametrize("lang", LANGUAGES)
@pytest.mark.parametrize("name", sorted(SCREENS))
def test_a_screen_draws_nothing_cut_spilled_or_glued(browser, saves, name, lang):
    i18n.set_language(lang)
    page = Page(browser, SCREENS[name]())
    try:
        found = page.audit(shot=f"screen-{name}-{lang}")
        assert not found, "\n" + "\n".join(found)
    finally:
        page.close()
