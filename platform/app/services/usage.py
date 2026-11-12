"""License guard service: loads what the agent bought, checks its answer, repairs violations,
and stores a signed usage receipt the publisher can verify."""

import hashlib
import json

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import AccessGrant, Agent, License, Resource, UsageReceipt
from app.services import llm, page_text
from app.services.license_core import Item, all_violations, check, deterministic_fix
from app.services.passes import sign_receipt


class UsageError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


async def _source_text(resource) -> str:
    """Fetch the ORIGINAL content from the publisher (never trust the agent's copy)."""
    if resource.origin_url:  # the publisher's own website
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(resource.origin_url)
        resp.raise_for_status()
        return page_text.extract(resp.text, resp.headers.get("content-type", ""))[1]
    path = resource.path
    async with httpx.AsyncClient(base_url=settings.origin_url, timeout=10.0) as client:
        resp = await client.get(path)
    resp.raise_for_status()
    data = resp.json()
    return data["body"] if isinstance(data, dict) and "body" in data else json.dumps(data)


async def _llm_rewrite(answer: str, items: list[Item], violations: list[dict]) -> str | None:
    rules = "\n".join(
        f"- {i.title} [{i.resource_id}]: license '{i.license_type}', at most {i.max_quote_words} "
        f"consecutive words may be copied, citation {'required' if i.attribution_required else 'optional'}"
        for i in items
    )
    problems = "\n".join(f"- {v['type']}: {v['message']} {v.get('excerpt', '')}" for v in violations)
    prompt = (
        "Rewrite the ANSWER so it respects every content license below. Paraphrase copied passages "
        "in your own words, keep all facts, and cite each used source with its marker like [res_id]. "
        "Return only the rewritten answer.\n\n"
        f"LICENSES:\n{rules}\n\nVIOLATIONS FOUND:\n{problems}\n\nANSWER:\n{answer}"
    )
    return await llm.generate_text(prompt)


async def check_usage(session: AsyncSession, *, agent: Agent, answer: str, grant_ids: list[str],
                      auto_fix: bool = True) -> dict:
    if not grant_ids:
        raise UsageError(422, "no_grants", "Send the grant_ids of the content used in this answer")

    rows = (await session.execute(
        select(AccessGrant, Resource, License)
        .join(Resource, AccessGrant.resource_id == Resource.id)
        .join(License, AccessGrant.license_id == License.id)
        .where(AccessGrant.id.in_(grant_ids))
    )).all()
    if len(rows) != len(set(grant_ids)) or any(g.agent_id != agent.id for g, _, _ in rows):
        raise UsageError(403, "grant_not_yours", "Every grant must exist and belong to this agent")

    items = []
    for grant, resource, lic in rows:
        try:
            text = await _source_text(resource)
        except httpx.HTTPError:
            raise UsageError(502, "origin_unreachable", f"Could not load source text for {resource.path}")
        items.append(Item(
            resource_id=resource.id, path=resource.path, title=resource.title, text=text,
            license_id=lic.id, license_type=lic.type, max_quote_words=lic.max_quote_words,
            attribution_required=lic.attribution_required, expires_at=grant.expires_at, grant_id=grant.id,
        ))

    original_results = check(answer, items)
    original_violations = all_violations(original_results)
    final_answer, final_results, fixed_by = answer, original_results, None

    if original_violations and auto_fix:
        rewritten = await _llm_rewrite(answer, items, original_violations)
        if rewritten:
            candidate_results = check(rewritten, items)
            if not all_violations(candidate_results):
                final_answer, final_results, fixed_by = rewritten, candidate_results, "llm_rewrite"
        if fixed_by is None:
            final_answer = deterministic_fix(answer, items, original_results)
            final_results = check(final_answer, items)
            fixed_by = "deterministic_fix"

    final_violations = all_violations(final_results)
    passed = not final_violations
    answer_sha = hashlib.sha256(final_answer.encode()).hexdigest()
    item_dicts = [r.__dict__ for r in final_results]

    receipt = UsageReceipt(agent_id=agent.id, answer_sha256=answer_sha, items=item_dicts,
                           violations=original_violations, passed=passed)
    session.add(receipt)
    await session.flush()
    receipt.signature = sign_receipt({
        "rcp": receipt.id, "sub": agent.id, "answer_sha256": answer_sha, "passed": passed,
        "items": [{"rid": r.resource_id, "grant": r.grant_id, "lic": r.license_id,
                   "how": r.how_used, "run": r.longest_copied_run, "cited": r.cited} for r in final_results],
    })
    await session.commit()

    return {
        "receipt_id": receipt.id,
        "passed": passed,
        "fixed_by": fixed_by,
        "answer": final_answer,
        "violations_found": original_violations,
        "violations_remaining": final_violations,
        "items": item_dicts,
        "signature": receipt.signature,
    }
