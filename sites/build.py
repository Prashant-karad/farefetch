"""Build the three publisher websites into sites/<slug>/dist (plain static HTML).

    python sites/build.py

Absolute sitemap URLs come from sites/urls.json ({"codedojo": "https://...", ...}) when present;
otherwise the sitemap uses site-relative paths (fine for local development).
"""

import html
import json
from pathlib import Path

from content import SITES

ROOT = Path(__file__).resolve().parent
URLS = json.loads((ROOT / "urls.json").read_text()) if (ROOT / "urls.json").exists() else {}


def page(site: dict, title: str, body: str) -> str:
    font = site["font"].replace(" ", "+")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family={font}:wght@600;700&family=Inter:wght@400;500;600&display=swap">
<style>
:root {{ --c: {site['color']}; --ink: {site['ink']}; --paper: {site['paper']}; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: var(--paper); color: var(--ink); font: 17px/1.7 Inter, system-ui, sans-serif; }}
header {{ border-bottom: 1px solid color-mix(in srgb, var(--ink) 12%, transparent); }}
.in {{ max-width: 760px; margin: 0 auto; padding: 0 max(18px, env(safe-area-inset-left, 0px)); }}
header .in {{ display: flex; justify-content: space-between; align-items: center; padding-block: 18px; gap: 12px; flex-wrap: wrap; }}
.logo {{ font: 700 24px '{site['font']}', Georgia, serif; color: var(--ink); text-decoration: none; }}
.logo span {{ color: var(--c); }}
nav a {{ color: var(--ink); opacity: .7; text-decoration: none; font-size: 15px; }}
h1 {{ font: 700 clamp(30px, 5vw, 44px)/1.15 '{site['font']}', Georgia, serif; margin: 40px 0 10px; text-wrap: balance; }}
.tag {{ color: var(--c); font-weight: 600; font-size: 14px; letter-spacing: .04em; text-transform: uppercase; }}
article p {{ margin: 0 0 1.1em; }}
.list {{ list-style: none; padding: 0; margin: 28px 0; display: grid; gap: 14px; }}
.list a {{ display: block; padding: 18px 20px; background: #fff; border: 1px solid color-mix(in srgb, var(--ink) 10%, transparent);
  border-radius: 12px; text-decoration: none; color: var(--ink); font: 600 19px/1.35 '{site['font']}', Georgia, serif; }}
.list a:hover {{ border-color: var(--c); }}
.list small {{ display: block; font: 400 14px Inter, sans-serif; opacity: .65; margin-top: 4px; }}
footer {{ margin: 60px 0 30px; font-size: 14px; opacity: .6; }}
</style></head>
<body><header><div class="in"><a class="logo" href="/">{html.escape(site['name'][:-4] if site['name'].endswith('Dojo') else site['name'])}<span>{'Dojo' if site['name'].endswith('Dojo') else '.'}</span></a>
<nav><a href="/">All guides</a></nav></div></header>
<main class="in">{body}</main>
<footer class="in">© {html.escape(site['name'])} · {html.escape(site['tagline'])}</footer></body></html>
"""


def build(slug: str, site: dict) -> None:
    dist = ROOT / slug / "dist"
    dist.mkdir(parents=True, exist_ok=True)
    base = URLS.get(slug, "").rstrip("/")
    items = []
    for art_slug, title, *_rest, text in site["articles"]:
        paras = "".join(f"<p>{html.escape(p.strip())}</p>" for p in text.strip().split("\n\n"))
        first = text.strip().split(".")[0] + "."
        (dist / art_slug).mkdir(exist_ok=True)
        (dist / art_slug / "index.html").write_text(page(site, f"{title} · {site['name']}",
            f'<span class="tag">Guide</span><h1>{html.escape(title)}</h1><article>{paras}</article>'))
        items.append(f'<li><a href="/{art_slug}/">{html.escape(title)}<small>{html.escape(first[:140])}</small></a></li>')
    (dist / "index.html").write_text(page(site, f"{site['name']}: {site['tagline']}",
        f'<h1>{html.escape(site["tagline"])}</h1><ul class="list">{"".join(items)}</ul>'))
    locs = "".join(f"<url><loc>{base}/{a[0]}/</loc></url>" for a in site["articles"])
    (dist / "sitemap.xml").write_text(f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{locs}</urlset>\n')
    (dist / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {base}/sitemap.xml\n")
    print(f"built {slug}: {len(site['articles'])} articles -> {dist}")


if __name__ == "__main__":
    for slug, site in SITES.items():
        build(slug, site)
