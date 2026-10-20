from collections import deque
from statistics import mean

from .schemas import Intervention, Sample
from .sensing import ACTIONS, issues


class MeasurementCoach:
    BASELINE = 5.0
    RESPONSE = 3.0
    OBSERVE = 5.0
    COOLDOWN = 8.0

    def __init__(self, passive=False):
        self.history = deque(maxlen=40)
        self.interventions: list[Intervention] = []
        self.active: Intervention | None = None
        self.cooldown_until = 0
        self.pending_issue = None
        self.issue_since = 0
        self.passive = passive
        self.baseline: list[Sample] = []

    @staticmethod
    def window_metrics(samples: list[Sample]):
        quality = [s.sqi for s in samples if s.sqi is not None]
        enough = len(samples) >= 8 and samples[-1].t-samples[0].t >= 3.5
        sqi = mean(quality) if enough and len(quality) >= 8 else None
        usable = mean(s.usable for s in samples) if enough else None
        return sqi, usable

    def update(self, sample: Sample) -> Intervention | None:
        self.history.append(sample)
        if self.passive:
            return None
        if self.active:
            item = self.active
            if sample.t >= item.started_at+self.RESPONSE+self.OBSERVE:
                post = [s for s in self.history
                        if item.started_at+self.RESPONSE <= s.t < item.started_at+self.RESPONSE+self.OBSERVE]
                item.after_sqi, item.after_usable = self.window_metrics(post)
                item.evaluated_at = sample.t
                if item.before_sqi is not None and item.after_sqi is not None:
                    item.delta = round(item.after_sqi-item.before_sqi, 3)
                    item.outcome = ("improved" if item.delta >= 0.08 else
                                    "worsened" if item.delta <= -0.08 else "unchanged")
                else:
                    item.outcome = "inconclusive"
                self.active = None
                self.cooldown_until = sample.t+self.COOLDOWN
                self.pending_issue = None
            return None
        eligible = issues(sample)
        issue = eligible[0] if eligible else None
        if issue != self.pending_issue:
            self.pending_issue, self.issue_since = issue, sample.t
        if sample.t < self.BASELINE or sample.t < self.cooldown_until:
            return None
        if issue is None or sample.t-self.issue_since < self.BASELINE:
            return None
        self.baseline = [s for s in self.history if sample.t-self.BASELINE <= s.t < sample.t]
        sqi, usable = self.window_metrics(self.baseline)
        item = Intervention(id=f"intervention-{len(self.interventions)+1}", issue=issue,
                            action=ACTIONS[issue], started_at=sample.t, before_sqi=sqi, before_usable=usable)
        self.interventions.append(item)
        self.active = item
        return item

    def finish(self, t: float):
        if self.active:
            self.active.outcome = "inconclusive"
            self.active.evaluated_at = t
            self.active = None
