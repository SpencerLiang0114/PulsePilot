import asyncio
import json
import os

import httpx
from pydantic import BaseModel

from .schemas import (
    DECISION_EXPLANATIONS,
    AgentDecision,
    Analysis,
    DecisionContext,
    DecisionResult,
    Report,
    ReportInterpretation,
    Statement,
)
from .timing import ADAPTIVE_DEADLINE

META_URL = "https://api.meta.ai/v1/chat/completions"
SYSTEM = """You interpret webcam rPPG measurement conditions, not cardiovascular health.
Use only supplied evidence. Never diagnose, give medical advice, invent observations,
claim physiological accuracy, or describe associations as causation.
Do not calculate statistics. Numerical results are rendered by deterministic tools.
Use plain concise English and no digits in narrative text. Distinguish facts,
possible explanations, and limitations. Never claim you saw images; you receive metrics only."""


def configured() -> bool:
    return bool(os.getenv("MODEL_API_KEY", "").strip())


async def structured(schema: type[BaseModel], payload: dict, instruction: str, *, usage: dict | None = None,
                     client: httpx.AsyncClient | None = None):
    key = os.getenv("MODEL_API_KEY", "").strip()
    if not key:
        raise RuntimeError("Meta key is not configured")
    if client is None:
        async with httpx.AsyncClient(timeout=httpx.Timeout(12.0, connect=4.0)) as owned:
            return await structured(schema, payload, instruction, usage=usage, client=owned)
    wire_schema = schema.model_json_schema()

    def require_fields(node):
        if isinstance(node, dict):
            node.pop("default", None)
            node.pop("title", None)
            if "properties" in node:
                node["required"] = list(node["properties"])
            for value in node.values():
                require_fields(value)
        elif isinstance(node, list):
            for value in node:
                require_fields(value)

    require_fields(wire_schema)
    response = await client.post(
        META_URL,
        headers={"Authorization": f"Bearer {key}"},
        json={
            "model": os.getenv("META_MODEL", "muse-spark-1.3"),
            "reasoning_effort": "minimal",
            "messages": [
                {"role": "system", "content": SYSTEM + "\n" + instruction},
                {"role": "user", "content": json.dumps(payload, allow_nan=False, separators=(",", ":"))},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": schema.__name__, "strict": True, "schema": wire_schema},
            },
        },
    )
    if usage is not None:
        usage["responses"] = usage.get("responses", 0)+1
    response.raise_for_status()
    body = response.json()
    if usage is not None:
        counts = body.get("usage") or {}
        for field in ("prompt_tokens", "completion_tokens"):
            count = counts.get(field)
            if type(count) is int and count >= 0:
                usage[field] = count
    content = body["choices"][0]["message"]["content"]
    return schema.model_validate_json(content)


def validate_decision(decision: AgentDecision, context: DecisionContext) -> bool:
    if decision.explanation != DECISION_EXPLANATIONS[decision.reason]:
        return False
    if decision.action_id is None:
        return decision.reason == "wait"
    if decision.reason == "wait" or decision.action_id not in {c.action_id for c in context.candidates}:
        return False
    if decision.reason == "try_alternative":
        return any(r.outcome in ("unchanged", "worsened") and r.action_id != decision.action_id
                   for r in context.outcomes)
    return True


class SensingDecisionAgent:
    DEADLINE = ADAPTIVE_DEADLINE

    async def decide(self, context: DecisionContext) -> DecisionResult:
        try:
            decision = await asyncio.wait_for(structured(
                AgentDecision,
                {"context": context.model_dump(), "supported_explanations": DECISION_EXPLANATIONS},
                "Select one eligible action_id, or null to abstain. Use only an offered reason and its exact "
                "supported explanation. Consider SQI trend, remaining time and recent outcomes. Prefer a useful "
                "alternative after unchanged or worsened outcomes and consider previously improved conditions. "
                "Inconclusive is insufficient evidence, not failure. "
                "You cannot alter measurements, thresholds or instructions. Never claim causal benefit.",
            ), timeout=self.DEADLINE)
            decision = AgentDecision.model_validate(decision.model_dump())
            if not validate_decision(decision, context):
                return DecisionResult(status="invalid")
            return DecisionResult(status="selected", decision=decision)
        except (TimeoutError, httpx.TimeoutException):
            return DecisionResult(status="timeout")
        except (ValueError, KeyError, IndexError, TypeError):
            return DecisionResult(status="invalid")
        except (httpx.HTTPError, RuntimeError, ImportError):
            return DecisionResult(status="unavailable")


async def analyze_report(report: Report) -> Report:
    try:
        interpretation = await structured(
            ReportInterpretation, {"claims": [c.model_dump() for c in report.claims]},
            "Select the most useful supplied claims for each report section. Copy each complete typed claim "
            "exactly, including its section, metric, value, evidence_id and text. Do not write new prose or "
            "modify a claim. Each section must contain one to four distinct claims from that section.",
        )
        interpretation = ReportInterpretation.model_validate(interpretation.model_dump())
        catalogue = {c.claim_id: c for c in report.claims}
        sections = {}
        for section in type(interpretation).model_fields:
            selected = getattr(interpretation, section)
            if len({c.claim_id for c in selected}) != len(selected):
                raise ValueError("Duplicate claims")
            statements = []
            for claim in selected:
                canonical = catalogue.get(claim.claim_id)
                if canonical is None or claim != canonical or claim.section != section:
                    raise ValueError("Unsupported claim")
                statements.append(Statement(
                    kind=canonical.statement_kind,
                    text=canonical.text, evidence_ids=[canonical.evidence_id],
                ))
            sections[section] = statements
        analysis = Analysis(**sections)
        return report.model_copy(update={"analysis": analysis, "analyst": "muse", "ai_status": "complete"})
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError, RuntimeError, ImportError):
        return report.model_copy(update={"ai_status": "unavailable"})
