"""The wiki's RULES tab (wiki_rules.py): the numbers are the live ones and the filter finds a rule."""


from gartok import dialogue, group, recruit, wiki_rules


def test_the_rules_quote_the_live_constants():
    body = " ".join(" ".join(lines) for _, lines in wiki_rules.sections())
    assert f"against {dialogue.BASE_DC} +" in body
    assert f"-{recruit.SIZE_PENALTY} for every member of the whole guild past {recruit.FREE_SLOTS}" in body


def test_the_filter_finds_the_crowd_penalty():
    titles = [t for t, _ in wiki_rules.matching("crowd")]
    assert titles == ["Recruiting"]
    assert len(wiki_rules.matching("")) == len(wiki_rules.sections())


def test_the_group_size_line_names_every_term_capacity_adds():
    line = next(ln for ln in dict(wiki_rules.sections())["Groups, Leaders & Fame"] if "A group holds" in ln)
    assert f"holds {group.BASE_CAPACITY} + " in line
    for phrase, _, _ in group.CAPACITY_TERMS:
        assert phrase in line
