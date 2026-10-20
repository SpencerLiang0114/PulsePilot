import json
import os
import re

import httpx
from pydantic import BaseModel

from .schemas import Analysis, CoachDecision, Intervention, Report, Sample

META_URL = "https://api.meta.ai/v1/chat/completions"
SYSTEM = """You interpret webcam rPPG measurement conditions, not cardiovascular health.
Use only supplied evidence. Never diagnose, give medical advice, invent observations,
claim physiological accuracy, or describe associations as causation.
Do not calculate statistics. Numerical results are rendered by deterministic tools.
Use plain concise English and no digits in narrative text. Distinguish facts,
possible explanations, and limitations. Never claim you saw images; you receive metrics only."""


def configured() -> bool:
    return bool(os.getenv("MODEL_API_KEY", "").strip())


async def structured(schema: type[BaseModel], payload: dict, instruction: str):
    key = os.getenv("MODEL_API_KEY", "").strip()
    if not key:
        raise RuntimeError("Meta key is not configured")
    async with httpx.AsyncClient(timeout=httpx.Timeout(12.0, connect=4.0)) as client:
        response = await client.post(
            META_URL,
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": os.getenv("META_MODEL", "muse-spark-1.3"),
                "messages": [
                    {"role": "system", "content": SYSTEM + "\n" + instruction},
                    {"role": "user", "content": json.dumps(payload, allow_nan=False)},
                ],
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {"name": schema.__name__, "strict": True, "schema": schema.model_json_schema()},
                },
            },
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return schema.model_validate_json(content)


def safe_text(text: str) -> bool:
    prohibited = r"\d|diagnos|arrhythm|tachycard|bradycard|heart disease|healthy heart|accurate heart|improved accuracy|guarantee"
    return not re.search(prohibited, text, re.IGNORECASE)


async def enrich_coach(item: Intervention, sample: Sample) -> CoachDecision | None:
    try:
        decision = await structured(
            CoachDecision,
            {"eligible_issue": item.issue, "action": item.action,
             "camera": sample.camera.model_dump(), "sqi": sample.sqi, "fps": sample.fps},
            "Explain why the single eligible correction may help the measurement. "
            "Return exactly that issue. Do not propose another action or claim an outcome.",
        )
        if decision.issue != item.issue or not safe_text(decision.explanation):
            return None
        return decision
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError, RuntimeError):
        return None


async def analyze_report(report: Report) -> Report:
    try:
        analysis = await structured(
            Analysis, {"evidence": report.evidence},
            "Write the four report sections. Every statement must cite existing evidence_ids. "
            "Explain meaningful trends and limitations, not just restate facts. Only describe an "
            "intervention as improved when its cited record explicitly has outcome improved.",
        )
        for section in analysis.model_dump().values():
            for item in section:
                refs = item["evidence_ids"]
                if any(ref not in report.evidence for ref in refs) or not safe_text(item["text"]):
                    raise ValueError("Unsupported statement")
                if re.search(r"\bimprov", item["text"], re.IGNORECASE):
                    cited = [i for i in report.interventions if i.id in refs]
                    if not cited or any(i.outcome != "improved" for i in cited):
                        raise ValueError("Unsupported intervention outcome")
        return report.model_copy(update={"analysis": analysis, "analyst": "muse", "ai_status": "complete"})
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError, RuntimeError):
        return report.model_copy(update={"ai_status": "unavailable"})
