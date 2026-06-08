"""
Generates a non-technical "reading of the result", in English, for the end user.

Goal: turn a module's raw result (verdict, scores, sometimes technical labels…) into a CLEAR,
REASSURING and CREDIBLE explanation — why this verdict, what mattered, what was checked — with no
jargon ("Grad-CAM", "softmax", "spectral artifacts"…). Designed for the experience of the person
reading the report: they must understand and trust the result.

Wired in as post-processing inside the routers:
    from backend.shared.xai_narrative import attach_narrative
    attach_narrative(result, "io2", thumb=pil_image)        # adds result["narrative"] if possible

OpenAI key: env var OPENAI_API_KEY, otherwise backend/data/openai_key.txt.
Model: IO_XAI_MODEL (default gpt-4o-mini). Disable: IO_XAI_NARRATIVE=off.
No key / no `requests` / on error → does nothing (the front end copes without it).
"""
from __future__ import annotations

import base64
import io
import json
import os
import re

_KEY_FILE = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "data", "openai_key.txt"))
_MODEL = (os.environ.get("IO_XAI_MODEL") or "gpt-4o-mini").strip() or "gpt-4o-mini"
_TIMEOUT = float(os.environ.get("IO_XAI_TIMEOUT", "45"))
_API_URL = "https://api.openai.com/v1/chat/completions"
_ENABLED = (os.environ.get("IO_XAI_NARRATIVE", "on").strip().lower() not in {"", "0", "off", "false", "no"})

_CONF_ALLOWED = ["Almost certain", "Very likely", "Likely", "Plausible — to confirm", "Uncertain"]


def _api_key() -> str | None:
    k = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if k:
        return k
    try:
        with open(_KEY_FILE, encoding="utf-8") as f:
            return f.read().strip().strip('"').strip("'") or None
    except OSError:
        return None


def available() -> bool:
    return _ENABLED and bool(_api_key())


_MODULE_CONTEXT = {
    "io1": "Detection of AI-generated photos/videos or faked faces (deepfakes): genuine capture or fabricated image.",
    "io2": "Detection of images manipulated to persuade or visually mislead (compositing, deceptive cropping, staging).",
    "io3": "Coherence between an image (or a video) and the caption / text that accompanies it.",
    "io4": "Detection of edits in a photo: regions added, erased, duplicated, spliced in.",
    "io5": "Caption fidelity: does the caption honestly describe what the media actually shows.",
    "io6": "Checking the claims of a cosmetic ad: exaggerated, unproven or misleading claims.",
}

_SYSTEM = (
    "You are the writer of a verification report for the general public (serious press / fact-checking). "
    "You are given the RAW result of an automated analysis module: a verdict, a confidence level, "
    "and sometimes technical labels or scores. "
    "Your job: write, for the person reading this report, a CLEAR, REASSURING and CREDIBLE explanation "
    "of this verdict — why we arrive there, what mattered, what was reviewed — so that they UNDERSTAND "
    "the result and TRUST it.\n"
    "ABSOLUTE RULES:\n"
    "- Zero technical jargon. Forbidden: Grad-CAM, heatmap, softmax, logits, neural network, "
    "ResNet, CLIP, embedding, ELA, \"spectral artifacts\", \"convolutional layer\", model names, "
    "raw unexplained percentages, needless jargon. Write as if for a newspaper reader.\n"
    "- Stay FAITHFUL to the verdict and confidence level provided: never contradict the module, do not over-assert, "
    "do not understate either.\n"
    "- Tone: sober, professional, editorial — that of a serious newsroom. No sensationalism, no emoji.\n"
    "- Write EVERYTHING in ENGLISH.\n"
    "Reply ONLY with a JSON object (no markdown, nothing around it) with EXACTLY these keys:\n"
    '  "headline" : the verdict restated in 2 to 5 words, crystal clear (e.g. "Authentic photo", "Image probably edited", "Caption faithful to the media").\n'
    '  "confidence_label" : the level of certainty IN WORDS, exactly one of these values: '
    + ", ".join(f'"{c}"' for c in _CONF_ALLOWED) + ".\n"
    '  "summary" : 2 to 3 sentences explaining the verdict in plain language, in a way that inspires trust, without jargon.\n'
    '  "signals" : array of 2 to 4 short strings — "what led us to this verdict", concrete and understandable.\n'
    '  "checked" : array of 2 to 4 short strings — "what the analysis reviewed", to show how thorough the verification was.\n'
    '  "caveat" : one honest sentence of limitation or advice (e.g. "Human review is still recommended before publication."), or "" if there is nothing notable.'
)


def _result_brief(result: dict) -> str:
    """Serialize the result as compact JSON, dropping the large blobs (base64, frames…)."""
    SKIP_KEYS = {
        "xai", "heatmap", "gradcam_overlay", "gradcam_pure", "gradcam_base64", "face_crop",
        "overlay_base64", "overlay", "image_b64", "frames", "raw", "thumbnail", "thumb",
    }

    def clean(v, depth=0):
        if depth > 4:
            return "…"
        if isinstance(v, dict):
            return {k: clean(x, depth + 1) for k, x in v.items()
                    if k not in SKIP_KEYS and not (isinstance(x, str) and len(x) > 500)}
        if isinstance(v, (list, tuple)):
            return [clean(x, depth + 1) for x in list(v)[:14]]
        if isinstance(v, str) and len(v) > 700:
            return v[:700] + "…"
        return v

    try:
        return json.dumps(clean(result), ensure_ascii=False)[:6500]
    except Exception:
        return str(result)[:2000]


def build(module_id: str, result: dict, *, thumb=None, extra_text: str | None = None) -> dict | None:
    if not available():
        return None
    try:
        import requests
    except ImportError:
        return None

    ctx = _MODULE_CONTEXT.get((module_id or "").lower(), "Visual disinformation analysis.")
    text_block = (
        f"Module: {module_id} — {ctx}\n"
        + (f"Text / caption submitted by the user: \"{extra_text.strip()[:600]}\"\n" if extra_text and extra_text.strip() else "")
        + "Raw module result (JSON):\n"
        + _result_brief(result)
        + "\n\nNow write the requested JSON, in English, with no jargon whatsoever."
    )
    user_parts = [{"type": "text", "text": text_block}]
    if thumb is not None:
        try:
            im = thumb.convert("RGB")
            im.thumbnail((640, 640))
            buf = io.BytesIO()
            im.save(buf, format="JPEG", quality=82)
            b64 = base64.b64encode(buf.getvalue()).decode("ascii")
            user_parts.append({"type": "image_url", "image_url": {
                "url": f"data:image/jpeg;base64,{b64}", "detail": "low"}})
        except Exception:
            pass

    payload = {
        "model": _MODEL,
        "temperature": 0.2,
        "max_tokens": 700,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": user_parts},
        ],
    }
    try:
        r = requests.post(
            _API_URL,
            headers={"Authorization": f"Bearer {_api_key()}", "Content-Type": "application/json"},
            json=payload, timeout=_TIMEOUT,
        )
        if r.status_code != 200:
            return None
        obj = _parse_json(r.json()["choices"][0]["message"]["content"])
    except Exception:
        return None
    if not isinstance(obj, dict):
        return None

    headline = str(obj.get("headline") or "").strip()
    conf = str(obj.get("confidence_label") or "").strip()
    if conf and conf not in _CONF_ALLOWED:
        # recover an approximate wording
        low = conf.lower()
        conf = next((c for c in _CONF_ALLOWED if c.lower() in low or low in c.lower()), conf)
    summary = str(obj.get("summary") or "").strip()
    signals = [str(x).strip() for x in (obj.get("signals") or []) if str(x).strip()][:4]
    checked = [str(x).strip() for x in (obj.get("checked") or []) if str(x).strip()][:4]
    caveat = str(obj.get("caveat") or "").strip()
    if not (summary or headline):
        return None
    return {
        "headline": headline,
        "confidence_label": conf,
        "summary": summary,
        "signals": signals,
        "checked": checked,
        "caveat": caveat,
        "generated_by": "ai",
    }


def attach_narrative(result, module_id: str, *, thumb=None, extra_text: str | None = None):
    """Add `result['narrative']` if a narrative could be produced. Mutates in place, never raises."""
    try:
        if isinstance(result, dict):
            n = build(module_id, result, thumb=thumb, extra_text=extra_text)
            if n:
                result["narrative"] = n
    except Exception:
        pass
    return result


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
