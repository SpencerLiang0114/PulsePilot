import json
import time
from uuid import uuid4

import pytest
from pydantic import ValidationError
from test_sensing_agent import proposal

from pulsepilot.orchestration.contracts import CoachEvent, ReportEvent
from pulsepilot.orchestration.tools import get_quality_context, get_report_evidence
from pulsepilot.reports import build_report
from pulsepilot.schemas import SessionConfig


def coach_event(**updates):
    _, context = proposal()
    return CoachEvent(**{
        "session_id": str(uuid4()), "event_id": str(uuid4()), "issued_at": time.monotonic(),
        "measurement_timestamp": context.sample_at, "ai_consent": True, "purpose": "select",
        "context": get_quality_context(context), **updates,
    })


def report_event(**updates):
    return ReportEvent(**{
        "session_id": str(uuid4()), "event_id": str(uuid4()), "issued_at": time.monotonic(),
        "measurement_timestamp": 0.0, "ai_consent": True,
        "bundle": get_report_evidence(build_report(SessionConfig(), [], [])), **updates,
    })


def test_typed_event_roundtrip_and_bounded_privacy():
    for event in (coach_event(), report_event()):
        assert type(event).model_validate_json(event.model_dump_json()) == event
        encoded = event.model_dump_json()
        for key in ("waveform", "landmarks", "bbox", "samples", "api_key", "input_image"):
            assert key not in encoded
    assert len(coach_event().context.outcomes) <= 6


@pytest.mark.parametrize("mutation", [
    {"session_id": "another person"}, {"event_type": "frame"}, {"issued_at": "10"},
    {"measurement_timestamp": float("nan")}, {"ai_consent": "true"}, {"unexpected": True},
])
def test_strict_event_fields(mutation):
    data = coach_event().model_dump()
    data.update(mutation)
    with pytest.raises(ValidationError):
        CoachEvent.model_validate(data)


def test_missing_context_and_raw_image_fields_rejected():
    data = coach_event().model_dump()
    del data["context"]
    with pytest.raises(ValidationError):
        CoachEvent.model_validate(data)
    data = coach_event().model_dump()
    data["context"]["quality"]["waveform"] = [1, 2]
    with pytest.raises(ValidationError):
        CoachEvent.model_validate(data)
    json.dumps(coach_event().model_dump(), allow_nan=False)
