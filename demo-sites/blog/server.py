"""A plain publisher website + data API. It knows NOTHING about payments; the gateway protects it."""

from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, Response

ARTICLES = (Path(__file__).parent / "articles").resolve()

app = FastAPI(title="Demo publisher (origin server)")


def parse_article(path: Path) -> tuple[dict[str, str], str]:
    """Split a markdown file into (frontmatter, body)."""
    _, header, body = path.read_text(encoding="utf-8").split("---", 2)
    meta = {}
    for line in header.strip().splitlines():
        key, value = line.split(":", 1)
        meta[key.strip()] = value.strip()
    return meta, body.strip()


def all_articles() -> list[tuple[str, dict[str, str]]]:
    return [(f.stem, parse_article(f)[0]) for f in sorted(ARTICLES.glob("*.md"))]


@app.get("/", response_class=HTMLResponse)
def home():
    """The publishers' ordinary website for human readers."""
    items = "".join(f'<li><a href="/blog/{slug}">{m["title"]}</a> <small>{m["publisher"]}</small></li>'
                    for slug, m in all_articles())
    return f"<!doctype html><title>Code Dojo &amp; Learn Daily</title><h1>Code Dojo &amp; Learn Daily</h1><ul>{items}</ul>"


@app.get("/sitemap.xml")
def sitemap():
    """Standard sitemap: how the Fairfetch setup scan (and search engines) find every page."""
    urls = [f"/blog/{slug}" for slug, _ in all_articles()] + ["/api/job-trends"]
    body = "".join(f"<url><loc>{u}</loc></url>" for u in urls)
    return Response(f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{body}</urlset>',
                    media_type="application/xml")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/blog/{slug}")
def article(slug: str):
    path = (ARTICLES / f"{slug}.md").resolve()
    # Block path traversal: the real file must still be inside ARTICLES.
    if path.parent != ARTICLES or not path.is_file():
        raise HTTPException(404, detail="Article not found")
    meta, body = parse_article(path)
    return {"title": meta["title"], "publisher": meta["publisher"], "body": body}


@app.get("/api/job-trends")
def job_trends():
    """A paid DATA API (illustrative demo numbers, not real market data)."""
    return {
        "week_of": date.today().isoformat(),
        "note": "Illustrative demo data",
        "languages": [
            {"language": "Python", "open_roles": 48210, "median_salary_usd": 128000, "change_vs_last_month": "+3.1%"},
            {"language": "JavaScript", "open_roles": 52940, "median_salary_usd": 118000, "change_vs_last_month": "+0.8%"},
            {"language": "SQL", "open_roles": 39870, "median_salary_usd": 112000, "change_vs_last_month": "+1.6%"},
        ],
    }
