"""
Pipeline io4 — Image Tampering Detection / Photoshop Forensics (Rayen).

CNN from scratch (2.15M params) trained on DF2023:
    - 4-class classification: Inpainting / Copy-move / Splicing / Enhancement
    - Pixel-level segmentation mask 256×256 (U-Net decoder)
    - Grad-CAM on enc4 (target layer from Rayen's readme)

Weights (env var):
    IO4_WEIGHTS — path to tamper_cnn.pt (state_dict)
Without weights → random init (the pipeline runs, scores are not meaningful).

Decision: if max(P) < threshold 0.50 → AUTHENTIC, otherwise FAKE — class argmax.
"""
from __future__ import annotations

import base64
import io
import os
import warnings
from typing import Optional

from backend.shared.device import DEVICE

warnings.filterwarnings("ignore")

# ─── Config ─────────────────────────────────────────────────────────────────
IO4_WEIGHTS = os.environ.get("IO4_WEIGHTS", "tamper_cnn.pt")
THRESHOLD = float(os.environ.get("IO4_THRESHOLD", "0.50"))

# ESPRIT publication: verdict comes from local model-free forensics (ELA + noise residual + JPEG ghost).
# The OpenAI vision backend stays in the file for the chatbot but is not called from analyze_image
# unless IO4_USE_OPENAI=on is set.
USE_OPENAI = os.environ.get("IO4_USE_OPENAI", "off").strip().lower() in {"on", "1", "true", "yes"}

CLASSES = ["Inpainting", "Copy-move", "Splicing", "Enhancement"]
CLASS_CODES = ["I", "C", "S", "E"]
CLASS_KEYS = ["inpainting", "copy_move", "splicing", "enhancement"]
CLASS_DESCRIPTIONS = {
    "Inpainting":  "A region was filled in algorithmically to remove or replace content",
    "Copy-move":   "Part of the image was duplicated and pasted to another location",
    "Splicing":    "Content from another image was inserted",
    "Enhancement": "Global or local adjustments (brightness, contrast, blur) that hide a prior edit",
}

# ─── Lazy heavy deps ────────────────────────────────────────────────────────
np = cv2 = torch = nn = F = Image = plt = None
_HEAVY_DEPS_LOADED = False


def _ensure_heavy_deps():
    global np, cv2, torch, nn, F, Image, plt, _HEAVY_DEPS_LOADED
    if _HEAVY_DEPS_LOADED:
        return
    try:
        import numpy as _np
        import cv2 as _cv2
        import torch as _torch
        import torch.nn as _nn
        import torch.nn.functional as _F
        from PIL import Image as _Image
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as _plt
    except ImportError as e:
        raise RuntimeError(
            f"Module io4 — missing ML dependencies ({e}). "
            "Install: pip install -r backend/requirements.txt"
        ) from e
    np, cv2, torch, nn, F, Image, plt = _np, _cv2, _torch, _nn, _F, _Image, _plt
    _HEAVY_DEPS_LOADED = True


# ─── Globals populated by init() ────────────────────────────────────────────
_model = None
_transform = None
LOADED = False
INFO: dict = {}


# ============================================================================
# Architecture — exact copy of cell 8 from rayen's notebook
# ============================================================================
def _build_model_classes():
    """Lazily-defined classes that need torch.nn — return the model class."""
    class DoubleConv(nn.Module):
        def __init__(self, in_c, out_c):
            super().__init__()
            self.block = nn.Sequential(
                nn.Conv2d(in_c, out_c, kernel_size=3, padding=1, bias=False),
                nn.BatchNorm2d(out_c),
                nn.ReLU(inplace=True),
                nn.Conv2d(out_c, out_c, kernel_size=3, padding=1, bias=False),
                nn.BatchNorm2d(out_c),
                nn.ReLU(inplace=True),
            )

        def forward(self, x):
            return self.block(x)

    class CNNFromScratch(nn.Module):
        def __init__(self, num_classes=4, dropout=0.3):
            super().__init__()
            # Encoder
            self.enc1 = DoubleConv(3,   32)
            self.enc2 = DoubleConv(32,  64)
            self.enc3 = DoubleConv(64,  128)
            self.enc4 = DoubleConv(128, 256)
            self.pool = nn.MaxPool2d(2)
            # Decoder
            self.up   = nn.Upsample(scale_factor=2, mode="bilinear", align_corners=False)
            self.dec4 = DoubleConv(256 + 256, 128)
            self.dec3 = DoubleConv(128 + 128, 64)
            self.dec2 = DoubleConv(64 + 64,   32)
            self.dec1 = DoubleConv(32 + 32,   16)
            self.final_conv = nn.Conv2d(16, 1, kernel_size=1)
            # Classification head (on bottleneck 256x16x16)
            self.cls_head = nn.Sequential(
                nn.AdaptiveAvgPool2d(1),
                nn.Flatten(),
                nn.Dropout(dropout),
                nn.Linear(256, num_classes),
            )

        def forward(self, x):
            s1 = self.enc1(x)
            s2 = self.enc2(self.pool(s1))
            s3 = self.enc3(self.pool(s2))
            s4 = self.enc4(self.pool(s3))
            b  = self.pool(s4)

            cls_logits = self.cls_head(b)

            d = self.up(b)
            d = self.dec4(torch.cat([d, s4], dim=1))
            d = self.up(d)
            d = self.dec3(torch.cat([d, s3], dim=1))
            d = self.up(d)
            d = self.dec2(torch.cat([d, s2], dim=1))
            d = self.up(d)
            d = self.dec1(torch.cat([d, s1], dim=1))
            mask_logits = self.final_conv(d)
            return mask_logits, cls_logits

    return CNNFromScratch


# ============================================================================
# INIT
# ============================================================================
def init() -> dict:
    global _model, _transform, LOADED, INFO
    if LOADED:
        return INFO

    _ensure_heavy_deps()
    print(f"[io4] Device: {DEVICE}")
    print(f"[io4] Building CNNFromScratch (2.15M params)…")

    CNNFromScratch = _build_model_classes()
    _model = CNNFromScratch(num_classes=4)

    weight_status = "random init (no weights)"
    if os.path.exists(IO4_WEIGHTS):
        try:
            state = torch.load(IO4_WEIGHTS, map_location=DEVICE)
            if isinstance(state, dict):
                if "state_dict" in state: state = state["state_dict"]
                elif "model_state_dict" in state: state = state["model_state_dict"]
                state = {k.replace("module.", ""): v for k, v in state.items()}
            missing, unexpected = _model.load_state_dict(state, strict=False)
            weight_status = f"loaded from {IO4_WEIGHTS} ({len(missing)} missing, {len(unexpected)} unexpected)"
            print(f"[io4]   → {weight_status}")
        except Exception as e:
            weight_status = f"load error ({type(e).__name__}: {e})"
            print(f"[io4]   ⚠️  {weight_status}")
    else:
        print(f"[io4]   → {weight_status} (set IO4_WEIGHTS=path/to/tamper_cnn.pt)")

    _model = _model.to(DEVICE).eval()

    # Count params
    total = sum(p.numel() for p in _model.parameters())

    # ImageNet stats per readme
    from torchvision import transforms
    _transform = transforms.Compose([
        transforms.Resize((256, 256)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])

    if USE_OPENAI:
        try:
            from . import openai_vision as _ov
            _vb = f"OpenAI · {_ov.model_name()}" if _ov.available() else "local forensics (ELA + noise + JPEG ghost)"
        except Exception:
            _vb = "local forensics (ELA + noise + JPEG ghost)"
    else:
        _vb = "local forensics (ELA + noise residual + JPEG ghost)"
    INFO = {
        "device": DEVICE,
        "verdict_backend": _vb,
        "model": "CNN From Scratch (U-Net + classification head)",
        "params_M": round(total / 1e6, 2),
        "input_resolution": "256x256",
        "classes": CLASSES,
        "weights": weight_status,
        "threshold": THRESHOLD,
    }
    LOADED = True
    print(f"[io4] ✅ Pipeline io4 ready — {total/1e6:.2f}M params on {DEVICE}\n")
    return INFO


# ============================================================================
# INFERENCE
# ============================================================================
def _forward(pil_image):
    """Returns (mask_logits, cls_logits) as torch tensors."""
    x = _transform(pil_image.convert("RGB")).unsqueeze(0).to(DEVICE)
    with torch.no_grad():
        mask_logits, cls_logits = _model(x)
    return mask_logits, cls_logits, x


def _softmax_probs(cls_logits):
    return F.softmax(cls_logits, dim=-1)[0].cpu().numpy()


def _sigmoid_mask(mask_logits):
    """Returns float mask in [0,1] of shape (256, 256)."""
    return torch.sigmoid(mask_logits)[0, 0].cpu().numpy()


# ============================================================================
# GRAD-CAM
# ============================================================================
class _GradCAM:
    """Re-implements Rayen's GradCAM (cell 22)."""
    def __init__(self, model, target_module):
        self.model = model
        self.activations = None
        self.gradients = None
        self.h_fwd = target_module.register_forward_hook(self._fwd_hook)
        self.h_bwd = target_module.register_full_backward_hook(self._bwd_hook)

    def _fwd_hook(self, module, inp, out):
        self.activations = out.detach()

    def _bwd_hook(self, module, grad_in, grad_out):
        self.gradients = grad_out[0].detach()

    def remove(self):
        self.h_fwd.remove()
        self.h_bwd.remove()

    def __call__(self, x, class_idx):
        self.model.eval()
        self.model.zero_grad()
        _, logits = self.model(x)
        score = logits[0, class_idx]
        score.backward()
        weights = self.gradients.mean(dim=(2, 3), keepdim=True)
        cam = F.relu((weights * self.activations).sum(dim=1, keepdim=True))
        cam = F.interpolate(cam, size=x.shape[-2:], mode="bilinear", align_corners=False)
        cam_min = cam.amin(dim=(2, 3), keepdim=True)
        cam_max = cam.amax(dim=(2, 3), keepdim=True)
        cam = (cam - cam_min) / (cam_max - cam_min + 1e-8)
        return cam[0, 0].cpu().numpy()


def gradcam_at_enc4(pil_image, class_idx: int) -> "np.ndarray":
    """Compute Grad-CAM at enc4 for the given predicted class."""
    x = _transform(pil_image.convert("RGB")).unsqueeze(0).to(DEVICE)
    x.requires_grad_(True)
    cam_engine = _GradCAM(_model, _model.enc4)
    try:
        cam = cam_engine(x, class_idx)
    finally:
        cam_engine.remove()
    return cam  # 256x256 in [0,1]


# ============================================================================
# RENDER OVERLAYS — base64 PNGs
# ============================================================================
def _fig_to_b64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, bbox_inches="tight", pad_inches=0.1)
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("ascii")


def _render_mask_overlay(pil_image, mask: "np.ndarray", alpha: float = 0.45) -> str:
    """Red-tinted overlay on tampered pixels (mask > 0.5)."""
    img_np = np.array(pil_image.convert("RGB").resize((256, 256)))
    binary = (mask > 0.5).astype(np.uint8)
    red = np.zeros_like(img_np)
    red[..., 0] = 220  # R = red
    overlay = img_np.copy().astype(np.float32)
    mask_3 = np.stack([binary] * 3, axis=-1)
    overlay = np.where(mask_3, (1 - alpha) * overlay + alpha * red, overlay)
    overlay = overlay.astype(np.uint8)
    fig, ax = plt.subplots(figsize=(5.5, 5.5))
    ax.imshow(overlay); ax.axis("off")
    fig.subplots_adjust(0, 0, 1, 1)
    return _fig_to_b64(fig)


def _render_gradcam_overlay(pil_image, cam: "np.ndarray", alpha: float = 0.5) -> str:
    """Grad-CAM with jet colormap overlay."""
    img_np = np.array(pil_image.convert("RGB").resize((256, 256)))
    cam_8 = (cam * 255).clip(0, 255).astype(np.uint8)
    heatmap = cv2.applyColorMap(cam_8, cv2.COLORMAP_JET)
    heatmap = cv2.cvtColor(heatmap, cv2.COLOR_BGR2RGB)
    overlay = ((1 - alpha) * img_np + alpha * heatmap).astype(np.uint8)
    fig, ax = plt.subplots(figsize=(5.5, 5.5))
    ax.imshow(overlay); ax.axis("off")
    fig.subplots_adjust(0, 0, 1, 1)
    return _fig_to_b64(fig)


def _render_gradcam_pure(cam: "np.ndarray") -> str:
    """Pure Grad-CAM heatmap (no image, just colormap)."""
    fig, ax = plt.subplots(figsize=(5.5, 5.5))
    ax.imshow(cam, cmap="jet", vmin=0, vmax=1); ax.axis("off")
    fig.subplots_adjust(0, 0, 1, 1)
    return _fig_to_b64(fig)


# ============================================================================
# PIPELINE — public entry point
# ============================================================================
_EDIT_TO_IDX = {"inpainting": 0, "copy_move": 1, "splicing": 2, "enhancement": 3, "other": 2}


def _result_from_forensics(pil_image, synth: dict, ela_res: dict, noise_res: dict, ghost_res: dict) -> dict:
    """Build the standard io4 result dict from the local forensics fusion (ELA + noise + JPEG ghost)."""
    is_fake = synth["verdict"] == "FAKE"
    edit_type = synth.get("edit_type", "none")
    fake_prob = float(synth.get("fake_prob", 0.5))
    pct = int(round(fake_prob * 100))
    region = synth.get("region", "none")
    clues = synth.get("clues", [])
    fused = float(synth.get("fused_score", 0.0))

    idx = _EDIT_TO_IDX.get(edit_type, 2)
    if is_fake:
        class_probs = {k: round((1.0 - fake_prob) / 3.0, 4) for k in CLASS_KEYS}
        class_probs[CLASS_KEYS[idx]] = round(fake_prob, 4)
        verdict_label = f"Manipulation detected: {CLASSES[idx]}"
        verdict_class = CLASSES[idx]
    else:
        class_probs = {k: round(0.25, 4) for k in CLASS_KEYS}
        verdict_label = "No local manipulation detected — appears to be an unedited photo"
        verdict_class = None

    explanation_parts = []
    if is_fake:
        explanation_parts.append(
            f"The local forensic analysis combined three model-free techniques (ELA, noise residual, JPEG ghost) "
            f"and reached a {pct}% suspicion score, above the {int(_forensics_threshold_fake()*100)}% threshold."
        )
        if region and region != "none":
            explanation_parts.append(f"The most suspicious area sits in the {region} of the frame.")
        explanation_parts.append("Clues: " + "; ".join(clues) + ".")
    else:
        explanation_parts.append(
            "The local forensic analysis (ELA, noise residual, JPEG ghost) found no consistent compression, "
            "noise or ghosting artifact in this image — it looks like an unedited photo."
        )
        if clues:
            explanation_parts.append("Observation: " + "; ".join(clues) + ".")
    explanation = " ".join(explanation_parts)

    # Build XAI from the forensic overlays
    xai = {}
    if ela_res and ela_res.get("overlay_b64"):
        xai["tamper_mask_overlay"] = ela_res["overlay_b64"]   # ELA overlay → "tampered regions" view
        xai["ela_overlay"] = ela_res["overlay_b64"]
        xai["ela_score"] = float(ela_res.get("score", 0.0))
    if noise_res and noise_res.get("overlay_b64"):
        xai["gradcam_overlay"] = noise_res["overlay_b64"]     # Noise-variance map → "where the signal disagrees" view
        xai["noise_overlay"] = noise_res["overlay_b64"]
        xai["noise_score"] = float(noise_res.get("score", 0.0))
    if ghost_res:
        xai["jpeg_ghost_score"] = float(ghost_res.get("score", 0.0))
        if ghost_res.get("best_quality") is not None:
            xai["jpeg_ghost_quality"] = int(ghost_res["best_quality"])
    if ela_res and ela_res.get("raw_b64"):
        xai["gradcam_pure"] = ela_res["raw_b64"]              # the pure ELA heatmap

    return {
        "verdict": "FAKE" if is_fake else "AUTHENTIC",
        "verdict_class": verdict_class,
        "verdict_label": verdict_label,
        "is_synthetic": False,
        "threshold": THRESHOLD,
        "predicted_class": CLASSES[idx] if is_fake else CLASSES[idx],
        "predicted_class_code": CLASS_CODES[idx],
        "predicted_class_description": CLASS_DESCRIPTIONS[CLASSES[idx]] if is_fake else "—",
        "max_confidence": round(fake_prob if is_fake else (1.0 - fake_prob), 4),
        "class_probabilities": class_probs,
        "class_probabilities_pct": {k: round(v * 100, 2) for k, v in class_probs.items()},
        "tamper_mask_pct": round(min(60.0, fused * 100), 1) if is_fake else 0.0,
        "prob_fake": round(fake_prob if is_fake else (1.0 - fake_prob), 4),
        "region": region,
        "clues": clues,
        "ela_score": round(float(ela_res.get("score", 0.0)) if ela_res else 0.0, 3),
        "noise_score": round(float(noise_res.get("score", 0.0)) if noise_res else 0.0, 3),
        "jpeg_ghost_score": round(float(ghost_res.get("score", 0.0)) if ghost_res else 0.0, 3),
        "fused_score": round(fused, 3),
        "signals_agreement": int(synth.get("firing", 0)),
        "xai": xai,
        "image_size": {"width": pil_image.size[0], "height": pil_image.size[1]},
        "explanation": explanation,
        "explanation_source": "local_forensics",
        "model_used": "ELA + Noise residual + JPEG ghost (model-free forensics)",
    }


def _forensics_threshold_fake() -> float:
    from . import forensics as _f
    return _f.THRESHOLD_FAKE


def _result_from_openai(pil_image, o: dict, ela: Optional[dict] = None) -> dict:
    """Build the standard io4 result dict from an OpenAI-vision response (+ optional ELA second opinion)."""
    is_fake = bool(o.get("is_fake"))
    is_synthetic = bool(o.get("is_synthetic"))
    et = o.get("edit_type") or ("other" if (is_fake and not is_synthetic) else "none")
    conf = int(o.get("confidence_pct", 75))
    reason = (o.get("reason") or "").strip()
    clues = [str(c).strip() for c in (o.get("clues") or []) if str(c).strip()][:6]
    region = (o.get("region") or "none")
    source = "openai"

    # ELA (Error-Level Analysis) — kept as a *visual exhibit only*, NOT an automatic verdict.
    # Rationale: ELA naturally lights up any sharp/detailed region (faces, edges, the in-focus
    # subject), so an automated "bright blob ⇒ tampered" rule produces constant false positives.
    # We surface the map for a human to read; the verdict stays with the vision model. If GPT-4o
    # already says FAKE and ELA happens to point somewhere while GPT-4o gave no region, borrow it.
    ela_score = float(ela["score"]) if (ela and isinstance(ela.get("score"), (int, float))) else 0.0
    ela_region = (ela.get("region") if ela else "none") or "none"
    if is_fake and not is_synthetic and ela_region != "none" and region in ("none", ""):
        region = ela_region

    idx = _EDIT_TO_IDX.get(et, 2)
    p = conf / 100.0
    if is_synthetic:
        # whole-image AI/GAN picture — not a "local edit", but definitely not an authentic photo
        class_probs = {k: round(0.04, 4) for k in CLASS_KEYS}
        verdict, verdict_class = "FAKE", "AI-generated"
        verdict_label = "AI-generated / synthetic image — not a real photograph"
        pred_idx = idx
        if not clues:
            clues = ["The whole image has the look of an AI/GAN-generated picture, not a camera photo"]
    elif is_fake:
        class_probs = {k: 0.0 for k in CLASS_KEYS}
        class_probs[CLASS_KEYS[idx]] = round(p, 4)
        rem = round((1.0 - p) / 3.0, 4)
        for k in CLASS_KEYS:
            if k != CLASS_KEYS[idx]:
                class_probs[k] = rem
        verdict, verdict_class = "FAKE", CLASSES[idx]
        verdict_label = f"Manipulation detected: {CLASSES[idx]}"
        pred_idx = idx
    else:
        class_probs = {k: round(0.25, 4) for k in CLASS_KEYS}
        verdict, verdict_class = "AUTHENTIC", None
        verdict_label = "No local manipulation detected — appears to be an unedited photo"
        pred_idx = idx
    explanation = reason
    if clues:
        explanation = (reason.rstrip(" .") + ". Clues found: " + "; ".join(clues) + ".") if reason else ("Clues found: " + "; ".join(clues) + ".")
    if is_fake and not is_synthetic and region and region not in ("none", ""):
        explanation = (explanation.rstrip(" .") + f". Most suspicious area: {region}." ) if explanation else f"Most suspicious area: {region}."
    if is_synthetic:
        explanation = (explanation.rstrip(" .") + ". For a dedicated AI-image analysis, use the Fake-Media module.") if explanation \
            else "This image looks AI-generated. For a dedicated AI-image analysis, use the Fake-Media module."
    if not explanation:
        explanation = ("No sign of local editing — this looks like an unedited photo."
                       if not is_fake else "Local editing detected — see the report for the suspicious region.")

    pcd = ("The whole picture was produced by an image generator, not captured by a camera"
           if is_synthetic else CLASS_DESCRIPTIONS[CLASSES[pred_idx]])
    pc = "Synthetic" if is_synthetic else CLASSES[pred_idx]
    pcc = "G" if is_synthetic else CLASS_CODES[pred_idx]

    xai = {}
    if ela:
        # always expose the ELA map — it doubles as the "what the analysis shows" visual
        xai = {"tamper_mask_overlay": ela.get("overlay_b64"), "gradcam_overlay": ela.get("raw_b64"),
               "ela_overlay": ela.get("overlay_b64"), "ela_score": round(ela_score, 3)}
        xai = {k: v for k, v in xai.items() if v}

    return {
        "verdict": verdict,
        "verdict_class": verdict_class,
        "verdict_label": verdict_label,
        "is_synthetic": is_synthetic,
        "threshold": THRESHOLD,
        "predicted_class": pc,
        "predicted_class_code": pcc,
        "predicted_class_description": pcd,
        "max_confidence": round(p, 4),
        "class_probabilities": class_probs,
        "class_probabilities_pct": {k: round(v * 100, 2) for k, v in class_probs.items()},
        "tamper_mask_pct": (0.0 if is_synthetic else (round(min(60.0, max(conf * 0.35, ela_score * 25)), 1) if is_fake else 0.0)),
        "prob_fake": round(p if is_fake else (1.0 - p), 4),
        "region": region,
        "clues": clues,
        "ela_score": round(ela_score, 3),
        "xai": xai,
        "image_size": {"width": pil_image.size[0], "height": pil_image.size[1]},
        "explanation": explanation,
        "explanation_source": source,
        "model_used": (f"OpenAI · {o.get('model', 'gpt-4o')}" + (" + ELA" if ela else "")),
    }


def analyze_image(pil_image) -> dict:
    # 1) Primary: local model-free forensics (ELA + noise residual + JPEG ghost). 100% offline,
    #    no trained weights required — gives a real verdict on splicing / inpainting / copy-move.
    try:
        from . import forensics as _forensics
        ela_res = _forensics.ela(pil_image)
        noise_res = _forensics.noise_residual(pil_image)
        ghost_res = _forensics.jpeg_ghost(pil_image)
        synth = _forensics.synthesize(ela_res, noise_res, ghost_res)
        return _result_from_forensics(pil_image, synth, ela_res, noise_res, ghost_res)
    except Exception as e:
        print(f"[io4] local forensics failed ({type(e).__name__}: {e}) — falling back to next backend")

    # 2) Optional: OpenAI vision (off by default — kept for the chatbot).
    if USE_OPENAI:
        try:
            from . import openai_vision as ov
            o = ov.analyze(pil_image) if ov.available() else None
        except Exception as e:
            print(f"[io4] OpenAI vision unavailable, falling back to the local CNN: {e}")
            o = None
        if o is not None:
            ela_res = None
            try:
                from . import ela as _ela_mod
                ela_res = _ela_mod.analyze(pil_image)
            except Exception as e:
                print(f"[io4] ELA unavailable: {e}")
                ela_res = None
            return _result_from_openai(pil_image, o, ela_res)

    # 3) Last-resort: local CNN (untrained without IO4_WEIGHTS — flagged in the explanation).
    init()

    # Forward
    mask_logits, cls_logits, _x = _forward(pil_image)
    probs = _softmax_probs(cls_logits)
    pred_idx = int(probs.argmax())
    max_conf = float(probs.max())

    # Apply threshold logic (per readme)
    if max_conf < THRESHOLD:
        verdict = "AUTHENTIC"
        verdict_class = None
        verdict_label = "No manipulation detected — uncertain distribution"
    else:
        verdict = "FAKE"
        verdict_class = CLASSES[pred_idx]
        verdict_label = f"Manipulation detected: {CLASSES[pred_idx]}"

    # Mask
    mask = _sigmoid_mask(mask_logits)
    mask_pct_tampered = round(float((mask > 0.5).mean()) * 100, 2)

    # Grad-CAM at enc4 (always run, even for AUTHENTIC — shows what model considered)
    cam = gradcam_at_enc4(pil_image, pred_idx)

    # Render overlays
    mask_overlay = _render_mask_overlay(pil_image, mask)
    gradcam_overlay = _render_gradcam_overlay(pil_image, cam)
    gradcam_pure = _render_gradcam_pure(cam)

    # Build class_probabilities dict
    class_probs = {
        CLASS_KEYS[i]: round(float(probs[i]), 4)
        for i in range(4)
    }

    untrained = not os.path.exists(IO4_WEIGHTS)
    res = {
        "verdict": verdict,
        "verdict_class": verdict_class,
        "verdict_label": verdict_label,
        "threshold": THRESHOLD,
        "predicted_class": CLASSES[pred_idx],
        "predicted_class_code": CLASS_CODES[pred_idx],
        "predicted_class_description": CLASS_DESCRIPTIONS[CLASSES[pred_idx]],
        "max_confidence": round(max_conf, 4),
        "class_probabilities": class_probs,
        "class_probabilities_pct": {k: round(v * 100, 2) for k, v in class_probs.items()},
        "tamper_mask_pct": mask_pct_tampered,
        "xai": {
            "tamper_mask_overlay": mask_overlay,
            "gradcam_overlay": gradcam_overlay,
            "gradcam_pure": gradcam_pure,
        },
        "image_size": {"width": pil_image.size[0], "height": pil_image.size[1]},
        "explanation_source": "local_untrained" if untrained else "local",
    }
    if untrained:
        res["explanation"] = ("⚠️ Heuristic fallback only — no trained tampering model is installed "
                              "(set IO4_WEIGHTS) and the OpenAI-vision detector is not configured, so this "
                              "verdict is not reliable.")
    return res


# ============================================================================
# COMPARE MODE — pixel diff between an original and a suspect copy
# ============================================================================
def _region_name_xy(cy: float, cx: float) -> str:
    v = "top" if cy < 1 / 3 else ("middle" if cy < 2 / 3 else "bottom")
    h = "left" if cx < 1 / 3 else ("center" if cx < 2 / 3 else "right")
    return f"{v} {h}"


def compare_images(pil_reference, pil_suspect) -> dict:
    """Diff a *suspect* image against a known *reference/original*.

    This is the only reliable way to localise a clean local edit (an object erased, a face feature
    changed) — the kind of thing no single-image detector can see. We resize the reference onto the
    suspect's geometry, take the per-pixel difference, and report what changed and where.
    """
    try:
        import numpy as _np
        from PIL import Image as _PIL
    except Exception as e:  # pragma: no cover
        raise RuntimeError(f"compare mode needs numpy + Pillow ({e})")

    ref = pil_reference.convert("RGB")
    sus = pil_suspect.convert("RGB")
    # cap size for speed; the suspect's geometry is the canvas we judge on
    sus.thumbnail((1400, 1400))
    if ref.size != sus.size:
        ref = ref.resize(sus.size, _PIL.BILINEAR)
    a = _np.asarray(ref).astype(_np.int16)
    b = _np.asarray(sus).astype(_np.int16)
    diff = _np.abs(a - b).max(axis=2).astype(_np.uint8)            # H×W, 0..255
    H, W = diff.shape
    npx = float(H * W)

    soft = diff > 12     # any visible change (above re-compression noise)
    hard = diff > 40     # a substantial change
    soft_frac = float(soft.mean())
    hard_frac = float(hard.mean())
    changed_pct = round(soft_frac * 100, 2)

    sel = hard if hard.any() else (soft if soft.any() else None)
    if sel is not None:
        ys, xs = _np.where(sel)
        bb = ((ys.max() - ys.min() + 1) * (xs.max() - xs.min() + 1)) / npx
        region = _region_name_xy(float(ys.mean()) / H, float(xs.mean()) / W)
    else:
        bb, region = 0.0, "none"

    # Verdict
    if soft_frac < 0.0008:
        verdict, edit_type = "AUTHENTIC", "none"
        verdict_label = "Identical to the original — no modification found."
        verdict_class = None
        explanation = ("Pixel-for-pixel, the submitted image matches the reference (only negligible "
                       "re-compression noise). Nothing was edited.")
        clues = []
        conf = 0.99
    elif bb <= 0.55 and soft_frac < 0.25:
        verdict, edit_type = "FAKE", "splicing"
        verdict_class = "Splicing"
        verdict_label = f"Local modification vs the original — in the {region}"
        explanation = (f"Compared with the original, {changed_pct}% of the pixels changed, concentrated in the "
                       f"{region} of the frame. That is the signature of a local edit (an object added/removed "
                       "or a region painted over).")
        clues = [f"{changed_pct}% of pixels differ from the original",
                 f"the changes form a compact patch in the {region}"]
        conf = 0.99
    else:
        verdict, edit_type = "FAKE", "enhancement"
        verdict_class = "Enhancement"
        verdict_label = "Differs widely from the original — global re-processing or a different image."
        explanation = (f"About {changed_pct}% of the pixels differ from the reference and the change is spread "
                       "across the whole frame — this is global re-processing (a filter, a heavy re-compression, "
                       "a resize) or simply a different picture, not a single local edit.")
        clues = [f"{changed_pct}% of pixels differ from the original", "the change covers most of the frame"]
        conf = 0.9

    is_fake = (verdict == "FAKE")

    # Overlays: (1) the suspect with changed pixels lit in magenta, (2) the raw amplified diff map
    base = _np.asarray(sus).astype(_np.float32)
    hl = base.copy()
    m = soft
    accent = _np.array([255.0, 40.0, 210.0])
    hl[m] = 0.30 * hl[m] + 0.70 * accent
    over_img = _PIL.fromarray(hl.clip(0, 255).astype(_np.uint8), "RGB")
    amp = _np.clip(diff.astype(_np.float32) * 3.2, 0, 255).astype(_np.uint8)
    diff_img = _PIL.fromarray(_np.stack([amp, amp, amp], axis=2), "RGB")

    def _b64(im):
        bf = io.BytesIO(); im.save(bf, format="PNG"); return base64.b64encode(bf.getvalue()).decode("ascii")

    idx = _EDIT_TO_IDX.get(edit_type, 2)
    if is_fake:
        class_probs = {k: round((1.0 - conf) / 3.0, 4) for k in CLASS_KEYS}
        class_probs[CLASS_KEYS[idx]] = round(conf, 4)
        pred_idx = idx
    else:
        class_probs = {k: 0.25 for k in CLASS_KEYS}
        pred_idx = idx

    return {
        "mode": "compare",
        "verdict": verdict,
        "verdict_class": verdict_class,
        "verdict_label": verdict_label,
        "threshold": THRESHOLD,
        "predicted_class": (CLASSES[pred_idx] if is_fake else CLASSES[pred_idx]),
        "predicted_class_code": CLASS_CODES[pred_idx],
        "predicted_class_description": (CLASS_DESCRIPTIONS[CLASSES[pred_idx]] if is_fake else "—"),
        "max_confidence": round(conf, 4),
        "class_probabilities": class_probs,
        "class_probabilities_pct": {k: round(v * 100, 2) for k, v in class_probs.items()},
        "tamper_mask_pct": changed_pct if is_fake else 0.0,
        "changed_pct": changed_pct,
        "prob_fake": round(conf if is_fake else (1.0 - conf), 4),
        "region": region,
        "clues": clues,
        "xai": {"tamper_mask_overlay": _b64(over_img), "gradcam_overlay": _b64(diff_img),
                "diff_overlay": _b64(over_img)},
        "image_size": {"width": sus.size[0], "height": sus.size[1]},
        "explanation": explanation,
        "explanation_source": "compare",
        "model_used": "Pixel comparison vs the original image",
    }
