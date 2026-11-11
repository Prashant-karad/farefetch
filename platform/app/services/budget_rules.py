"""Plain-English budget rules -> structured limits.
"Never spend more than $1 a day, max 5 cents per article, ask me above 3 cents" -> numbers."""

import re
from decimal import Decimal, InvalidOperation

from app.services import llm

UNITS_PER_DOLLAR = 10_000

_MONEY = r"\$?\s*(\d+(?:\.\d+)?)\s*(cents?|c\b|dollars?|usd)?"


def _to_units(amount: str, unit: str | None) -> int:
    value = Decimal(amount)
    if unit and unit.lower().startswith(("cent", "c")):
        value = value / 100
    return int(value * UNITS_PER_DOLLAR)


def heuristic_parse(rule: str) -> dict:
    text = rule.lower()
    out: dict[str, int | None] = {"max_per_item": None, "max_per_day": None, "approval_threshold": None}
    patterns = {
        "max_per_day": _MONEY + r"[^.,;]*?\b(per day|a day|daily|each day)",
        "max_per_item": _MONEY + r"[^.,;]*?\b(per item|per article|each|per page|per purchase|per resource)",
        "approval_threshold": r"(?:above|over|more than)\s*" + _MONEY + r"[^.,;]*?\b(ask|approv)",
    }
    for key, pattern in patterns.items():
        m = re.search(pattern, text)
        if m:
            out[key] = _to_units(m.group(1), m.group(2))
    # "ask me before anything over X" (ask comes first)
    if out["approval_threshold"] is None:
        m = re.search(r"(?:ask|approv)[^.;]*?(?:above|over|more than)\s*" + _MONEY, text)
        if m:
            out["approval_threshold"] = _to_units(m.group(1), m.group(2))
    return out


async def parse_rule(rule: str) -> dict:
    data = await llm.generate_json(
        "Convert this AI-agent spending rule into JSON with USD amounts as numbers or null: "
        '{"max_per_item_usd": number|null, "max_per_day_usd": number|null, '
        '"approval_threshold_usd": number|null, "explanation": str}.\n\nRULE: ' + rule
    )
    if data:
        try:
            def units(key: str) -> int | None:
                v = data.get(key)
                return None if v is None else int(Decimal(str(v)) * UNITS_PER_DOLLAR)
            return {"max_per_item": units("max_per_item_usd"), "max_per_day": units("max_per_day_usd"),
                    "approval_threshold": units("approval_threshold_usd"),
                    "explanation": str(data.get("explanation", ""))[:500], "source": "llm"}
        except (InvalidOperation, ValueError, TypeError):
            pass
    parsed = heuristic_parse(rule)
    return {**parsed, "explanation": "parsed with pattern rules", "source": "heuristic"}
