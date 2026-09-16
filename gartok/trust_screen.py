"""The Bankers' trust mission: offered and turned in at the City (Ankareth),
same "one job out at a time" shape `missions.py` already gives every giver --
this is a dedicated screen rather than a reuse of `tanner_screen.py` because
the flavor (a test of trust, not a gathering job) and giver ("bankers", not
"tanner") are different enough to read as their own place, even though the
underlying mechanism (`missions.accept`/`can_turn_in`/`turn_in`) is identical.

Accepting hands the signer a sealed chest (`missions.TRUST_CHEST.starting_item`)
instead of asking the guild to gather anything; the "goal" `turn_in` counts is
a letter of receipt, traded for the chest at Ledger Hold
(`ledger_screen.py`) once the group gets there safely.
"""

from . import missions
from .ui.mission_offer_screen import MissionOfferScreen


class TrustScreen(MissionOfferScreen):
    TEMPLATE = missions.TRUST_CHEST

    @property
    def title_text(self):
        return "THE BANKERS"

    @property
    def subtitle_text(self):
        return '"Prove the guild can be trusted with something precious."'

    @property
    def accept_label(self):
        return "ACCEPT THE TEST OF TRUST"

    @property
    def leave_label(self):
        return "LEAVE THE BANKERS"

    def get_template(self):
        return self.TEMPLATE

    def get_req_str(self, t):
        return f"carry: {t.starting_item}  ·  bring back: {t.goal_item}  ·  deadline: {t.deadline_days} days"

    def get_status_str(self, t, progress, ready, days_left):
        if ready:
            return f"{t.goal_item} in hand  ·  {days_left} day(s) left"
        return f"carrying the sealed chest to Ledger Hold  ·  {days_left} day(s) left"

    def get_turn_in_label(self, t, progress, ready):
        return "TURN IN THE LETTER" if ready else "NOT BACK YET"

    def get_success_notice(self, reward):
        return "the Bankers accept the letter -- your trust is earned."
