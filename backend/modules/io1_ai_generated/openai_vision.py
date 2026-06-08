"""
OpenAI (vision) backend for module io1.

When an OpenAI key is available, we delegate the "genuine photo vs generated /
faked image" verdict to a vision model (GPT-4o by default) rather than the small
local ResNet50 — much more reliable, especially on AI-generated images.

Key read, in order of priority:
    1. environment variable OPENAI_API_KEY
    2. file backend/data/openai_key.txt  (one line — handy locally)

Optional env vars:
    IO1_OPENAI_MODEL    vision model to use                 (default: gpt-4o)
    IO1_OPENAI_TIMEOUT  HTTP request timeout in seconds      (default: 60)
"""
from __future__ import annotations

import base64
import io
import json
import os
import re

_KEY_FILE = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "data", "openai_key.txt")
)
_MODEL = os.environ.get("IO1_OPENAI_MODEL", "gpt-4o").strip() or "gpt-4o"
_TIMEOUT = float(os.environ.get("IO1_OPENAI_TIMEOUT", "60"))
_API_URL = "https://api.openai.com/v1/chat/completions"


def api_key() -> str | None:
    k = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if k:
        return k
    try:
        with open(_KEY_FILE, "r", encoding="utf-8") as f:
            k = f.read().strip().strip('"').strip("'")
        return k or None
    except OSError:
        return None


def available() -> bool:
    return bool(api_key())


def model_name() -> str:
    return _MODEL


_SYSTEM = (
    "You are a senior image-forensics analyst working for a fact-checking newsroom. "
    "You receive ONE image and must decide whether it is a REAL photograph genuinely captured by a "
    "camera, or whether it is synthetically generated or manipulated — i.e. an AI text-to-image picture "
    "(Midjourney, DALL-E, Stable Diffusion, Flux, Firefly…), a GAN-generated face, a deepfake face-swap, or a "
    "heavily digitally edited photo.\n"
    "Inspect carefully for: anatomical errors (hands, fingers, teeth, ears, eyes), impossible physics or "
    "perspective, melted or garbled text and logos, unnaturally smooth skin / plasticky bokeh, repeated or "
    "tiled textures, inconsistent lighting and shadows, warped or nonsensical backgrounds, mismatched "
    "earrings/glasses, and other generative artifacts.\n"
    "IMPORTANT — modern generators (DALL-E 3, Midjourney v6, Flux, SDXL) routinely produce images with NO "
    "classic artifact: correct hands, coherent text, plausible physics. For those, the real tell is the "
    "ABSENCE of real-world contingency — no candid imperfections, no readable genuine brand/place/licence-plate, "
    "an over-clean 'stock-photo / concept-art / 3D-render' aesthetic, lighting and composition that are "
    "slightly-too-perfect, surfaces that look 'rendered' rather than photographed. If your overall judgement "
    "is that nobody actually took this picture with a camera (it is a generated/composed image), answer "
    "FAKE / ai_generated even without one single broken detail.\n"
    "Be well-calibrated the other way too: ordinary real photos — selfies, tourist snapshots, phone photos, "
    "slightly blurry, low-light, JPEG-compressed or screenshot images — MUST be judged REAL with high "
    "confidence; do not flag a real picture as fake merely because the photography is good.\n"
    "CONSISTENCY RULE: the verdict and category MUST agree — if category is anything other than "
    "\"authentic_photo\" (i.e. ai_generated / deepfake_face / edited_photo), then verdict MUST be \"FAKE\". "
    "Never return verdict \"REAL\" with a non-authentic category.\n"
    "Answer with ONLY a JSON object (no markdown, no prose around it) with EXACTLY these keys:\n"
    '  "verdict": "REAL" or "FAKE"\n'
    '  "category": one of "authentic_photo", "ai_generated", "deepfake_face", "edited_photo"\n'
    '  "confidence": integer 50-99 — how certain you are of the verdict\n'
    '  "has_face": true or false — is there at least one clearly visible human face\n'
    '  "reason": 1 to 3 short sentences in ENGLISH, plain language for a general audience, explaining the verdict\n'
    '  "clues": array of short ENGLISH strings naming the concrete visual clues you used (empty array if none)'
)


def analyze(pil_image, hint_face: bool | None = None, hint_ai: bool = False) -> dict | None:
    """Returns a normalized dict, or None if no key/dependency. Raises RuntimeError on API error.

    hint_ai: the user explicitly submitted this to the "AI-generated image" check → scrutinise harder.
    """
    key = api_key()
    if not key:
        return None
    try:
        import requests  # noqa
    except ImportError:
        return None

    img = pil_image.convert("RGB")
    img.thumbnail((1024, 1024))  # lighter / cheaper payload, sufficient for the diagnosis
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")

    user_text = "Analyze this image and return only the requested JSON."
    if hint_face is True:
        user_text += " A human face appears to be present in the image."
    if hint_ai:
        user_text += (" The submitter specifically believes this image is AI-generated, so apply maximum "
                      "scrutiny: AI generators are now near-perfect, so the absence of clear artifacts is NOT "
                      "evidence of authenticity. Unless you can point to concrete evidence that a real camera "
                      "captured this scene (genuine readable details, candid imperfections, sensor noise, "
                      "natural depth-of-field), lean toward FAKE / ai_generated.")

    payload = {
        "model": _MODEL,
        "temperature": 0,
        "max_tokens": 600,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": [
                {"type": "text", "text": user_text},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}", "detail": "high"}},
            ]},
        ],
    }
    try:
        import requests
        r = requests.post(
            _API_URL,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json=payload, timeout=_TIMEOUT,
        )
    except Exception as e:  # network, DNS, timeout…
        raise RuntimeError(f"OpenAI request failed ({type(e).__name__}: {e})") from e
    if r.status_code != 200:
        raise RuntimeError(f"OpenAI API {r.status_code}: {r.text[:300]}")
    try:
        content = r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        raise RuntimeError(f"Unexpected OpenAI response ({type(e).__name__})") from e

    obj = _parse_json(content)
    if not isinstance(obj, dict):
        raise RuntimeError(f"OpenAI did not return usable JSON: {str(content)[:200]}")

    verdict = str(obj.get("verdict", "")).strip().upper()
    is_fake = verdict.startswith("FAKE") or verdict in {"AI", "DEEPFAKE", "MANIPULATED", "GENERATED"}
    category = str(obj.get("category", "")).strip().lower()
    # Reconcile verdict ↔ category: the model sometimes labels an image "ai_generated" / "deepfake_face"
    # / "edited_photo" yet still says verdict "REAL" (or vice-versa). The category is the more specific
    # signal — trust it.
    if category and category not in ("authentic_photo", "real", "authentic", "genuine", "photo"):
        if any(k in category for k in ("ai", "generat", "deepfake", "fake", "edit", "photoshop", "retouch", "manipulat", "synthet", "gan")):
            is_fake = True
    elif category in ("authentic_photo", "real", "authentic", "genuine", "photo"):
        is_fake = False
    try:
        conf = int(round(float(obj.get("confidence", 75))))
    except (TypeError, ValueError):
        conf = 75
    conf = max(50, min(99, conf))
    has_face = obj.get("has_face")
    clues = [str(c).strip() for c in (obj.get("clues") or []) if str(c).strip()][:6]
    return {
        "is_fake": is_fake,
        "category": category,
        "confidence_pct": conf,
        "has_face": (bool(has_face) if isinstance(has_face, bool) else None),
        "reason": str(obj.get("reason", "")).strip(),
        "clues": clues,
        "model": _MODEL,
    }


def _parse_json(s):
    if not isinstance(s, str):
        return None
    s = s.strip()
    try:
        return json.loads(s)
    except Exception:
        pass
    m = re.search(r"\{.*\}", s, re.S)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            return None
    return None
