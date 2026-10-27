import json
import logging
from collections import deque

from .contracts import GraphOutcome


class Telemetry:
    """Only allowlisted metadata leaves this bounded session-local collector."""

    def __init__(self):
        self.records = deque(maxlen=256)

    def record(self, outcome: GraphOutcome):
        item = outcome.model_dump(exclude={"action", "analysis"})
        self.records.append(item)
        logging.getLogger("pulsepilot.agents").info("agent_event %s", json.dumps(item, allow_nan=False))
