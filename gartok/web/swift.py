"""The swift resolution of a fight in the browser: the clean-stomp estimate (`autowin`) of the fight now
due, run on a thread so the screen never waits for it, and what the browser is told of it."""

from .. import autowin

POLL_MS = 1200


class Look:
    """The estimate for one fight at a time. `of(key, ...)` starts it the first time it is asked about
    `key` (a fight is told apart by its band or party) and answers `state()` ever after."""

    def __init__(self):
        self.estimator = autowin.AutoWinEstimator()
        self.key = None

    def of(self, key, squad, foes, scenario, daylight, lethal):
        if key != self.key:
            self.key = key
            self.estimator.request(list(squad), list(foes), scenario=scenario, daylight=daylight, lethal=lethal)
        return self.state()

    def state(self):
        """`{"computing": bool, "pct", "runs", "eligible"}` for the screen; None before any fight was asked."""
        if self.key is None:
            return None
        est = self.estimator.result
        if est is None:
            return {"computing": True, "pct": 0, "runs": 0, "eligible": False, "poll": POLL_MS}
        return {"computing": False, "pct": round(est.stomp_rate * 100), "runs": est.iterations,
                "eligible": est.eligible, "poll": 0}

    @property
    def result(self):
        """The finished estimate when it makes the fight a clean stomp, else None."""
        est = self.estimator.result
        return est if est is not None and est.eligible else None

    def clear(self):
        self.key = None
        self.estimator.reset()
