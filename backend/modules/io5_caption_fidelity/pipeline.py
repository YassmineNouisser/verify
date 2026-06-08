"""Pipeline io5 — Caption Fidelity.

Question: does the caption (or alt-text, social-media headline, news cutline) **faithfully describe
what is in the image**, or is it misleading / exaggerated / unrelated?

Approach — 100% local, no external API:

  1. CLIP ViT-B/32 zero-shot similarity        — global image↔caption alignment
  2. CLIP per-object scoring                   — split the caption into noun phrases and check
                                                 each against the image; identifies the specific
                                                 fragments that don't match
  3. OCR cross-check (EasyOCR)                 — if the caption mentions words that appear as
                                                 on-screen text, that's strong evidence of fidelity
  4. Sentiment tone gap                         — alarmist / exaggerated caption on a calm image
                                                 is a fidelity-loss signal

Output verdict: FAITHFUL / PARTIAL / MISLEADING with calibrated confidence and a per-phrase
breakdown so the user sees exactly which parts of the caption are unsupported.
"""
from __future__ import annotations

import base64
import io as _io
import os
import re
import warnings

from backend.shared.device import DEVICE

warnings.filterwarnings("ignore")

# ─── Config ─────────────────────────────────────────────────────────────────
CLIP_MODEL = os.environ.get("IO5_CLIP_MODEL", "ViT-B-32")
CLIP_PRETRAINED = os.environ.get("IO5_CLIP_PRETRAINED", "openai")
FAITHFUL_THRESHOLD = float(os.environ.get("IO5_FAITHFUL_THRESHOLD", "0.60"))
MISLEADING_THRESHOLD = float(os.environ.get("IO5_MISLEADING_THRESHOLD", "0.40"))

# ─── Lazy heavy deps ────────────────────────────────────────────────────────
np = torch = F = Image = cv2 = None
_HEAVY_DEPS_LOADED = False


def _ensure_heavy_deps():
    global np, torch, F, Image, cv2, _HEAVY_DEPS_LOADED
    if _HEAVY_DEPS_LOADED:
        return
    try:
        import numpy as _np
        import torch as _torch
        import torch.nn.functional as _F
        from PIL import Image as _Image
        import cv2 as _cv2
    except ImportError as e:
        raise RuntimeError(
            f"Module io5 — missing ML dependencies ({e}). "
            "Install: pip install -r backend/requirements.txt"
        ) from e
    np, torch, F, Image, cv2 = _np, _torch, _F, _Image, _cv2
    _HEAVY_DEPS_LOADED = True


# ─── Globals ─────────────────────────────────────────────────────────────────
_clip_model = None
_clip_preprocess = None
_clip_tokenizer = None
_ocr_reader = None
LOADED = False
INFO: dict = {}


# ─── Stop words for noun-phrase extraction ──────────────────────────────────
_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "of", "in", "on", "at", "to", "for", "with", "by", "from", "as",
    "and", "or", "but", "this", "that", "these", "those",
    "it", "its", "they", "them", "their", "we", "us", "our", "you", "your",
    "le", "la", "les", "un", "une", "des", "du", "de", "et", "ou",
    "pour", "avec", "sans", "sur", "dans", "ce", "cette", "ces",
}

# Alarmist / exaggerated lexicon — used to detect tone-gap mismatches
_ALARMIST = {
    "shocking", "shock", "horror", "horrible", "catastrophe", "disaster",
    "alarming", "terrifying", "scandal", "scandalous", "outrageous", "explosive",
    "choquant", "horrible", "catastrophe", "scandale", "scandaleux", "alarmant",
    "miracle", "miraculous", "miraculeux", "incredible", "incroyable", "unbelievable",
}


# ============================================================================
# INIT
# ============================================================================
def init() -> dict:
    global _clip_model, _clip_preprocess, _clip_tokenizer, _ocr_reader, LOADED, INFO
    if LOADED:
        return INFO

    _ensure_heavy_deps()
    print(f"[io5] Device: {DEVICE}")
    print(f"[io5] Loading CLIP {CLIP_MODEL} ({CLIP_PRETRAINED})…")
    import open_clip
    _clip_model, _, _clip_preprocess = open_clip.create_model_and_transforms(CLIP_MODEL, pretrained=CLIP_PRETRAINED)
    _clip_tokenizer = open_clip.get_tokenizer(CLIP_MODEL)
    _clip_model = _clip_model.to(DEVICE).eval()

    print("[io5] Loading EasyOCR (en + fr) for caption↔on-screen-text cross-check…")
    import easyocr
    _ocr_reader = easyocr.Reader(["en", "fr"], gpu=(DEVICE == "cuda"), verbose=False)

    INFO = {
        "device": DEVICE,
        "clip": f"open_clip {CLIP_MODEL} ({CLIP_PRETRAINED})",
        "ocr": "easyocr (en, fr)",
        "thresholds": {"faithful": FAITHFUL_THRESHOLD, "misleading": MISLEADING_THRESHOLD},
        "verdict_backend": "local (CLIP image↔text similarity + OCR cross-check)",
    }
    LOADED = True
    print(f"[io5] ✅ Pipeline io5 ready on {DEVICE}")
    return INFO


# ============================================================================
# Encoders
# ============================================================================
def _encode_image(pil_image):
    with torch.no_grad():
        x = _clip_preprocess(pil_image.convert("RGB")).unsqueeze(0).to(DEVICE)
        emb = _clip_model.encode_image(x)
        return F.normalize(emb, dim=-1)


def _encode_texts(texts: list):
    with torch.no_grad():
        toks = _clip_tokenizer(texts).to(DEVICE)
        emb = _clip_model.encode_text(toks)
        return F.normalize(emb, dim=-1)


def _cos(a, b) -> float:
    return float((a * b).sum().item())


# ============================================================================
# Noun-phrase extraction (light — no spaCy dependency)
# ============================================================================
def _phrases(text: str) -> list:
    """Split a caption into noun-phrase-like fragments for per-fragment scoring."""
    if not text:
        return []
    # Split on punctuation and conjunctions; keep meaningful chunks of 2-6 words
    chunks = re.split(r"[.,;:!?\n]| and | or | but | et | ou | mais ", text, flags=re.IGNORECASE)
    out = []
    for c in chunks:
        words = [w for w in re.findall(r"[A-Za-zÀ-ÿ'’\-]+", c)
                 if w.lower() not in _STOPWORDS and len(w) > 1]
        if 2 <= len(words) <= 8:
            phrase = " ".join(words)
            if phrase and phrase.lower() not in {p.lower() for p in out}:
                out.append(phrase)
    return out[:6]


# ============================================================================
# OCR helper
# ============================================================================
def _ocr_text(pil_image) -> str:
    arr = np.asarray(pil_image.convert("RGB"))
    try:
        results = _ocr_reader.readtext(arr, detail=1, paragraph=False)
    except Exception:
        results = []
    parts = [t for _bbox, t, c in results if c >= 0.35 and t.strip()]
    return " ".join(parts)


def _word_overlap(a: str, b: str) -> float:
    sa = {w.lower() for w in re.findall(r"[A-Za-zÀ-ÿ]+", a) if len(w) > 2 and w.lower() not in _STOPWORDS}
    sb = {w.lower() for w in re.findall(r"[A-Za-zÀ-ÿ]+", b) if len(w) > 2 and w.lower() not in _STOPWORDS}
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / max(1, len(sa))


# ============================================================================
# Sentiment / tone proxy
# ============================================================================
def _alarmist_score(text: str) -> float:
    words = {w.lower() for w in re.findall(r"[A-Za-zÀ-ÿ]+", text)}
    hits = len(words & _ALARMIST)
    exclam = text.count("!")
    return min(1.0, 0.30 * hits + 0.10 * exclam)


# ============================================================================
# Verdict
# ============================================================================
def _verdict_from_score(sim: float) -> tuple:
    if sim >= FAITHFUL_THRESHOLD:
        return "FAITHFUL", "#22C55E"
    if sim >= MISLEADING_THRESHOLD:
        return "PARTIAL", "#F59E0B"
    return "MISLEADING", "#E53E3E"


# ============================================================================
# Visual overlay — gradient saliency of the (caption ↔ image) similarity
# ============================================================================
def _saliency_overlay_b64(pil_image, caption: str) -> str | None:
    if not caption:
        return None
    try:
        x = _clip_preprocess(pil_image.convert("RGB")).unsqueeze(0).to(DEVICE)
        x.requires_grad_(True)
        img_emb = F.normalize(_clip_model.encode_image(x), dim=-1)
        txt_emb = _encode_texts([caption])
        sim = (img_emb @ txt_emb.T).sum()
        _clip_model.zero_grad()
        sim.backward()
        sal = x.grad.detach().abs().squeeze(0).mean(0).cpu().numpy()
        sal = (sal - sal.min()) / (sal.max() - sal.min() + 1e-8)
        orig = np.array(pil_image.convert("RGB"))
        H, W = orig.shape[:2]
        sal_up = cv2.resize(sal, (W, H), interpolation=cv2.INTER_CUBIC)
        heat = cv2.applyColorMap((sal_up * 255).astype(np.uint8), cv2.COLORMAP_JET)
        heat = cv2.cvtColor(heat, cv2.COLOR_BGR2RGB)
        overlay = (0.55 * orig + 0.45 * heat).astype(np.uint8)
        return _b64_png_from_array(overlay)
    except Exception as e:
        print(f"[io5] saliency failed: {e}")
        return None


def _b64_png_from_array(arr):
    img = Image.fromarray(arr.astype(np.uint8), mode="RGB")
    b = _io.BytesIO()
    img.save(b, format="PNG")
    return base64.b64encode(b.getvalue()).decode("ascii")


# ============================================================================
# Public entry point
# ============================================================================
def analyze(pil_image, caption: str) -> dict:
    init()
    caption = (caption or "").strip()
    if not caption:
        raise ValueError("io5 requires a caption to compare against the image.")

    # 1. Global CLIP similarity (raw cosine in CLIP feature space, in [-1, 1] practice ~[0.1, 0.4])
    img_emb = _encode_image(pil_image)
    cap_emb = _encode_texts([caption])
    raw_sim = _cos(img_emb[0], cap_emb[0])

    # Calibrate to [0, 1] using a sigmoid centred on the empirical "neutral" CLIP score (~0.22).
    # This makes thresholds (0.40 / 0.60) intuitive.
    cal_sim = float(1.0 / (1.0 + np.exp(-(raw_sim - 0.20) * 20.0)))

    # 2. Per-phrase scoring — identifies fragments of the caption that don't appear in the image
    phrases = _phrases(caption)
    phrase_scores = []
    if phrases:
        ph_embs = _encode_texts(phrases)
        for i, ph in enumerate(phrases):
            s = _cos(img_emb[0], ph_embs[i])
            cs = float(1.0 / (1.0 + np.exp(-(s - 0.20) * 20.0)))
            phrase_scores.append({"phrase": ph, "raw_sim": round(s, 3), "score": round(cs, 3),
                                  "supported": bool(cs >= MISLEADING_THRESHOLD)})

    # 3. OCR cross-check — caption words that appear as on-screen text in the image
    ocr = _ocr_text(pil_image)
    ocr_overlap = _word_overlap(caption, ocr) if ocr else 0.0

    # 4. Tone-gap — alarmist caption on a sober image is a misleading-style signal
    alarmism = _alarmist_score(caption)
    visual_calm = 1.0 - cal_sim  # if image doesn't match caption, an alarmist caption is suspicious
    tone_gap = float(min(1.0, alarmism * visual_calm))

    # Combine: global similarity is the main driver; OCR overlap is a confidence boost when it fires;
    # tone-gap is a penalty (alarmist caption + low visual match).
    score = cal_sim
    if ocr_overlap >= 0.30:
        score = min(1.0, score + 0.15 * ocr_overlap)
    if tone_gap >= 0.30:
        score = max(0.0, score - 0.20 * tone_gap)

    verdict, color = _verdict_from_score(score)

    # Confidence (how far we are from the nearest threshold)
    if verdict == "FAITHFUL":
        conf = min(1.0, 0.60 + (score - FAITHFUL_THRESHOLD) * 1.5)
    elif verdict == "MISLEADING":
        conf = min(1.0, 0.60 + (MISLEADING_THRESHOLD - score) * 1.5)
    else:
        conf = 0.55

    # Pick the weakest phrases to flag explicitly
    unsupported = [p for p in phrase_scores if not p["supported"]]
    unsupported.sort(key=lambda p: p["score"])
    weakest = unsupported[:3]

    explain_bits = [
        f"CLIP image↔caption similarity: {int(score*100)}%.",
    ]
    if verdict == "FAITHFUL":
        explain_bits.append("The caption matches the image content well.")
    elif verdict == "PARTIAL":
        explain_bits.append("The caption partly matches: some elements are supported, others aren't visible.")
    else:
        explain_bits.append("The caption does not appear to describe what is in the image.")
    if weakest:
        explain_bits.append("Unsupported fragments: " + "; ".join(f"\"{p['phrase']}\"" for p in weakest) + ".")
    if ocr_overlap >= 0.30:
        explain_bits.append(f"On-screen text shares {int(ocr_overlap*100)}% of the caption's distinctive words — supports the caption.")
    if tone_gap >= 0.30:
        explain_bits.append("The caption uses alarmist/sensational language that the image itself does not justify.")

    saliency_b64 = _saliency_overlay_b64(pil_image, caption)

    xai = {}
    if saliency_b64:
        xai["clip_saliency"] = saliency_b64

    return {
        "verdict": verdict,
        "verdict_color": color,
        "score": round(score, 3),
        "confidence": round(conf, 3),
        "raw_clip_similarity": round(raw_sim, 3),
        "calibrated_similarity": round(cal_sim, 3),
        "ocr_overlap": round(ocr_overlap, 3),
        "ocr_text": ocr,
        "tone_gap": round(tone_gap, 3),
        "phrase_breakdown": phrase_scores,
        "unsupported_phrases": [p["phrase"] for p in weakest],
        "caption": caption,
        "explanation": " ".join(explain_bits),
        "explanation_source": "local",
        "model_used": f"open_clip {CLIP_MODEL} ({CLIP_PRETRAINED}) + EasyOCR",
        "image_size": {"width": pil_image.size[0], "height": pil_image.size[1]},
        "xai": xai,
    }
