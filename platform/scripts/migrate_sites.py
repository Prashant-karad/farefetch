"""Move an existing database to the three publisher websites, in place. Safe to run many times.

- adds the publishers that live on their own websites (sites/content.py + sites/urls.json) and their pages
- retires the old bundled demo articles: their path moves under /retired/ so agents no longer find them,
  but purchases, passes, receipts and ledger entries that reference them stay intact (nothing is deleted)

Run from platform/:  python -m scripts.migrate_sites
"""

import asyncio

from sqlalchemy import select

from app.db import SessionLocal, engine
from app.models import Account, Publisher, Resource
from app.redis_client import redis_client
from scripts.seed import PUBLISHERS, SITE_URLS, SITES


async def main() -> None:
    added = retired = 0
    async with SessionLocal() as session:
        for slug, pub in PUBLISHERS.items():
            row = await session.get(Publisher, pub["id"])
            if row is None:
                session.add(Publisher(**pub))
                session.add(Account(type="publisher_payable", owner_id=pub["id"]))
                await session.flush()
            else:
                row.name, row.website_url = pub["name"], pub["website_url"]
            for art_slug, title, price, license_id, text in SITES[slug]["articles"]:
                rid = f"res_{art_slug.replace('-', '_')}"
                old = await session.get(Resource, rid)
                if old is not None and old.origin_url is None:  # same id as an old bundled article: use its own id
                    rid = f"res_{slug}_{art_slug.replace('-', '_')}"
                    old = await session.get(Resource, rid)
                if old is None:
                    words = text.split()
                    session.add(Resource(id=rid, publisher_id=pub["id"], path=f"/p/{slug}/{art_slug}",
                                         origin_url=f"{SITE_URLS[slug]}/{art_slug}/", kind="article", title=title,
                                         price=price, license_id=license_id,
                                         preview=" ".join(words[:30]) + " ...", word_count=len(words)))
                    added += 1
        for res in (await session.scalars(select(Resource).where(Resource.path.like("/blog/%")))).all():
            await redis_client.delete(f"gw:resource:{res.path}")
            res.path = "/retired" + res.path
            retired += 1
        await session.commit()
    await engine.dispose()
    print(f"Publisher websites: {added} pages added, {retired} old demo pages retired")


if __name__ == "__main__":
    asyncio.run(main())
