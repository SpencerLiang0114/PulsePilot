from collections import deque
from statistics import mean

from .schemas import (
    DECISION_EXPLANATIONS,
    CoachingState,
    DecisionContext,
    DecisionResult,
    Intervention,
    OutcomeRecord,
    Sample,
)
from .sensing import candidate_actions, issues, observations
from .timing import ADAPTIVE_DEADLINE

METRIC_TOLERANCES = {"brightness": 10, "light_imbalance": 10, "light_change": 10,
                     "roll_degrees": 5, "fps": 3}


def conditions_changed(previous, current):
    return any(key in previous and abs(float(value)-previous[key]) > METRIC_TOLERANCES.get(key, .1)
               for key, value in current.items())


class OutcomeMemory:
    """Session-local summaries; insufficient evidence never counts as a failed action."""

    def __init__(self):
        self.records: deque[OutcomeRecord] = deque(maxlen=6)
        self.unsuccessful: dict[str, dict[str, float]] = {}

    def record(self, item: Intervention):
        self.records.append(OutcomeRecord(
            action_id=item.action_id, decision_source=item.decision_source, outcome=item.outcome,
            before_sqi=item.before_sqi, after_sqi=item.after_sqi,
            before_usable=item.before_usable, after_usable=item.after_usable,
            environmental_changes=item.environmental_changes,
        ))
        if item.outcome in ("unchanged", "worsened"):
            self.unsuccessful[item.action_id] = item.after_camera.copy()

    def observe(self, detected):
        for action_id in list(self.unsuccessful):
            if action_id not in detected:
                del self.unsuccessful[action_id]

    def filter(self, candidates):
        eligible = []
        for candidate in candidates:
            previous = self.unsuccessful.get(candidate.action_id)
            if previous is None or candidate.issue in ("face", "cadence"):
                eligible.append(candidate)
                continue
            changed = conditions_changed(previous, candidate.observations)
            if changed:
                eligible.append(candidate)
        latest = {record.action_id: record.outcome for record in self.records}
        return sorted(eligible, key=lambda c: (latest.get(c.action_id) != "improved", c.priority))


class MeasurementCoach:
    BASELINE = 5.0
    RESPONSE = 3.0
    OBSERVE = 5.0
    COOLDOWN = 8.0
    FRESHNESS = 1.5

    def __init__(self, passive=False, mode="rules", rule_status="rules"):
        self.history: deque[Sample] = deque(maxlen=40)
        self.interventions: list[Intervention] = []
        self.active: Intervention | None = None
        self.cooldown_until = 0.0
        self.passive = passive or mode == "passive"
        self.mode = mode
        self.rule_status = rule_status
        self.baseline: list[Sample] = []
        self.state: CoachingState = "MONITORING"
        self.proposal: DecisionContext | None = None
        self.issue_since: dict[str, float] = {}
        self.memory = OutcomeMemory()
        self.sequence = 0
        self.closed = False

    @staticmethod
    def window_metrics(samples: list[Sample]):
        quality = [s.sqi for s in samples if s.sqi is not None]
        enough = len(samples) >= 8 and samples[-1].t-samples[0].t >= 3.5
        sqi = mean(quality) if enough and len(quality) >= 8 else None
        usable = mean(s.usable for s in samples) if enough else None
        return sqi, usable

    @staticmethod
    def environment(samples: list[Sample]) -> dict[str, float]:
        values = [observations(sample) for sample in samples]
        return {key: mean(float(v[key]) for v in values if key in v)
                for key in dict.fromkeys(key for v in values for key in v)}

    def candidates(self, sample):
        persistent = {issue for issue, since in self.issue_since.items() if sample.t-since >= self.BASELINE}
        return self.memory.filter(candidate_actions(sample, persistent))

    def update(self, sample: Sample, remaining: float = 180) -> Intervention | None:
        if self.closed:
            return None
        gap = self.history and sample.t-self.history[-1].t > self.FRESHNESS
        self.history.append(sample)
        if gap:
            self.issue_since.clear()
            self.proposal = None
            if self.active:
                self._finish_active(sample.t, interrupted=True)
            else:
                self.state = "MONITORING"
        detected = issues(sample)
        self.memory.observe(detected)
        self.issue_since = {issue: self.issue_since.get(issue, sample.t) for issue in detected}
        if self.passive:
            return None
        if self.active:
            if sample.t >= self.active.started_at+self.RESPONSE+self.OBSERVE:
                self._finish_active(sample.t)
            else:
                self.state = "ACTING" if sample.t < self.active.started_at+self.RESPONSE else "OBSERVING"
            return None
        if sample.t < self.cooldown_until:
            self.state = "COOLDOWN"
            return None
        candidates = self.candidates(sample)
        if self.proposal:
            proposed_ids = {c.action_id for c in self.proposal.candidates}
            if any(i in detected for i in ("face", "cadence")) or not any(
                c.action_id in proposed_ids for c in candidates
            ):
                self.proposal = None
                self.state = "MONITORING"
            elif any(conditions_changed(p.observations, c.observations)
                     for p in self.proposal.candidates for c in candidates if p.action_id == c.action_id):
                self.proposal = None
                self.state = "MONITORING"
                return None
            elif sample.t-self.proposal.sample_at >= self.proposal.deadline_seconds:
                return self.resolve(self.proposal.proposal_id, DecisionResult(status="timeout"), sample, remaining)
            else:
                return None
        self.state = "MONITORING"
        if not candidates or remaining < self.RESPONSE+self.OBSERVE:
            return None
        if self.mode != "meta" or candidates[0].issue in ("face", "cadence"):
            status = "safety" if candidates[0].issue in ("face", "cadence") else self.rule_status
            return self._commit(candidates[0], sample, "rules", status)
        if remaining < self.RESPONSE+self.OBSERVE+ADAPTIVE_DEADLINE:
            return None
        self.proposal = self.decision_context(sample, remaining, candidates)
        self.state = "DECIDING"
        return None

    def decision_context(self, sample: Sample, remaining: float, candidates=None) -> DecisionContext:
        recent = [s for s in self.history if sample.t-self.BASELINE <= s.t <= sample.t]
        quality = [s.sqi for s in recent if s.sqi is not None]
        half = len(quality)//2
        self.sequence += 1
        return DecisionContext(
            proposal_id=self.sequence, sample_at=sample.t, camera=observations(sample), issues=issues(sample),
            sqi=sample.sqi, sqi_trend=mean(quality[half:])-mean(quality[:half]) if half else None,
            usable_fraction=mean(s.usable for s in recent),
            candidates=self.candidates(sample) if candidates is None else candidates,
            outcomes=list(self.memory.records), remaining_seconds=remaining,
            deadline_seconds=ADAPTIVE_DEADLINE,
        )

    def resolve(self, proposal_id: int, result: DecisionResult, sample: Sample, remaining: float):
        proposal = self.proposal
        if self.closed or proposal is None or proposal.proposal_id != proposal_id:
            return None
        if not self.history or sample is not self.history[-1]:
            return None
        self.proposal = None
        self.state = "MONITORING"
        candidates = [c for c in self.candidates(sample)
                      if c.action_id in {p.action_id for p in proposal.candidates}]
        if not candidates or remaining < self.RESPONSE+self.OBSERVE:
            return None
        if any(i in issues(sample) for i in ("face", "cadence")):
            return None
        decision = result.decision
        if sample.t-proposal.sample_at >= proposal.deadline_seconds:
            result = DecisionResult(status="timeout")
        if result.status == "selected" and decision is not None:
            from .agents import validate_decision

            if validate_decision(decision, proposal):
                if decision.action_id is None:
                    self.cooldown_until = sample.t+self.COOLDOWN
                    self.state = "COOLDOWN"
                    return None
                selected = next((c for c in candidates if c.action_id == decision.action_id), None)
                if selected is None:
                    return None
                return self._commit(selected, sample, "muse", "selected", decision.explanation)
            result = DecisionResult(status="invalid")
        return self._commit(candidates[0], sample, "rules", f"fallback_{result.status}")

    def _commit(self, candidate, sample, source, status, explanation=None):
        self.baseline = [s for s in self.history if sample.t-self.BASELINE <= s.t < sample.t]
        sqi, usable = self.window_metrics(self.baseline)
        item = Intervention(
            id=f"intervention-{len(self.interventions)+1}", action_id=candidate.action_id,
            issue=candidate.issue, action=candidate.instruction, started_at=sample.t,
            before_sqi=sqi, before_usable=usable, before_camera=self.environment(self.baseline),
            source=source, decision_source=source, explanation_source=source,
            decision_status=status, explanation=explanation or DECISION_EXPLANATIONS["persistent_issue"],
        )
        self.interventions.append(item)
        self.active = item
        self.state = "ACTING"
        return item

    def _finish_active(self, t, interrupted=False):
        item = self.active
        post = [s for s in self.history
                if item.started_at+self.RESPONSE <= s.t < item.started_at+self.RESPONSE+self.OBSERVE]
        item.after_camera = self.environment(post)
        item.environmental_changes = {key: round(value-item.before_camera[key], 4)
                                      for key, value in item.after_camera.items() if key in item.before_camera}
        if not interrupted:
            item.after_sqi, item.after_usable = self.window_metrics(post)
        item.evaluated_at = t
        if item.before_sqi is not None and item.after_sqi is not None:
            item.delta = round(item.after_sqi-item.before_sqi, 3)
            item.outcome = ("improved" if item.delta >= 0.08 else
                            "worsened" if item.delta <= -0.08 else "unchanged")
        else:
            item.outcome = "inconclusive"
        self.memory.record(item)
        self.active = None
        self.cooldown_until = t+self.COOLDOWN
        self.state = "COOLDOWN"

    def finish(self, t: float):
        self.closed = True
        self.proposal = None
        if self.active:
            self._finish_active(t, interrupted=True)
        self.state = "MONITORING"
