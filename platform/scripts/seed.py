"""Seed demo data. Safe to run twice (it checks first).

Run from platform/:  python -m scripts.seed
"""

import asyncio
import os
from pathlib import Path

from sqlalchemy import select

from app.db import SessionLocal, engine
from app.models import Account, Agent, AgentOwner, BudgetPolicy, License, Publisher, Resource
from app.services.security import generate_api_key, hash_api_key

import json
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "sites"))
from content import SITES  # noqa: E402  (the publishers' websites: sites/content.py)

SITE_URLS = json.loads((ROOT / "sites" / "urls.json").read_text())

LICENSES = [
    {"id": "lic_read_24h", "type": "read", "max_quote_words": 8, "attribution_required": True, "ttl_hours": 24},
    {"id": "lic_quote_24h", "type": "quote", "max_quote_words": 50, "attribution_required": True, "ttl_hours": 24},
]

# Publishers already on Fairfetch at start. StudyNest is not here: it connects live through the setup flow.
# PayPal emails are placeholders; scripts/setup_demo.py sets the sandbox accounts.
PUBLISHERS = {
    slug: {"id": site["publisher_id"], "name": site["name"], "paypal_email": f"{slug}@example.com",
           "website_url": SITE_URLS[slug]}
    for slug, site in SITES.items() if site["publisher_id"]
}


def parse_article(path: Path) -> tuple[dict[str, str], str]:
    """Split a markdown file into (frontmatter dict, body text)."""
    _, header, body = path.read_text(encoding="utf-8").split("---", 2)
    meta = {}
    for line in header.strip().splitlines():
        key, value = line.split(":", 1)
        meta[key.strip()] = value.strip()
    return meta, body.strip()


async def main() -> None:
    async with SessionLocal() as session:
        if await session.scalar(select(Publisher.id).limit(1)):
            print("Already seeded. Nothing to do.")
            return

        for lic in LICENSES:
            session.add(License(**lic))

        for pub in PUBLISHERS.values():
            session.add(Publisher(**pub))
            session.add(Account(type="publisher_payable", owner_id=pub["id"]))

        # System accounts with fixed, well-known IDs.
        session.add(Account(id="acc_platform_revenue", type="platform_revenue"))
        session.add(Account(id="acc_paypal_clearing", type="paypal_clearing"))
        await session.flush()  # send INSERTs now so the rows exist for the foreign keys below

        count = 0
        for slug, pub in PUBLISHERS.items():
            for art_slug, title, price, license_id, text in SITES[slug]["articles"]:
                words = text.split()
                session.add(Resource(
                    id=f"res_{art_slug.replace('-', '_')}",
                    publisher_id=pub["id"],
                    path=f"/p/{slug}/{art_slug}",                       # gateway address
                    origin_url=f"{SITE_URLS[slug]}/{art_slug}/",        # the publisher's own page
                    kind="article", title=title, price=price, license_id=license_id,
                    preview=" ".join(words[:30]) + " ...", word_count=len(words),
                ))
                count += 1

        owner = AgentOwner(name="Maya's Study Assistant", email="owner@example.com")
        session.add(owner)
        await session.flush()  # assigns owner.id

        session.add(Account(type="agent_wallet", owner_id=owner.id))

        # Hosting sets DEMO_AGENT_API_KEY up front so the live demo agent knows its key; locally we generate one.
        fixed = os.environ.get("DEMO_AGENT_API_KEY", "").strip()
        full_key, prefix, key_hash = (fixed, fixed[:12], hash_api_key(fixed)) if fixed else generate_api_key()
        agent = Agent(owner_id=owner.id, name="study-agent", api_key_prefix=prefix, api_key_hash=key_hash)
        session.add(agent)
        await session.flush()

        # $0.05 max per item, $1.00 max per day
        session.add(BudgetPolicy(agent_id=agent.id, max_per_item=500, max_per_day=10_000))

        await session.commit()  # everything above is saved together, or not at all

    await engine.dispose()
    print(f"Seeded {len(PUBLISHERS)} publishers, {count} articles, 1 owner, 1 agent.")
    print(f"Agent ID: {agent.id}")
    print(f"Agent API key (shown ONCE, copy it now): {full_key}")


if __name__ == "__main__":
    asyncio.run(main())
