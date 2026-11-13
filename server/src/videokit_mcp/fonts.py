"""Make pages render offline: download Google Fonts stylesheets and font files once into ~/.videokit/cache/fonts,
copy them beside the page and point the page at the copies. Headless Chrome often has no internet (or no proxy)
while rendering, and a font that loads late changes frames, so local fonts are also more reproducible."""

from __future__ import annotations

import hashlib
import re
import shutil
import urllib.request
from pathlib import Path

from . import config

_LINK = re.compile(r'https://fonts\.googleapis\.com/css2?\?[^"\'\s>]+')
_URL = re.compile(r"url\((https://fonts\.gstatic\.com/[^)]+)\)")
# Ask for woff2, which Chrome reads; Google varies the format by user agent.
_UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"


def _get(url: str) -> bytes:
    cache = config.CACHE_DIR / "fonts" / hashlib.sha256(url.encode()).hexdigest()[:24]
    if cache.exists():
        return cache.read_bytes()
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_bytes(data)
    return data


def localize(html: Path, fonts_dir_name: str = "fonts") -> list[str]:
    """Rewrite every Google Fonts <link> in `html` to a local stylesheet. Returns the families localized."""
    text = html.read_text(encoding="utf-8")
    links = sorted(set(m.group(0).replace("&amp;", "&") for m in _LINK.finditer(text)))
    if not links:
        return []
    out = html.parent / fonts_dir_name
    out.mkdir(exist_ok=True)
    done = []
    for link in links:
        css = _get(link).decode("utf-8")
        for u in sorted(set(_URL.findall(css))):
            name = hashlib.sha256(u.encode()).hexdigest()[:16] + Path(u.split("?")[0]).suffix
            (out / name).write_bytes(_get(u))
            css = css.replace(u, name)
        css_name = "gf-" + hashlib.sha256(link.encode()).hexdigest()[:12] + ".css"
        (out / css_name).write_text(css, encoding="utf-8")
        for variant in (link, link.replace("&", "&amp;")):
            text = text.replace(variant, f"{fonts_dir_name}/{css_name}")
        done += re.findall(r"family=([^&:]+)", link)
    # Preconnect hints to Google are now pointless and can stall a page with no network.
    text = re.sub(r'<link[^>]+rel="preconnect"[^>]+fonts\.(googleapis|gstatic)\.com[^>]*>\s*', "", text)
    html.write_text(text, encoding="utf-8")
    return [d.replace("+", " ") for d in done]


def copy_tree(src: Path, dst: Path, skip: tuple[str, ...]) -> None:
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns(*skip), dirs_exist_ok=True)
