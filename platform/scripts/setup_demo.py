"""Add the paid-API demo resource and set publisher PayPal sandbox emails. Safe to run many times.

Run from platform/:  python -m scripts.setup_demo
Reads PUBLISHER_A_PAYPAL_EMAIL and PUBLISHER_B_PAYPAL_EMAIL from the environment / .env.
"""

import asyncio
import os
from pathlib import Path

from sqlalchemy import select

from app.db import SessionLocal, engine
from app.models import License, Publisher, Resource


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

        if await session.scalar(select(Resource).where(Resource.path == "/api/mandi-prices")) is None:
            session.add(Resource(
                id="res_api_mandi_prices", publisher_id="pub_krishi_today", path="/api/mandi-prices",
                kind="api", title="Live mandi prices: onion, soybean, cotton (Maharashtra)", price=50,
                license_id="lic_data_1h",
                preview="Today's modal prices (Rs/quintal) at Lasalgaon, Latur and Akola APMCs ...",
                word_count=60,
            ))
            print("Added paid API resource /api/mandi-prices ($0.0050 per pass)")

        for pub_id, var in (("pub_krishi_today", "PUBLISHER_A_PAYPAL_EMAIL"),
                            ("pub_monsoon_notes", "PUBLISHER_B_PAYPAL_EMAIL")):
            email = env(var)
            if email:
                (await session.get(Publisher, pub_id)).paypal_email = email
                print(f"{pub_id} -> {email}")
            else:
                print(f"{var} not set; {pub_id} keeps its placeholder email")

        await session.commit()
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
