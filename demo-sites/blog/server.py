"""A plain publisher website. It knows NOTHING about payments; the gateway protects it."""

from pathlib import Path

from fastapi import FastAPI, HTTPException

ARTICLES = (Path(__file__).parent / "articles").resolve()

app = FastAPI(title="Demo publisher blog (origin server)")


def parse_article(path: Path) -> tuple[dict[str, str], str]:
    """Split a markdown file into (frontmatter, body)."""
    _, header, body = path.read_text(encoding="utf-8").split("---", 2)
    meta = {}
    for line in header.strip().splitlines():
        key, value = line.split(":", 1)
        meta[key.strip()] = value.strip()
    return meta, body.strip()


@app.get("/blog/{slug}")
def article(slug: str):
    path = (ARTICLES / f"{slug}.md").resolve()
    # Block path traversal: the real file must still be inside ARTICLES.
    if path.parent != ARTICLES or not path.is_file():
        raise HTTPException(404, detail="Article not found")
    meta, body = parse_article(path)
    return {"title": meta["title"], "publisher": meta["publisher"], "body": body}