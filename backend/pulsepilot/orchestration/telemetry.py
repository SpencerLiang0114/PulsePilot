import json
import logging
from collections import deque

from ..schemas import AgentTrace
from .contracts import GraphOutcome


class Telemetry:
    """Only allowlisted metadata leaves this bounded session-local collector."""

    def __init__(self):
        self.records = deque(maxlen=256)

    def record(self, outcome: GraphOutcome):
        item = outcome.model_dump(exclude={"action", "analysis", "health_insights"})
        self.records.append(item)
        logging.getLogger("pulsepilot.agents").info("agent_event %s", json.dumps(item, allow_nan=False))

    def snapshot(self) -> list[AgentTrace]:
        return [AgentTrace(
            **{key: item[key] for key in ("event_id", "session_id", "event_type", "graph_version",
                                          "model_identifier", "route", "status", "model_latency_ms",
                                          "graph_latency_ms")},
            validation_result=item["validation"]["valid"], fallback_reason=item["validation"]["reason"],
            api_requests=item["usage"]["requests"], input_tokens=item["usage"]["input_tokens"],
            output_tokens=item["usage"]["output_tokens"],
        ) for item in self.records]
