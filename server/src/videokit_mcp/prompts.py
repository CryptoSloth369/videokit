"""Search prompts that made good code-made videos, as inspiration. Personal mode only: the prompts are other
people's posts (one library has no license at all), so they are never offered inside a service.

Sources:
  awesome   yihui-dev/awesome-opus5-5-videos (submodule vendor/awesome-opus5-5-videos): 703 prompts, English
  opus-cn   joeseesun/opus-video-prompts (no license: downloaded on first use to ~/.videokit/cache, never committed):
            18 full prompts with notes (Chinese) and 54 case links
"""

from __future__ import annotations

import json
import re
import subprocess
from functools import cache
from pathlib import Path

from . import config

OPUS_CN_URL = "https://github.com/joeseesun/opus-video-prompts.git"
USE_NOTE = ("Use as inspiration, not as a template to copy. The prompt belongs to its author (credit them if you "
            "share it). Leave out third-party characters, brands and franchises in videos you publish or monetize.")


def _opus_cn_dir(fetch: bool) -> Path | None:
    d = config.CACHE_DIR / "opus-video-prompts"
    if (d / "cases.json").exists():
        return d
    if not fetch:
        return None
    d.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["git", "clone", "-q", "--depth", "1", OPUS_CN_URL, str(d)], capture_output=True, text=True,
                       timeout=180)
    return d if r.returncode == 0 and (d / "cases.json").exists() else None


@cache
def _index() -> tuple[list[dict], list[str]]:
    items: list[dict] = []
    problems: list[str] = []
    aw = config.VENDOR_DIR / "awesome-opus5-5-videos" / "data" / "videos.json"
    if aw.exists():
        for v in json.loads(aw.read_text(encoding="utf-8")):
            items.append({"id": f"awesome:{v['slug']}", "source": "awesome", "title": v["prompt"][:90],
                          "category": v.get("category"), "tech": v.get("tech_tags", []),
                          "author": v.get("author"), "post_url": v.get("post_url"),
                          "remake_url": v.get("skillry_url"), "partial": bool(v.get("prompt_partial")),
                          "_text": v["prompt"]})
    else:
        problems.append("awesome library missing: run `git submodule update --init` in the videokit repo")
    cn = _opus_cn_dir(fetch=True)
    if cn:
        for f in sorted((cn / "prompts").glob("*.md")):
            text = f.read_text(encoding="utf-8")
            title = re.search(r"^# (.+)$", text, re.M)
            author = re.search(r"\*\*作者\*\*[：:]\s*(.+)$", text, re.M)
            url = re.search(r"(https?://\S+)", text)
            body = re.search(r"```(?:text)?\n(.*?)```", text, re.S)
            items.append({"id": f"opus-cn:{f.stem}", "source": "opus-cn", "title": title.group(1) if title else f.stem,
                          "category": "full prompt with notes (Chinese)", "tech": [],
                          "author": author.group(1).strip() if author else None,
                          "post_url": url.group(1) if url else None, "partial": False,
                          "_text": body.group(1).strip() if body else text, "_doc": text})
        for i, c in enumerate(json.loads((cn / "cases.json").read_text(encoding="utf-8"))):
            items.append({"id": f"opus-cn-case:{i}", "source": "opus-cn", "title": c.get("title"),
                          "category": c.get("category"), "tech": [], "author": c.get("author"),
                          "post_url": c.get("url"), "partial": True,
                          "_text": f"{c.get('title')}\nHow: {c.get('how')}\nCost: {c.get('cost')}\n(See the post for the work.)"})
    else:
        problems.append("opus-video-prompts could not be downloaded (offline?): only the awesome library is searched")
    return items, problems


def public(item: dict) -> dict:
    return {k: v for k, v in item.items() if not k.startswith("_")}


def search(query: str, category: str, tech: str, source: str, limit: int) -> dict:
    items, problems = _index()
    words = [w.lower() for w in query.split()]
    hits = []
    for it in items:
        if source and it["source"] != source:
            continue
        if category and category.lower() not in (it.get("category") or "").lower():
            continue
        if tech and tech.lower() not in [t.lower() for t in it["tech"]]:
            continue
        hay = (it["_text"] + " " + (it.get("title") or "") + " " + (it.get("category") or "")).lower()
        score = sum(hay.count(w) for w in words) if words else 1
        if score:
            hits.append((score, it))
    hits.sort(key=lambda x: -x[0])
    return {"count": len(hits), "results": [public(it) for _, it in hits[:limit]], "problems": problems,
            "categories": sorted({i.get("category") for i in items if i.get("category")}),
            "use_note": USE_NOTE}


def get(prompt_id: str) -> dict:
    items, _ = _index()
    it = next((i for i in items if i["id"] == prompt_id), None)
    if it is None:
        raise KeyError(f"no prompt {prompt_id!r}; find ids with search_prompts")
    return {**public(it), "prompt": it["_text"], "notes": it.get("_doc"), "use_note": USE_NOTE}
