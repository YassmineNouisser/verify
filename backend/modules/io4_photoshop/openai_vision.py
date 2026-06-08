"""OpenAI-vision photo-tampering analysis for io4.

The bundled local CNN ships with no trained weights, so when an OpenAI key is configured
we delegate the "edited / montaged photo vs unedited original" verdict to a vision model
(GPT-4o by default) — same key resolution as io1 (OPENAI_API_KEY env, else
backend/data/openai_key.txt).

Env vars:
    IO4_OPENAI_MODEL    vision model         (default: IO1_OPENAI_MODEL or "gpt-4o")
    IO4_OPENAI_TIMEOUT  HTTP timeout, seconds (default: IO1_OPENAI_TIMEOUT or 60)
"""
from __future__ import annotations

import base64
import io
import json
import os
import re

try:  # reuse io1's key loader (env var or backend/data/openai_key.txt)
    from backend.modules.io1_ai_generated.openai_vision import api_key as _io1_api_key
except Exception:  # pragma: no cover
    _io1_api_key = None

_MODEL = (os.environ.get("IO4_OPENAI_MODEL") or os.environ.get("IO1_OPENAI_MODEL") or "gpt-4o").strip() or "gpt-4o"
_TIMEOUT = float(os.environ.get("IO4_OPENAI_TIMEOUT", os.environ.get("IO1_OPENAI_TIMEOUT", "60")))
_API_URL = "https://api.openai.com/v1/chat/completions"

_EDIT_TYPES = ("none", "inpainting", "copy_move", "splicing", "enhancement", "other")


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
    "You are a senior photo-forensics analyst for a fact-checking newsroom. You receive ONE image and "
    "must decide whether the photograph has been LOCALLY, DIGITALLY EDITED (a region retouched, montaged, "
    "added or removed) or is an unedited original.\n"
    "STRONG PRIOR — assume AUTHENTIC. The vast majority of real photos are NOT tampered. You may only answer "
    "FAKE if you can point to a SPECIFIC, CONCRETE, LOCALISED artifact and name exactly where it is. If you "
    "cannot articulate a concrete clue, the answer is AUTHENTIC. Do NOT guess, do NOT speculate, do NOT call an "
    "image edited just because it is clean, well-lit, professional, high-resolution, a studio/stock shot, a "
    "portrait, an ad, or because it 'could have been' edited. Plausibility is not evidence.\n"
    "Things that are NOT tampering (→ AUTHENTIC, edit_type \"none\"): cropping, rotation, resizing; global "
    "exposure / contrast / white-balance / saturation; a colour filter or LUT applied to the whole frame; "
    "global sharpening, denoise, vignette; JPEG re-compression or screenshotting; a watermark, logo, caption, "
    "border or meme text laid over the picture; normal lens bokeh / depth-of-field; motion blur; lens flare; "
    "ordinary studio lighting and a clean backdrop. None of these change what the picture shows.\n"
    "Things that ARE tampering (→ FAKE), only when you actually SEE the trace: copy-move (the exact same "
    "texture / object / person duplicated within the frame); splicing / compositing (a pasted object with a "
    "cut-out halo, edge fringing, or lighting / shadow-direction / perspective / colour-temperature / "
    "noise-grain that clearly does not match the rest of the scene); inpainting (an object removed and the gap "
    "filled with a smeared or repeated patch, or a shadow / reflection left behind of something that is gone); "
    "local retouch (a face/body region obviously liquified, a blemish or person painted out) leaving a soft "
    "warped patch.\n"
    "FACES — look carefully at the mouth, eyes, nose and jawline: a swapped or edited facial feature often "
    "leaves a faint blending seam around it, a patch whose skin texture / sharpness / noise differs from the "
    "rest of the face, an asymmetry, or a feature that doesn't quite line up with the head's pose and lighting. "
    "If you genuinely see such a seam, report it (edit_type \"splicing\" or \"enhancement\", region on that "
    "feature). But still obey the prior: if the face just looks slightly imperfect with NO concrete localised "
    "seam you can name, it is AUTHENTIC — do not flag a face as edited on a hunch.\n"
    "WHOLLY SYNTHETIC IMAGES — separately, judge whether the ENTIRE picture was produced by an image generator "
    "(a GAN face such as 'thispersondoesnotexist'; a Midjourney / DALL-E / Stable-Diffusion / Flux text-to-image "
    "picture; a 3D render passed off as a photo). GAN-face tells: a background that dissolves into abstract "
    "colour blur, hair strands fusing into the backdrop, water-colour-like reddish skin blotches, asymmetric or "
    "melted earrings / glasses, odd teeth or ears. Text-to-image tells: the over-clean 'concept-art / render / "
    "stock' look with no real-world contingency, slightly-too-perfect lighting and composition. If the whole "
    "image is synthetic, set \"synthetic\": true — this is INDEPENDENT of whether a local edit is also present, "
    "and it means the image is not an authentic photograph at all.\n"
    "Answer with ONLY a JSON object (no markdown, no prose around it) with EXACTLY these keys:\n"
    '  "verdict": "AUTHENTIC" or "FAKE"\n'
    '  "edit_type": one of "none", "inpainting", "copy_move", "splicing", "enhancement", "other"\n'
    '  "synthetic": true or false — is the ENTIRE image AI/GAN-generated (not a real photograph at all)\n'
    '  "confidence": integer 50-99 — how certain you are of the verdict\n'
    '  "region": rough location of the most suspicious area, "<top|middle|bottom> <left|center|right>", or "none"\n'
    '  "reason": 1 to 3 short ENGLISH sentences in plain language for a general audience\n'
    '  "clues": array of short ENGLISH strings, each naming ONE concrete visual artifact you actually saw and '
    "where it is (empty array if the image is authentic — never invent clues to justify a FAKE)\n"
    "CONSISTENCY: (a) if \"synthetic\" is true the image is NOT authentic — verdict must be \"FAKE\"; "
    "(b) if verdict is \"FAKE\" then EITHER synthetic is true OR (edit_type is not \"none\" AND clues is "
    "non-empty AND region is not \"none\"); (c) otherwise verdict is \"AUTHENTIC\", edit_type \"none\", "
    "synthetic false, region \"none\", clues []."
)


def analyze(pil_image):
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

    payload = {
        "model": _MODEL,
        "temperature": 0,
        "max_tokens": 600,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": [
                {"type": "text", "text": "Analyze this image for local digital tampering AND for being a wholly AI/GAN-generated picture. Return only the requested JSON."},
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

    verdict = str(obj.get("verdict", "")).strip().upper()
    is_fake = verdict.startswith("FAKE") or verdict in {"EDITED", "TAMPERED", "MANIPULATED"}
    edit_type = str(obj.get("edit_type", "")).strip().lower().replace("-", "_").replace(" ", "_")
    if edit_type not in _EDIT_TYPES:
        edit_type = "other" if is_fake else "none"
    if edit_type != "none":
        is_fake = True
    sv = obj.get("synthetic")
    is_synthetic = (sv is True) or (str(sv).strip().lower() in ("true", "1", "yes", "ai", "gan", "synthetic"))

    try:
        conf = int(round(float(obj.get("confidence", 75))))
    except (TypeError, ValueError):
        conf = 75
    conf = max(50, min(99, conf))
    region = (str(obj.get("region", "")).strip().lower() or "none")
    reason = str(obj.get("reason", "")).strip()
    clues = [str(c).strip() for c in (obj.get("clues") or []) if str(c).strip()][:6]
    # Anti-false-positive guard: a FAKE *editing* verdict is only credible with a concrete localised clue.
    # (A "synthetic" verdict is exempt — its evidence is the whole-image generative look, not a local patch.)
    if is_fake and not is_synthetic and (not clues or region in ("none", "", "n/a")):
        is_fake = False
        edit_type = "none"
        region = "none"
        clues = []
        if not reason:
            reason = "No concrete sign of local editing — the photo appears to be an unedited original."
    if is_synthetic:
        is_fake = True
    if is_fake and edit_type == "none" and not is_synthetic:
        edit_type = "other"
    if not is_fake:
        edit_type = "none"
    return {
        "is_fake": is_fake,
        "is_synthetic": is_synthetic,
        "edit_type": edit_type,
        "confidence_pct": conf,
        "region": region,
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
