"""Meta HTTP adaptation; no alternative provider, image tools, or autonomous tool loop."""
import asyncio
import os
from contextvars import ContextVar

from .. import agents
from ..schemas import DECISION_EXPLANATIONS
from .contracts import AnalysisProposal, CoachEvent, CoachProposal, ModelUsage, ReportEvent

# Per invocation, including concurrent sessions; never stored on a shared provider instance.
invocation_usage: ContextVar[dict | None] = ContextVar("invocation_usage", default=None)


class MetaProvider:
    TIMEOUT = 10.0  # Network timeout is independently set by the HTTP adapter.

    @property
    def identifier(self):
        return os.getenv("META_MODEL", "muse-spark-1.3")

    async def _generate(self, schema, event, payload, instruction):
        if not event.ai_consent:
            raise RuntimeError("Model transfer not authorized")
        if not agents.configured():
            raise RuntimeError("Meta key is not configured")
        usage = invocation_usage.get()
        if usage is not None:
            usage["requests"] += 1
        return await asyncio.wait_for(
            agents.structured(schema, payload, instruction, usage=usage), timeout=self.TIMEOUT,
        )

    async def propose(self, event: CoachEvent) -> CoachProposal:
        return await self._generate(CoachProposal, event, {
            "session_id": event.session_id, "event_id": event.event_id,
            "context": event.context.model_dump(), "purpose": event.purpose,
            "supported_explanations": DECISION_EXPLANATIONS,
        }, "Return the supplied session_id and event_id exactly. Select only an eligible action_id and its "
           "matching issue_id, or null for both with reason wait. Copy the exact supported explanation for "
           "your reason. Use try_alternative only after a different action was unchanged or worsened. "
           "Inconclusive is not failure. For explain, explain the single committed action; never replace it. "
           "You recommend a correction for the user to perform; you do not perform it or change thresholds.")

    async def analyze(self, event: ReportEvent) -> AnalysisProposal:
        return await self._generate(AnalysisProposal, event, {
            "session_id": event.session_id, "event_id": event.event_id,
            "claims": [c.model_dump() for c in event.bundle.claims],
        }, "Return the supplied session_id and event_id exactly. Select one to four distinct supplied claims "
           "for each matching section. Copy claim_id, evidence_id and claim_type exactly. The server renders "
           "all factual prose. Do not invent claims, numbers, observations, or recommendations.")


def read_usage(values: dict) -> ModelUsage:
    return ModelUsage(input_tokens=values.get("prompt_tokens"), output_tokens=values.get("completion_tokens"),
                      requests=values["requests"])
