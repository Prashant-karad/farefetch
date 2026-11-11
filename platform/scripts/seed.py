"""Seed demo data. Safe to run twice (it checks first).

Run from platform/:  python -m scripts.seed
"""

import asyncio
from pathlib import Path

from sqlalchemy import select

from app.db import SessionLocal, engine
from app.models import Account, Agent, AgentOwner, BudgetPolicy, License, Publisher, Resource
from app.services.security import generate_api_key

ARTICLES_DIR = Path(__file__).resolve().parents[2] / "demo-sites" / "blog" / "articles"

LICENSES = [
    {"id": "lic_read_24h", "type": "read", "max_quote_words": 8, "attribution_required": True, "ttl_hours": 24},
    {"id": "lic_quote_24h", "type": "quote", "max_quote_words": 50, "attribution_required": True, "ttl_hours": 24},
]

# PayPal emails are placeholders; we replace them with sandbox accounts in M4.
PUBLISHERS = {
    "code-dojo": {"id": "pub_code_dojo", "name": "Code Dojo", "paypal_email": "publisher-a@example.com"},
    "learn-daily": {"id": "pub_learn_daily", "name": "Learn Daily", "paypal_email": "publisher-b@example.com"},
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
        for path in sorted(ARTICLES_DIR.glob("*.md")):
            meta, body = parse_article(path)
            words = body.split()
            session.add(Resource(
                id=f"res_{path.stem.replace('-', '_')}",
                publisher_id=PUBLISHERS[meta["publisher"]]["id"],
                path=f"/blog/{path.stem}",
                kind="article",
                title=meta["title"],
                price=int(meta["price"]),
                license_id=meta["license"],
                preview=" ".join(words[:30]) + " ...",
                word_count=len(words),
            ))
            count += 1

        owner = AgentOwner(name="Maya's Study Assistant", email="owner@example.com")
        session.add(owner)
        await session.flush()  # assigns owner.id

        session.add(Account(type="agent_wallet", owner_id=owner.id))

        full_key, prefix, key_hash = generate_api_key()
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
