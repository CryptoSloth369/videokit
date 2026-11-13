"""Image generation with Gemini, for styles that draw characters, props or panels with an image model (the
lemo-opuscar styles marked "needs image-generation", reference sheets, posters).

The key: GEMINI_API_KEY (or GOOGLE_API_KEY) in the environment. In a Claude cloud session whose network injects the
key for generativelanguage.googleapis.com, no variable is needed."""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

MODELS = {"fast": "gemini-3.1-flash-image", "pro": "gemini-3-pro-image"}
ASPECTS = ("1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9")
API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class ImageError(ValueError):
    pass


def generate(prompt: str, out_dir: Path, name: str, aspect: str, refs: list[Path], quality: str) -> Path:
    if aspect not in ASPECTS:
        raise ImageError(f"aspect must be one of {ASPECTS}")
    if quality not in MODELS:
        raise ImageError(f"quality must be one of {list(MODELS)}")
    if not re.match(r"^[A-Za-z0-9_-]{1,60}$", name):
        raise ImageError("name: letters, digits, - and _ only")
    parts: list[dict] = []
    for r in refs:
        if not r.exists():
            raise ImageError(f"reference not found: {r}")
        mime = mimetypes.guess_type(r.name)[0] or "image/png"
        parts.append({"inline_data": {"mime_type": mime, "data": base64.b64encode(r.read_bytes()).decode()}})
    parts.append({"text": prompt})
    body = {"contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": aspect}}}
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "proxy-injected"
    req = urllib.request.Request(API.format(model=MODELS[quality]), data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "x-goog-api-key": key})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            data = json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise ImageError(f"Gemini returned {e.code}: {e.read().decode(errors='replace')[:400]}") from None
    for cand in data.get("candidates", []):
        for p in cand.get("content", {}).get("parts", []):
            blob = p.get("inline_data") or p.get("inlineData")
            if blob and blob.get("data"):
                ext = mimetypes.guess_extension(blob.get("mime_type") or blob.get("mimeType") or "image/png") or ".png"
                out_dir.mkdir(parents=True, exist_ok=True)
                out = out_dir / f"{name}_{time.strftime('%Y%m%d-%H%M%S')}{ext}"
                out.write_bytes(base64.b64decode(blob["data"]))
                return out
    reason = (data.get("promptFeedback") or {}).get("blockReason") or \
        next((c.get("finishReason") for c in data.get("candidates", [])), None)
    raise ImageError(f"no image returned (reason: {reason or 'unknown'})")
