"""Add the paid-API demo resource and set publisher PayPal sandbox emails. Safe to run many times.

Run from platform/:  python -m scripts.setup_demo
Reads PUBLISHER_A_PAYPAL_EMAIL and PUBLISHER_B_PAYPAL_EMAIL from the environment / .env.
"""

import asyncio
import os
from pathlib import Path

from sqlalchemy import select

from app.db import SessionLocal, engine
from app.models import Agent, BudgetPolicy, License, Publisher, Resource


def env(name: str) -> str | None:
    if os.environ.get(name):
        return os.environ[name]
    for f in (Path("../.env"), Path(".env")):
        if f.exists():
            for line in f.read_text().splitlines():
                if line.startswith(name + "="):
                    return line.split("=", 1)[1].strip() or None
    return None


async def main() -> None:
    async with SessionLocal() as session:
        if await session.get(License, "lic_data_1h") is None:
            session.add(License(id="lic_data_1h", type="quote", max_quote_words=50,
                                attribution_required=True, ttl_hours=1))
            await session.flush()
            print("Added license lic_data_1h (data may be quoted, 1-hour pass)")

        if await session.scalar(select(Resource).where(Resource.path == "/api/job-trends")) is None:
            session.add(Resource(
                id="res_api_job_trends", publisher_id="pub_code_dojo", path="/api/job-trends",
                kind="api", title="Live developer job trends: demand for Python, JavaScript and SQL", price=50,
                license_id="lic_data_1h",
                preview="This week's job postings and median salaries for Python, JavaScript and SQL developers ...",
                word_count=60,
            ))
            print("Added paid API resource /api/job-trends ($0.0050 per pass)")

        for pub_id, var in (("pub_code_dojo", "PUBLISHER_A_PAYPAL_EMAIL"),
                            ("pub_moneywise", "PUBLISHER_B_PAYPAL_EMAIL")):
            email = env(var)
            if email:
                pub = await session.get(Publisher, pub_id)
                if pub is None:
                    print(f"{pub_id} not found; skipped")
                    continue
                pub.paypal_email = email
                print(f"{pub_id} -> {email}")
            else:
                print(f"{var} not set; {pub_id} keeps its placeholder email")

        daily = env("DEMO_DAILY_BUDGET_USD")
        if daily:
            agent = await session.scalar(select(Agent).limit(1))
            policy = await session.get(BudgetPolicy, agent.id) if agent else None
            if policy is not None:
                policy.max_per_day = int(float(daily) * 10_000)
                print(f"Daily budget set to ${daily}")

        await session.commit()
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
