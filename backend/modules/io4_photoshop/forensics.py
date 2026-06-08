"""Local image-forensics toolkit for io4 — 100% offline, no model needed.

Combines three classic, model-free techniques that each catch a different family of edits:

  1. ELA (Error-Level Analysis) — re-save at a known JPEG quality, diff with the original,
     amplify. A spliced/pasted region was re-encoded a different number of times than the
     surrounding pixels, so it lights up brighter. Best for splicing/copy-paste.

  2. Noise residual analysis — denoise (median 3x3) and subtract. Authentic photos have a
     uniform sensor-noise floor across the frame; a pasted region from another source carries
     a foreign noise signature, producing a measurable variance break. Best for splicing/inpainting.

  3. JPEG ghost — re-save the image at several JPEG qualities and look for a quality at which
     a sub-region's error drops sharply (the "ghost" of its original compression). Best for
     spliced regions taken from a differently-compressed source.

Each function returns floats in [0,1] plus a heatmap. The pipeline fuses them into a verdict.
"""
from __future__ import annotations

import base64
import io as _io
import os

_ELA_QUALITY = int(os.environ.get("IO4_ELA_QUALITY", "90"))
_GHOST_QUALITIES = (60, 70, 75, 80, 85, 90)


def _b64_png(pil_im) -> str:
    b = _io.BytesIO()
    pil_im.save(b, format="PNG")
    return base64.b64encode(b.getvalue()).decode("ascii")


def _region_name(cy: float, cx: float) -> str:
    v = "top" if cy < 1 / 3 else ("middle" if cy < 2 / 3 else "bottom")
    h = "left" if cx < 1 / 3 else ("center" if cx < 2 / 3 else "right")
    return f"{v} {h}"


# ────────────────────────────────────────────────────────────────────────────
# 1. ELA
# ────────────────────────────────────────────────────────────────────────────
def ela(pil_image):
    """Return {score, region, overlay_b64, raw_b64, hot_frac}."""
    import numpy as np
    from PIL import Image, ImageChops

    orig = pil_image.convert("RGB")
    orig.thumbnail((1024, 1024))
    buf = _io.BytesIO()
    orig.save(buf, format="JPEG", quality=_ELA_QUALITY)
    buf.seek(0)
    resaved = Image.open(buf).convert("RGB")
    diff = ImageChops.difference(orig, resaved)
    arr = np.asarray(diff).astype(np.float32)
    mag = arr.max(axis=2)
    mx = float(mag.max())
    if mx < 1e-6:
        return {"score": 0.0, "region": "none", "overlay_b64": None, "raw_b64": None, "hot_frac": 0.0}

    norm = mag / mx
    scaled = (np.clip(norm * 255.0 * 2.2, 0, 255)).astype(np.uint8)
    h, w = norm.shape

    hot = norm > 0.45
    hot_frac = float(hot.mean())
    if hot_frac <= 1e-4:
        score = 0.0
        region = "none"
    else:
        ys, xs = np.where(hot)
        bb = ((ys.max() - ys.min() + 1) * (xs.max() - xs.min() + 1)) / float(h * w)
        rest = norm[~hot]
        rest_mean = float(rest.mean()) if rest.size else 0.0
        hot_mean = float(norm[hot].mean())
        contrast = (hot_mean - rest_mean) / (hot_mean + 1e-6)
        small = max(0.0, 1.0 - hot_frac / 0.10)
        compact = max(0.0, 1.0 - bb / 0.45)
        score = float(np.clip(0.45 * small + 0.30 * compact + 0.25 * contrast, 0.0, 1.0))
        if hot_frac > 0.30 or bb > 0.7:
            score = min(score, 0.25)
        cy = float(ys.mean()) / h
        cx = float(xs.mean()) / w
        region = _region_name(cy, cx) if score >= 0.4 else "none"

    # Colourised heatmap (no matplotlib)
    g = scaled.astype(np.float32) / 255.0
    r_ch = np.clip(g * 1.6, 0, 1)
    g_ch = np.clip(g * 1.1, 0, 1)
    b_ch = np.clip(0.35 - g * 0.35, 0, 1)
    heat = (np.stack([r_ch, g_ch, b_ch], axis=2) * 255).astype(np.uint8)
    base = np.asarray(orig).astype(np.float32)
    over = (0.45 * base + 0.55 * heat.astype(np.float32)).clip(0, 255).astype(np.uint8)

    return {
        "score": round(float(score), 3),
        "region": region,
        "overlay_b64": _b64_png(Image.fromarray(over, "RGB")),
        "raw_b64": _b64_png(Image.fromarray(heat, "RGB")),
        "hot_frac": round(hot_frac, 4),
    }


# ────────────────────────────────────────────────────────────────────────────
# 2. Noise residual
# ────────────────────────────────────────────────────────────────────────────
def noise_residual(pil_image):
    """Block-wise noise-variance map: a spliced region shows up as a contrasting block.

    Returns {score, region, overlay_b64, heterogeneity}.
    """
    import numpy as np
    from PIL import Image

    try:
        import cv2
    except ImportError:
        cv2 = None

    rgb = pil_image.convert("RGB")
    rgb.thumbnail((1024, 1024))
    arr = np.asarray(rgb).astype(np.float32)
    gray = arr.mean(axis=2)

    # Denoise via 3x3 median (cv2 if available, else a hand-rolled sliding-window)
    if cv2 is not None:
        denoised = cv2.medianBlur(gray.astype(np.uint8), 3).astype(np.float32)
    else:
        # naïve fallback: blur with a 3x3 mean filter (less effective but works)
        pad = np.pad(gray, 1, mode="edge")
        denoised = np.zeros_like(gray)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                denoised += pad[1 + dy:1 + dy + gray.shape[0], 1 + dx:1 + dx + gray.shape[1]]
        denoised /= 9.0

    residual = np.abs(gray - denoised)

    # Block-wise std on a coarse grid (faster + smoother). Block ~ 32x32.
    h, w = residual.shape
    B = max(16, min(48, min(h, w) // 24))
    nh, nw = h // B, w // B
    if nh < 4 or nw < 4:
        return {"score": 0.0, "region": "none", "overlay_b64": None, "heterogeneity": 0.0}

    block = residual[:nh * B, :nw * B].reshape(nh, B, nw, B).std(axis=(1, 3))
    bmin, bmax = float(block.min()), float(block.max())
    if bmax - bmin < 1e-6:
        return {"score": 0.0, "region": "none", "overlay_b64": None, "heterogeneity": 0.0}
    norm_block = (block - bmin) / (bmax - bmin)

    # Heterogeneity score: a uniform-noise image has low std-of-block-std; a spliced one has a
    # bright patch standing out. Compute the *gap* between the brightest 5% of blocks and the
    # median — large gap = likely splice. Combine with how compact the bright zone is.
    flat = norm_block.flatten()
    p95 = float(np.percentile(flat, 95))
    median = float(np.percentile(flat, 50))
    gap = p95 - median  # 0..1

    bright = norm_block > 0.7
    bright_frac = float(bright.mean())
    if bright_frac <= 1e-4:
        score = 0.0
        region = "none"
    else:
        ys, xs = np.where(bright)
        bb = ((ys.max() - ys.min() + 1) * (xs.max() - xs.min() + 1)) / float(nh * nw)
        compact = max(0.0, 1.0 - bb / 0.50)
        # localised bright patch in an otherwise uniform field
        score = float(np.clip(0.55 * gap + 0.25 * compact + 0.20 * max(0.0, 0.30 - bright_frac) / 0.30, 0.0, 1.0))
        if bright_frac > 0.30:
            score = min(score, 0.30)
        cy = float(ys.mean()) / nh
        cx = float(xs.mean()) / nw
        region = _region_name(cy, cx) if score >= 0.4 else "none"

    # Upscale the block map to image size + colourise (purple→yellow, distinct from ELA's red)
    if cv2 is not None:
        upmap = cv2.resize(norm_block, (w, h), interpolation=cv2.INTER_CUBIC)
    else:
        upmap = np.kron(norm_block, np.ones((B, B), dtype=np.float32))
        upmap = upmap[:h, :w]
    g = np.clip(upmap, 0, 1)
    r_ch = np.clip(0.30 + g * 0.70, 0, 1)
    g_ch = np.clip(0.10 + g * 0.85, 0, 1)
    b_ch = np.clip(0.55 - g * 0.55, 0, 1)
    heat = (np.stack([r_ch, g_ch, b_ch], axis=2) * 255).astype(np.uint8)
    base = np.asarray(rgb).astype(np.float32)
    over = (0.45 * base + 0.55 * heat.astype(np.float32)).clip(0, 255).astype(np.uint8)

    return {
        "score": round(float(score), 3),
        "region": region,
        "overlay_b64": _b64_png(Image.fromarray(over, "RGB")),
        "heterogeneity": round(float(gap), 3),
    }


# ────────────────────────────────────────────────────────────────────────────
# 3. JPEG ghost
# ────────────────────────────────────────────────────────────────────────────
def jpeg_ghost(pil_image):
    """Detect a "JPEG ghost" — a sub-region whose error drops sharply at one specific re-save
    quality, hinting at a paste from a differently-compressed source.

    Returns {score, best_quality, drop} — no overlay (this technique is summarised numerically).
    """
    import numpy as np
    from PIL import Image

    rgb = pil_image.convert("RGB")
    rgb.thumbnail((768, 768))
    base = np.asarray(rgb).astype(np.float32)

    errors_per_quality = []
    for q in _GHOST_QUALITIES:
        buf = _io.BytesIO()
        rgb.save(buf, format="JPEG", quality=q)
        buf.seek(0)
        re = np.asarray(Image.open(buf).convert("RGB")).astype(np.float32)
        err = ((base - re) ** 2).mean(axis=2)  # H×W
        # Coarse-grid average
        h, w = err.shape
        B = max(8, min(32, min(h, w) // 24))
        nh, nw = h // B, w // B
        if nh < 4 or nw < 4:
            continue
        block = err[:nh * B, :nw * B].reshape(nh, B, nw, B).mean(axis=(1, 3))
        errors_per_quality.append((q, block))

    if not errors_per_quality:
        return {"score": 0.0, "best_quality": None, "drop": 0.0}

    # For each block, the quality that minimises error. If a coherent sub-region picks a
    # quality different from the global majority, that's a ghost.
    stacked = np.stack([e for _, e in errors_per_quality], axis=0)   # K×nh×nw
    qualities = np.array([q for q, _ in errors_per_quality])
    best_idx = stacked.argmin(axis=0)                                # nh×nw
    # majority vote
    global_q = int(np.bincount(best_idx.flatten()).argmax())
    minority_mask = (best_idx != global_q)
    minority_frac = float(minority_mask.mean())

    if minority_frac < 0.05 or minority_frac > 0.45:
        # too clean (no ghost) or too noisy (just compression noise)
        return {"score": 0.0, "best_quality": int(qualities[global_q]), "drop": 0.0}

    # How much do the minority blocks prefer their quality over the global one?
    ys, xs = np.where(minority_mask)
    err_at_global = stacked[global_q][ys, xs]
    err_at_chosen = stacked[best_idx[ys, xs], ys, xs]
    drop = float(np.clip((err_at_global - err_at_chosen).mean() / (err_at_global.mean() + 1e-6), 0, 1))

    # Score: combine drop magnitude and how compact the minority region is
    bb = ((ys.max() - ys.min() + 1) * (xs.max() - xs.min() + 1)) / float(best_idx.size)
    compact = max(0.0, 1.0 - bb / 0.45)
    score = float(np.clip(0.65 * drop + 0.35 * compact, 0.0, 1.0))
    if minority_frac > 0.30:
        score = min(score, 0.40)

    return {
        "score": round(score, 3),
        "best_quality": int(qualities[global_q]),
        "drop": round(drop, 3),
    }


# ────────────────────────────────────────────────────────────────────────────
# Synthesis — combine the 3 signals into a single verdict
# ────────────────────────────────────────────────────────────────────────────
# Conservative thresholds, tuned to avoid flagging clean photos as tampered.
# We require *agreement* (≥2 out of 3 signals firing) or one strong signal (≥0.70).
THRESHOLD_AUTHENTIC = 0.35
THRESHOLD_FAKE = 0.55


def synthesize(ela_res: dict, noise_res: dict, ghost_res: dict) -> dict:
    """Combine three forensic scores into {verdict, edit_type, fake_prob, region, clues}."""
    se = float(ela_res.get("score", 0.0))
    sn = float(noise_res.get("score", 0.0))
    sg = float(ghost_res.get("score", 0.0))

    # Weighted fusion (ELA is the most reliable in general)
    fused = 0.45 * se + 0.30 * sn + 0.25 * sg

    # Agreement bonus: ≥2 signals over 0.40 → boost
    firing = sum(1 for s in (se, sn, sg) if s >= 0.40)
    if firing >= 2:
        fused = min(1.0, fused + 0.10)

    clues = []
    if se >= 0.40:
        clues.append(f"ELA shows a compact bright patch ({int(se*100)}% suspicious)")
    if sn >= 0.40:
        clues.append(f"noise floor is heterogeneous in one region ({int(sn*100)}%)")
    if sg >= 0.40:
        d = ghost_res.get("drop", 0.0)
        clues.append(f"JPEG ghost detected (compression mismatch, error drop {int(d*100)}%)")
    if fused < THRESHOLD_AUTHENTIC and not clues:
        clues.append("no compression, noise or ghost artifact stands out")

    # Verdict
    if fused < THRESHOLD_AUTHENTIC:
        verdict = "AUTHENTIC"
        edit_type = "none"
    elif fused < THRESHOLD_FAKE:
        # mid-zone: only call it fake if at least 2 signals agree
        if firing >= 2:
            verdict, edit_type = "FAKE", _classify_edit(ela_res, noise_res, ghost_res)
        else:
            verdict, edit_type = "AUTHENTIC", "none"
            clues.append("signals are weak and don't agree — not enough evidence to flag")
    else:
        verdict, edit_type = "FAKE", _classify_edit(ela_res, noise_res, ghost_res)

    # Best region from whichever signal localised it
    region = "none"
    for r in (ela_res.get("region"), noise_res.get("region")):
        if r and r != "none":
            region = r
            break

    fake_prob = float(fused) if verdict == "FAKE" else float(1.0 - fused)
    fake_prob = max(0.50, min(0.99, fake_prob)) if verdict == "FAKE" else max(0.50, min(0.99, fake_prob))

    return {
        "verdict": verdict,
        "edit_type": edit_type,
        "fake_prob": round(fake_prob, 3),
        "fused_score": round(float(fused), 3),
        "region": region,
        "clues": clues,
        "firing": firing,
    }


def _classify_edit(ela_res, noise_res, ghost_res) -> str:
    """Heuristic mapping forensic signals → one of the 4 standard edit types."""
    se = float(ela_res.get("score", 0.0))
    sn = float(noise_res.get("score", 0.0))
    sg = float(ghost_res.get("score", 0.0))
    # JPEG ghost + ELA agreement → classic splice
    if sg >= 0.40 and se >= 0.40:
        return "splicing"
    # Noise heterogeneous + ELA compact → inpainting or copy-move
    if sn >= 0.50 and se >= 0.30:
        return "inpainting" if ela_res.get("hot_frac", 0.0) < 0.05 else "copy_move"
    if se >= sn and se >= sg:
        return "splicing"
    if sn > se and sn > sg:
        return "inpainting"
    return "enhancement"
