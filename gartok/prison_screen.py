"""Prison: pay a minor criminal's bail and try to recruit them.

The taverna's screen, with one difference: the strangers here are the guild's
weekly `prison_pool`, and their bail (in copper) is paid before the pitch is even
rolled. The payment gives a +2 bonus to the Charisma contest, representing their
gratitude. If the pitch fails they walk free and take the money with them.
"""

from . import recruit
from .constants import fmt_money
from .taverna_screen import TavernaScreen

BAIL_BONUS = (2, "paid bail")


class PrisonScreen(TavernaScreen):
    LIST_LABEL = "PRISONERS IN THE CELLS"
    EMPTY_LIST = "The cells are empty right now.\nCome back when the crowd changes."
    REJECTED_LABEL = "WALKED FREE THIS WEEK"
    PITCH_BONUS = (BAIL_BONUS,)
    SEEN_KEY = "prison"

    def __init__(self, fonts, guild, party, node, on_done, candidates=None, title=None):
        pool = list(candidates) if candidates is not None else recruit.refresh_prison_pool(guild)
        super().__init__(fonts, guild, party, node, on_done, candidates=pool,
                         title=title or "CITY PRISON")

    def tutorial_key(self):
        return "prison"

    def _leave_label(self):
        return "LEAVE THE PRISON"

    def _barred(self, cand, member):
        return recruit.prison_barred(self.guild, cand, member)

    def _bar(self, cand, member):
        recruit.prison_bar(self.guild, cand, member)

    def _bail(self, cand):
        return recruit.bail_cost(cand)

    def _sub_extra(self):
        days_left = recruit.REFRESH_DAYS - (self.guild.clock.day - 1) % recruit.REFRESH_DAYS
        return f" · party holds {fmt_money(self._wealth())} · new faces in {days_left} day(s)"
