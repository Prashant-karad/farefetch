"""Readable text from a publisher's page: our JSON origin, or any HTML web page.

The license guard compares answers against this text, and the agent reads the same text,
so both sides use the same extraction rule (the <article> element when present, else the body).
"""

import html
import json
import re

_SKIP = re.compile(r"<(script|style|nav|header|footer|noscript|svg)[^>]*>.*?</\1>", re.S | re.I)
_TAG = re.compile(r"<[^>]+>")
_ARTICLE = re.compile(r"<article[^>]*>(.*?)</article>", re.S | re.I)
_TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.S | re.I)


def extract(raw: str, content_type: str = "") -> tuple[str | None, str]:
    """Returns (title, text)."""
    if "json" in content_type or raw.lstrip().startswith("{"):
        try:
            data = json.loads(raw)
            if isinstance(data, dict) and "body" in data:
                return data.get("title"), str(data["body"])
            return None, json.dumps(data)
        except ValueError:
            pass
    t = _TITLE.search(raw)
    title = html.unescape(t.group(1)).strip() if t else None
    m = _ARTICLE.search(raw)
    part = m.group(1) if m else _SKIP.sub(" ", raw)
    part = re.sub(r"</(p|h[1-6]|li|div)>", "\n\n", part, flags=re.I)
    text = html.unescape(_TAG.sub(" ", part))
    paras = [re.sub(r"[ \t\r\f\v]+", " ", p).strip() for p in text.split("\n\n")]
    return title, "\n\n".join(p for p in paras if p)
