"""License guard core: pure Python, no framework or database imports.

Kept dependency-free on purpose so it can later become a standalone open-source library
and be tested in isolation.

Checks an AI answer against the licenses of the content it bought:
  1. Verbatim copying  -> longest run of consecutive words shared with a source
                          must not exceed the license's max_quote_words.
  2. Attribution       -> if required, the answer must cite the source.
  3. Expiry            -> content may only be used while its pass is valid.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

_WORD = re.compile(r"[a-z0-9]+")
_SENTENCE = re.compile(r"(?<=[.!?])\s+")


def words(text: str) -> list[str]:
    return _WORD.findall(text.lower())


def longest_common_run(a: list[str], b: list[str]) -> tuple[int, int]:
    """Longest run of consecutive identical words between a and b.
    Returns (length, start index in a). Dynamic programming, O(len(a) * len(b))."""
    best_len, best_start = 0, 0
    prev = [0] * (len(b) + 1)
    for i in range(1, len(a) + 1):
        cur = [0] * (len(b) + 1)
        ai = a[i - 1]
        for j in range(1, len(b) + 1):
            if ai == b[j - 1]:
                cur[j] = prev[j - 1] + 1
                if cur[j] > best_len:
                    best_len, best_start = cur[j], i - cur[j]
        prev = cur
    return best_len, best_start


@dataclass
class Item:
    resource_id: str
    path: str
    title: str
    text: str
    license_id: str
    license_type: str           # "read" | "quote"
    max_quote_words: int
    attribution_required: bool
    expires_at: datetime
    grant_id: str = ""


@dataclass
class ItemResult:
    resource_id: str
    grant_id: str
    license_id: str
    used: bool
    how_used: str               # "quoted" | "paraphrased" | "not_used"
    longest_copied_run: int
    max_quote_words: int
    cited: bool
    copied_excerpt: str = ""
    violations: list[dict] = field(default_factory=list)


def is_cited(answer: str, item: Item) -> bool:
    low = answer.lower()
    return any(marker.lower() in low for marker in (item.resource_id, item.path, item.title) if marker)


def check(answer: str, items: list[Item], now: datetime | None = None) -> list[ItemResult]:
    now = now or datetime.now(timezone.utc)
    answer_words = words(answer)
    results = []
    for item in items:
        run, start = longest_common_run(answer_words, words(item.text))
        cited = is_cited(answer, item)
        used = cited or run >= 4
        how = "quoted" if run > 8 else ("paraphrased" if used else "not_used")
        res = ItemResult(
            resource_id=item.resource_id, grant_id=item.grant_id, license_id=item.license_id,
            used=used, how_used=how, longest_copied_run=run, max_quote_words=item.max_quote_words,
            cited=cited, copied_excerpt=" ".join(answer_words[start:start + run]) if run else "",
        )
        if run > item.max_quote_words:
            res.violations.append({
                "type": "verbatim_copy", "resource_id": item.resource_id,
                "message": f"{run} consecutive words copied; license {item.license_id} allows {item.max_quote_words}",
                "excerpt": res.copied_excerpt,
            })
        if used and item.attribution_required and not cited:
            res.violations.append({
                "type": "missing_attribution", "resource_id": item.resource_id,
                "message": f"License {item.license_id} requires citing '{item.title}'",
            })
        if used and item.expires_at <= now:
            res.violations.append({
                "type": "license_expired", "resource_id": item.resource_id,
                "message": "Content used after its access pass expired",
            })
        results.append(res)
    return results


def all_violations(results: list[ItemResult]) -> list[dict]:
    return [v for r in results for v in r.violations]


def deterministic_fix(answer: str, items: list[Item], results: list[ItemResult]) -> str:
    """Fallback repair without an LLM:
    - drop sentences that contain an over-limit verbatim run
    - append missing citations
    """
    by_id = {i.resource_id: i for i in items}
    sentences = _SENTENCE.split(answer.strip())
    kept = []
    for sentence in sentences:
        sw = words(sentence)
        bad = False
        for r in results:
            item = by_id[r.resource_id]
            if any(v["type"] == "verbatim_copy" for v in r.violations):
                run, _ = longest_common_run(sw, words(item.text))
                if run > item.max_quote_words:
                    bad = True
        if not bad:
            kept.append(sentence)
    fixed = " ".join(kept).strip()
    missing = [by_id[r.resource_id] for r in results
               if any(v["type"] == "missing_attribution" for v in r.violations)]
    if missing:
        fixed += "\n\nSources: " + "; ".join(f"{m.title} [{m.resource_id}]" for m in missing)
    return fixed
