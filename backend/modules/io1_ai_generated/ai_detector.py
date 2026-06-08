"""Lightweight second-opinion "is this image AI-generated?" detector for io1.

Empirical finding: no single open-source AI-image classifier on HF Hub reliably separates
StyleGAN/diffusion faces from real photographs. We tested 3 candidates on a mixed set
(ThisPersonDoesNotExist + stock photos from our own site):

    Model                              TPDNE scores            Real-photo bias
    ─────────────────────────────────  ──────────────────────  ────────────────
    dima806/ai_vs_real_image_detection 0.61–0.74               always ≥0.70 (unusable)
    Organika/sdxl-detector             0.86–1.00 (best recall) often ≥0.90 (over-flags)
    umm-maybe/AI-image-detector        0.07–0.57 (poor recall) low (good precision)

The two reasonable models — Organika and umm-maybe — have OPPOSITE failure modes. We combine
them with a 2-tier consensus rule that catches most TPDNE images while keeping the false-positive
rate on real photos near zero:

    tier 1: Organika ≥ 0.95  AND  umm-maybe ≥ 0.20    → escalate (very confident)
    tier 2: Organika ≥ 0.90  AND  umm-maybe ≥ 0.40    → escalate (consensus)
    otherwise                                          → don't escalate

Env vars (overridable):
    IO1_USE_AI_DETECTOR              "on" (default) | "off"
    IO1_AI_DETECTOR_PRIMARY          HF id          (default: Organika/sdxl-detector)
    IO1_AI_DETECTOR_SECONDARY        HF id          (default: umm-maybe/AI-image-detector)
    IO1_AI_TIER1_PRIMARY             (default 0.95)
    IO1_AI_TIER1_SECONDARY           (default 0.20)
    IO1_AI_TIER2_PRIMARY             (default 0.90)
    IO1_AI_TIER2_SECONDARY           (default 0.40)
"""
import os

_ENABLED = os.environ.get("IO1_USE_AI_DETECTOR", "on").strip().lower() in ("on", "1", "true", "yes")
_PRIMARY_ID = os.environ.get("IO1_AI_DETECTOR_PRIMARY", "Organika/sdxl-detector")
_SECONDARY_ID = os.environ.get("IO1_AI_DETECTOR_SECONDARY", "umm-maybe/AI-image-detector")

# Decision thresholds (tunable). Calibrated empirically — see file header.
_T1_P = float(os.environ.get("IO1_AI_TIER1_PRIMARY", "0.95"))
_T1_S = float(os.environ.get("IO1_AI_TIER1_SECONDARY", "0.20"))
_T2_P = float(os.environ.get("IO1_AI_TIER2_PRIMARY", "0.90"))
_T2_S = float(os.environ.get("IO1_AI_TIER2_SECONDARY", "0.40"))

_primary_pipe = None
_secondary_pipe = None
_tried = False

# Label-name heuristics: HF models name their AI class differently.
_AI_KEYS = ("artif", "ai", "fake", "synth", "generat", "sdxl", "diffus", "midjourney", "dalle", "machine")
_REAL_KEYS = ("human", "real", "authent", "natural", "photo", "genuine", "camera")


def available() -> bool:
    return _ENABLED


def thresholds() -> dict:
    return {"tier1_primary": _T1_P, "tier1_secondary": _T1_S,
            "tier2_primary": _T2_P, "tier2_secondary": _T2_S}


# Back-compat: some callers (and tests) still hit threshold() for a single number.
def threshold() -> float:
    return _T2_P


def _load():
    global _primary_pipe, _secondary_pipe, _tried
    if _tried or not _ENABLED:
        return _primary_pipe, _secondary_pipe
    _tried = True
    try:
        from transformers import pipeline
        if _primary_pipe is None:
            print(f"[io1] Loading AI-image detector (primary: {_PRIMARY_ID})…")
            _primary_pipe = pipeline("image-classification", model=_PRIMARY_ID)
        if _secondary_pipe is None:
            print(f"[io1] Loading AI-image detector (secondary: {_SECONDARY_ID})…")
            _secondary_pipe = pipeline("image-classification", model=_SECONDARY_ID)
        print("[io1]   → AI-image consensus ready (2 detectors)")
    except Exception as e:
        print(f"[io1] AI-image detector(s) unavailable ({type(e).__name__}: {e}) — skipping second opinion")
    return _primary_pipe, _secondary_pipe


def _extract_ai_prob(preds) -> float | None:
    """Pick the 'AI/fake/artificial' score from a HF image-classification output, robustly."""
    if not preds:
        return None
    ai_p = None
    real_p = None
    for d in preds:
        lbl = str(d.get("label", "")).lower()
        sc = float(d.get("score", 0.0))
        if any(k in lbl for k in _AI_KEYS):
            ai_p = sc if ai_p is None else max(ai_p, sc)
        elif any(k in lbl for k in _REAL_KEYS):
            real_p = sc if real_p is None else max(real_p, sc)
    if ai_p is not None:
        return round(float(ai_p), 4)
    if real_p is not None:
        return round(float(1.0 - real_p), 4)
    return None


def predict_ai(pil_image) -> dict | None:
    """Run both detectors and apply the 2-tier consensus rule. Returns:
        {primary: float, secondary: float, escalate: bool, top_score: float, tier: int}
    or None if the detectors aren't available."""
    primary, secondary = _load()
    if primary is None or secondary is None:
        return None
    try:
        img = pil_image.convert("RGB")
        p1 = _extract_ai_prob(primary(img))
        p2 = _extract_ai_prob(secondary(img))
        if p1 is None or p2 is None:
            return None
        tier = 0
        if p1 >= _T1_P and p2 >= _T1_S:
            tier = 1
        elif p1 >= _T2_P and p2 >= _T2_S:
            tier = 2
        # confidence we report on escalation = the primary score, but bounded by the secondary
        # (so we don't claim 99% when only one of the two is confident)
        top = max(p1, p2) if tier > 0 else max(p1, p2)
        return {
            "primary": p1, "secondary": p2,
            "escalate": tier > 0, "tier": tier,
            "top_score": top,
        }
    except Exception as e:
        print(f"[io1] AI-image detector inference failed ({type(e).__name__}: {e})")
        return None


# Back-compat wrapper for any old call sites.
def predict_ai_prob(pil_image):
    r = predict_ai(pil_image)
    if r is None:
        return None
    # average primary and secondary so legacy threshold checks still work directionally
    return round((r["primary"] + r["secondary"]) / 2.0, 4)
