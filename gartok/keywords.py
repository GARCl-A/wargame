"""Keywords: a reserved word of the rules that always means one thing, wherever it is written.

A description, a combat log line or a tooltip that uses the rule says only the word; the full text
lives here, once, and the wiki's KEYWORDS chapter shows it (`wiki_terms.terms()`). A condition is not
a keyword: it has its own registry (`conditions.py`).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Keyword:
    id: str
    name: str
    text: str


_KEYWORDS = [
    Keyword(
        id="brutal",
        name="Brutal",
        text="Brutal N: the blow rolls the weapon's damage N more times, modifiers included, and adds "
             "them. It is still one blow with one hit roll. Brutal from several sources adds up: "
             "Brutal 1 and Brutal 1 make Brutal 2.",
    ),
]

KEYWORDS = {k.id: k for k in _KEYWORDS}


def get(keyword_id: str) -> Keyword | None:
    return KEYWORDS.get(keyword_id)


def all_keywords() -> list[Keyword]:
    return list(_KEYWORDS)
