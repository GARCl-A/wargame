"""Keywords: a reserved word of the rules that always means one thing, wherever it is written.

A description, a combat log line or a tooltip that uses the rule says only the word; the full text
lives in the catalog (`name.keyword.<id>`, `desc.keyword.<id>`), once, and the wiki's KEYWORDS chapter shows it
(`wiki_terms.terms()`). A condition is not a keyword: it has its own registry (`conditions.py`).
"""

from dataclasses import dataclass

from . import i18n


@dataclass(frozen=True)
class Keyword:
    id: str

    @property
    def name(self) -> str:
        return i18n.name("keyword", self.id)

    @property
    def text(self) -> str:
        return i18n.desc("keyword", self.id)


_KEYWORDS = [Keyword(id=i) for i in ("brutal", "critical_hit", "flanked", "shove", "dying", "knocked_out", "morale", "reach", "distance")]

KEYWORDS = {k.id: k for k in _KEYWORDS}


def get(keyword_id: str) -> Keyword | None:
    return KEYWORDS.get(keyword_id)


def all_keywords() -> list[Keyword]:
    return list(_KEYWORDS)
