#!/usr/bin/env python3
"""Generate Platão's marble-bust hero art via OpenRouter — you run it, with your own key.

The key is read from the environment and never stored or printed. Zero dependencies (stdlib only).

    export OPENROUTER_API_KEY=sk-or-...        # your key — the script only reads it from the env
    python scripts/generate_art.py             # -> assets/platao-bust.png

It passes the Athena coin (assets/athena-coin.jpg) as a style reference so the palette matches:
white Carrara marble, warm gold accents, deep navy background. Model: gemini-2.5-flash-image
("nano-banana"; the old `-preview` id is gone from OpenRouter), ~US$0.04 per image — a few tries
stay well under a dollar.

Then drop it into the README:  ![Platão](assets/platao-bust.png)
"""

from __future__ import annotations

import base64
import json
import os
import sys
import urllib.request
from pathlib import Path

MODEL = "google/gemini-2.5-flash-image"
ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
ASSETS = Path(__file__).resolve().parent.parent / "assets"

PROMPT = (
    "A museum-quality portrait bust of the ancient Greek philosopher Plato, carved from white "
    "Carrara marble with fine natural veining. Three-quarter view, calm and contemplative "
    "expression, full beard, classical wavy hair. Subtle warm gold-leaf accents on the base. "
    "Centered on a deep navy background with soft, even studio lighting. Photorealistic, sharp "
    "detail, dignified, restrained — no text, no watermark. Match the marble-and-gold aesthetic of "
    "the attached reference medallion."
)


def _extract_image(data: dict) -> bytes | None:
    """Pull the first inline image out of an OpenRouter chat-completions response."""
    try:
        message = data["choices"][0]["message"]
    except (KeyError, IndexError, TypeError):
        return None
    for image in message.get("images") or []:
        url = image.get("image_url", {}).get("url", "")
        if url.startswith("data:") and "," in url:
            return base64.b64decode(url.split(",", 1)[1])
    return None


def main() -> int:
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        print("Set OPENROUTER_API_KEY in your environment first.", file=sys.stderr)
        return 2

    content: list[dict] = [{"type": "text", "text": PROMPT}]
    coin = ASSETS / "athena-coin.jpg"
    if coin.exists():
        encoded = base64.b64encode(coin.read_bytes()).decode()
        content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded}"}})

    body = json.dumps({
        "model": MODEL,
        "modalities": ["image", "text"],
        "messages": [{"role": "user", "content": content}],
    }).encode()

    request = urllib.request.Request(  # noqa: S310 — fixed https endpoint
        ENDPOINT,
        data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=180) as response:  # noqa: S310
        data = json.load(response)

    image = _extract_image(data)
    if image is None:
        print("No image in the response. First 800 chars:", file=sys.stderr)
        print(json.dumps(data, indent=2)[:800], file=sys.stderr)
        return 1

    out = ASSETS / "platao-bust.png"
    out.write_bytes(image)
    print(f"saved {out}  ({len(image) // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
