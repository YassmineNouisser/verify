"""OpenAI-vision assessment of visual manipulation & emotional persuasion for io2.

The bundled local pipeline (RoBERTa text classifier + ViT clickbait + DETR urgency + a hand-tuned
fusion) misses obvious cues — e.g. it rated an image whose only text was "ACT NOW" as "neutral /
authentic". When an OpenAI key is configured we instead let a vision model (GPT-4o by default) read
the image + the OCR'd text and rate the persuasion/manipulation, while the local DETR is still used
to draw the urgency-element boxes.

Reuses io1's key loader. Env: IO2_OPENAI_MODEL (default IO1_OPENAI_MODEL or "gpt-4o"), IO2_OPENAI_TIMEOUT.
"""
from __future__ import annotations

import base64
import io
import json
import os
import re

try:
    from backend.modules.io1_ai_generated.openai_vision import api_key as _io1_api_key
except Exception:  # pragma: no cover
    _io1_api_key = None

_MODEL = (os.environ.get("IO2_OPENAI_MODEL") or os.environ.get("IO1_OPENAI_MODEL") or "gpt-4o").strip() or "gpt-4o"
_TIMEOUT = float(os.environ.get("IO2_OPENAI_TIMEOUT", os.environ.get("IO1_OPENAI_TIMEOUT", "60")))
_API_URL = "https://api.openai.com/v1/chat/completions"


def api_key():
    k = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if k:
        return k
    if _io1_api_key is not None:
        try:
            return _io1_api_key()
        except Exception:
            return None
    return None


def available() -> bool:
    return bool(api_key())


def model_name() -> str:
    return _MODEL


_SYSTEM = (
    "You are a media-literacy analyst for a fact-checking newsroom. You receive ONE image (an ad, poster, "
    "social-media graphic, headline card, news photo…) and the text that OCR read from it. Rate how strongly "
    "the image uses EMOTIONAL PERSUASION and VISUAL MANIPULATION to push the viewer toward a reaction or "
    "action — and name the techniques.\n"
    "Techniques to look for: false urgency / scarcity ('ACT NOW', 'LIMITED TIME', 'ONLY TODAY', countdown "
    "timers, 'before it's too late'); alarmist or fear-inducing language and imagery; loaded / sensational "
    "headlines and ALL-CAPS shouting; heroic or dramatised framing (low-angle 'hero shot', staged crowds, "
    "tear-jerk close-ups); manipulative colour grading (heavy reds/oranges for danger, washed-out for despair); "
    "fake authority / fake social proof ('doctors hate this', '#1 recommended', fabricated ratings); "
    "guilt / shame appeals; cropping or framing that hides context; clickbait ('you won't believe…', "
    "'this one trick…').\n"
    "Be calibrated: a plain, informative image with neutral text is AUTHENTIC with a LOW manipulation level. "
    "Reserve high levels for content that is clearly engineered to manipulate. But note: a strong urgency / "
    "call-to-action phrase like 'ACT NOW' is itself a persuasion technique — never call such an image 'neutral'.\n"
    "Answer with ONLY a JSON object (no markdown) with EXACTLY these keys:\n"
    '  "verdict": "AUTHENTIC" or "MANIPULATIVE"\n'
    '  "manipulation_level": integer 0-100 — overall strength of persuasion/manipulation\n'
    '  "techniques": array of short ENGLISH strings, each one technique you identified (empty if none)\n'
    '  "text_tone": "neutral" or "persuasive" or "alarmist" — the tone of the text in the image\n'
    '  "confidence": integer 50-99 — how certain you are of the verdict\n'
    '  "reason": 1 to 3 short ENGLISH sentences in plain language\n'
    '  "clues": array of short ENGLISH strings naming the concrete visual clues you used (empty if none)\n'
    "CONSISTENCY: if techniques is non-empty OR text_tone is not \"neutral\", verdict must be \"MANIPULATIVE\" "
    "and manipulation_level should be at least 40."
)


def analyze(pil_image, ocr_text: str = "") -> dict | None:
    """Returns a normalized dict, or None if no key / no `requests`. Raises RuntimeError on API error."""
    key = api_key()
    if not key:
        return None
    try:
        import requests  # noqa: F401
    except ImportError:
        return None

    img = pil_image.convert("RGB")
    img.thumbnail((1024, 1024))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")

    ocr_text = (ocr_text or "").strip()
    user_text = ("Rate this image for emotional persuasion and visual manipulation, and name the techniques. "
                 "Return only the requested JSON.")
    if ocr_text:
        user_text += f"\n\nText OCR read from the image: «{ocr_text[:600]}»"

    payload = {
        "model": _MODEL,
        "temperature": 0,
        "max_tokens": 700,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": [
                {"type": "text", "text": user_text},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}", "detail": "high"}},
            ]},
        ],
    }
    import requests
    try:
        r = requests.post(
            _API_URL,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json=payload, timeout=_TIMEOUT,
        )
    except Exception as e:
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

    techniques = [str(t).strip() for t in (obj.get("techniques") or []) if str(t).strip()][:8]
    tone = str(obj.get("text_tone", "")).strip().lower()
    if tone not in ("neutral", "persuasive", "alarmist"):
        tone = "alarmist" if any(w in (s.lower() for s in techniques) for w in ("urgenc", "alarm", "fear")) else ("persuasive" if techniques else "neutral")
    verdict = str(obj.get("verdict", "")).strip().upper()
    is_manip = verdict.startswith("MANIP") or verdict in ("FAKE", "TRUE")  # "MANIPULATIVE"
    # reconcile: techniques / non-neutral tone ⇒ manipulative
    if techniques or tone != "neutral":
        is_manip = True
    try:
        level = int(round(float(obj.get("manipulation_level", 50 if is_manip else 15))))
    except (TypeError, ValueError):
        level = 50 if is_manip else 15
    level = max(0, min(100, level))
    if is_manip:
        level = max(level, 40)
    else:
        level = min(level, 30)
    try:
        conf = max(50, min(99, int(round(float(obj.get("confidence", 80))))))
    except (TypeError, ValueError):
        conf = 80
    reason = str(obj.get("reason", "")).strip()
    clues = [str(c).strip() for c in (obj.get("clues") or []) if str(c).strip()][:6]
    return {
        "is_manipulative": is_manip,
        "level": level,
        "techniques": techniques,
        "text_tone": tone,
        "confidence_pct": conf,
        "reason": reason,
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
            pass
    return None
