"""
AI service — calls Anthropic Claude to:
  1. Predict TAT and breach probability for an order.
  2. Explain risk factors in plain English for the dashboard.
"""
from __future__ import annotations

import json
import logging
from typing import Any

import anthropic

from config import get_settings
from utils.sla import elapsed_days

logger = logging.getLogger(__name__)
settings = get_settings()


def _build_order_context(order: Any) -> str:
    """Build a compact JSON summary of the order for the prompt."""
    return json.dumps(
        {
            "order_id": order.id,
            "lens_type": order.lens_type,
            "lens_index": order.lens_index,
            "coating": order.coating,
            "current_stage": order.stage,
            "elapsed_days": elapsed_days(order.placed_at),
            "sla_days": order.sla_days,
            "inv_status": order.inv_status,
            "store": order.store_location,
            "status_history": [
                {"from": log.from_stage, "to": log.to_stage, "reason": log.reason}
                for log in (order.status_logs or [])
            ],
        },
        default=str,
    )


SYSTEM_PROMPT = """
You are an operations AI for Eluno, an eyewear brand.
You receive eyewear order data and must predict:
  - predicted_tat: integer (total calendar days from placement to delivery)
  - breach_prob: float 0-1 (probability of SLA breach)
  - risk_level: "low" | "medium" | "high"
  - reasoning: 1-2 sentences explaining the key risk factors

Typical SLA benchmarks:
  Single Vision: 3 days, Progressive: 7 days, Bifocal: 5 days, Office: 4 days.

High-risk signals: QC Check with elapsed > 80% SLA, Photochromic/Polarised coating delays,
high-index lenses (1.67+) needing sourcing, repeat rework loops, stuck stages.

Respond ONLY with valid JSON — no markdown, no explanation outside the JSON.
Schema: {"predicted_tat": int, "breach_prob": float, "risk_level": str, "reasoning": str}
""".strip()


async def predict_tat(order: Any) -> dict:
    """
    Call Claude to predict TAT and risk for a single order.
    Returns a dict with keys: predicted_tat, breach_prob, risk_level, reasoning.
    Falls back to a rule-based estimate if the API call fails.
    """
    if not settings.anthropic_api_key:
        return _rule_based_fallback(order)

    try:
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=256,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": f"Analyse this order and respond with JSON:\n{_build_order_context(order)}",
                }
            ],
        )
        raw = message.content[0].text.strip()
        return json.loads(raw)
    except Exception as exc:
        logger.warning("AI predict_tat failed (%s) — using rule-based fallback", exc)
        return _rule_based_fallback(order)


def _rule_based_fallback(order: Any) -> dict:
    """Deterministic heuristic when the API is unavailable."""
    elapsed = elapsed_days(order.placed_at)
    sla = order.sla_days
    pct = elapsed / sla if sla else 1.0

    # Each sourced lens adds +2 days
    extra = 2 if order.inv_status == "sourced" else 0

    # High-index or photochromic adds +1
    if order.lens_index in ("1.67", "1.74") or order.coating in ("Photochromic", "Polarised"):
        extra += 1

    predicted = sla + extra
    breach_prob = min(1.0, pct + (0.2 if extra else 0))

    if breach_prob >= 0.7:
        risk = "high"
    elif breach_prob >= 0.4:
        risk = "medium"
    else:
        risk = "low"

    return {
        "predicted_tat": predicted,
        "breach_prob": round(breach_prob, 2),
        "risk_level": risk,
        "reasoning": (
            f"Rule-based estimate: {elapsed}d elapsed of {sla}d SLA. "
            f"Extra days from sourcing/coating: {extra}."
        ),
    }