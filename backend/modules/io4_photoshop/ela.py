"""Error-Level Analysis (ELA) — a classic, model-free image-tampering heuristic for io4.

Idea: re-save the image as JPEG at a known quality, subtract it from the original, and amplify.
A region that was pasted from another (already-compressed) source, or re-saved a different number
of times than the rest of the frame, lights up brighter than its surroundings. We turn that into
(a) a heatmap overlay, (b) a "localised-anomaly" score in [0, 1].

Pure Pillow + NumPy — no model download. Returns None if Pillow/NumPy aren't importable.

Caveat (told to the user too): ELA only sees an edit that left a *compression* trace. An edit that
was re-exported once, uniformly, as a lossless PNG leaves nothing for ELA to find — that case is
not detectable from the pixels alone without the original file to diff against.

Env:
    IO4_ELA_QUALITY     JPEG quality used for the re-save probe (default 90)
    IO4_ELA_THRESHOLD   anomaly score above which io4 escalates to FAKE (default 0.62)
"""
from __future__ import annotations

import base64
import io
import os

_QUALITY = int(os.environ.get("IO4_ELA_QUALITY", "90"))
_THRESHOLD = float(os.environ.get("IO4_ELA_THRESHOLD", "0.62"))


def threshold() -> float:
    return _THRESHOLD


def _region_name(cy: float, cx: float) -> str:
    v = "top" if cy < 1 / 3 else ("middle" if cy < 2 / 3 else "bottom")
    h = "left" if cx < 1 / 3 else ("center" if cx < 2 / 3 else "right")
    return f"{v} {h}"


def analyze(pil_image):
    """Return {score, region, overlay_b64, raw_b64} or None if deps/inputs are unusable."""
    try:
        import numpy as np
        from PIL import Image, ImageChops
    except Exception:
        return None
    try:
        orig = pil_image.convert("RGB")
        # cap size — ELA is scale-insensitive enough and this keeps it fast
        orig.thumbnail((1024, 1024))
        buf = io.BytesIO()
        orig.save(buf, format="JPEG", quality=_QUALITY)
        buf.seek(0)
        resaved = Image.open(buf).convert("RGB")
        diff = ImageChops.difference(orig, resaved)
        arr = np.asarray(diff).astype(np.float32)            # H×W×3
        mag = arr.max(axis=2)                                 # H×W — per-pixel ELA magnitude
        mx = float(mag.max())
        if mx < 1e-6:
            # perfectly clean (e.g. already a fresh JPEG at this quality, or a flat image)
            scaled = np.zeros_like(mag, dtype=np.uint8)
            score = 0.0
            region = "none"
        else:
            norm = mag / mx                                   # 0..1
            scaled = (np.clip(norm * 255.0 * 2.2, 0, 255)).astype(np.uint8)  # amplify for the heatmap
            # Localised-anomaly score: is the bright energy concentrated in a small patch
            # (suspicious) or spread over the whole frame (just normal texture/edges)?
            h, w = norm.shape
            hot = norm > 0.45
            hot_frac = float(hot.mean())
            if hot_frac <= 1e-4:
                score = 0.0
                region = "none"
            else:
                ys, xs = np.where(hot)
                # tightness: bbox area of the hot pixels relative to the frame
                bb = ((ys.max() - ys.min() + 1) * (xs.max() - xs.min() + 1)) / float(h * w)
                # contrast: how much brighter the hot patch is vs the rest
                rest = norm[~hot]
                rest_mean = float(rest.mean()) if rest.size else 0.0
                hot_mean = float(norm[hot].mean())
                contrast = (hot_mean - rest_mean) / (hot_mean + 1e-6)   # 0..1
                # a real splice/inpaint: small fraction of pixels, compact bbox, high contrast
                small = max(0.0, 1.0 - hot_frac / 0.10)                 # 1 when <<10% of pixels are hot
                compact = max(0.0, 1.0 - bb / 0.45)                     # 1 when bbox is small
                score = float(np.clip(0.45 * small + 0.30 * compact + 0.25 * contrast, 0.0, 1.0))
                if hot_frac > 0.30 or bb > 0.7:
                    score = min(score, 0.25)                            # whole-frame energy → not localised
                cy = float(ys.mean()) / h
                cx = float(xs.mean()) / w
                region = _region_name(cy, cx) if score >= 0.4 else "none"

        # Build overlays
        import numpy as _np
        raw_img = Image.fromarray(scaled, mode="L").convert("RGB")
        # colourise: dark = blue, hot = yellow/red (cheap LUT without matplotlib)
        g = scaled.astype(_np.float32) / 255.0
        r_ch = _np.clip(g * 1.6, 0, 1)
        g_ch = _np.clip(g * 1.1, 0, 1)
        b_ch = _np.clip(0.35 - g * 0.35, 0, 1)
        heat = _np.stack([r_ch, g_ch, b_ch], axis=2)
        heat = (heat * 255).astype(_np.uint8)
        base = _np.asarray(orig).astype(_np.float32)
        # match sizes (orig may differ slightly after thumbnail of diff source) — they're the same here
        over = (0.45 * base + 0.55 * heat.astype(_np.float32)).clip(0, 255).astype(_np.uint8)
        overlay_img = Image.fromarray(over, mode="RGB")

        def _b64(im):
            b = io.BytesIO()
            im.save(b, format="PNG")
            return base64.b64encode(b.getvalue()).decode("ascii")

        return {
            "score": round(float(score), 3),
            "region": region,
            "overlay_b64": _b64(overlay_img),
            "raw_b64": _b64(Image.fromarray(heat, mode="RGB")),
            "quality": _QUALITY,
        }
    except Exception:
        return None
