"""
Pipeline io1 — Fake media detection (Islem).

A unified detector that automatically routes to the right model, on image OR video:

    face detected   → "deepfake" model (face swap / face manipulation)
    no face         → "AI-generated image" model (genuine shot vs fabricated image)

Models (all optional — the pipeline runs with whatever is available):
    IO1_VIDEO_WEIGHTS     ResNet50 state_dict *trained and validated* by Islem (best_ResNet50.pth)
                          (Linear head; idx 0 = FAKE, 1 = REAL)  — default backend/data/io1_resnet50.pth
                          → default detector for ALL cases (video, image with a face, image without a face)
    IO1_DEEPFAKE_WEIGHTS  ResNet50 state_dict "Model X" by Islem, still being trained
                          (Dropout+Linear head; idx 0 = REAL, 1 = DEEPFAKE) — default backend/data/io1_resnet50_deepfake.pth
                          NOT LOADED by default (over-predicts "FAKE"); enable with IO1_USE_IMAGE_DEEPFAKE=on
    IO1_AI_WEIGHTS        ResNet50 state_dict "Model Y" by Islem for "AI image vs genuine"
                          (Dropout+Linear head; idx 0 = REAL, 1 = AI) — default backend/data/io1_resnet50_ai_vs_real.pth
                          (not delivered yet → the "no face" route falls back to IO1_VIDEO_WEIGHTS)

Face detection: OpenCV Haar cascade (no extra dependency).
Grad-CAM: layer4[-1], targeted at the "fake" class → heatmap + overlay.
Explanation: geometric analysis of the heatmap by default; optional LLaVA if GPU + bitsandbytes (IO1_ENABLE_LLAVA=on).
"""
from __future__ import annotations

import base64
import io
import os
import warnings

from backend.shared.device import DEVICE

warnings.filterwarnings("ignore")

# ─── Config ─────────────────────────────────────────────────────────────────
_DATA = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "data"))

# Main model: best_ResNet50.pth (delivered here under the name io1_resnet50.pth). This is Islem's
# *trained and validated* ResNet50 (~97% accuracy, recall ~98% on the FAKE class). Class
# convention: idx 0 = FAKE, idx 1 = REAL. According to Islem's docs it covers face deepfakes
# (video AND image) as well as fully synthetic portraits (GAN / diffusion) → we use it
# as the default detector for ALL cases.
IO1_VIDEO_WEIGHTS = os.environ.get("IO1_VIDEO_WEIGHTS", os.path.join(_DATA, "io1_resnet50.pth"))

# Dedicated image deepfake detector io1_resnet50_deepfake.pth (= resnet50_deepfake.pth, Islem's
# "Model X"). Per Islem's **official** `fake_images_detection/inference.py`, this is THE model to
# use for image deepfake detection on faces (idx 0=REAL, idx 1=DEEPFAKE, Dropout+Linear head).
# The previous "still being trained, over-predicts FAKE" warning was based on an outdated build —
# we now use it by default, matching the official inference pipeline. Disable with IO1_USE_IMAGE_DEEPFAKE=off.
IO1_DEEPFAKE_WEIGHTS = os.environ.get("IO1_DEEPFAKE_WEIGHTS", os.path.join(_DATA, "io1_resnet50_deepfake.pth"))
USE_IMAGE_DEEPFAKE = os.environ.get("IO1_USE_IMAGE_DEEPFAKE", "on").strip().lower() not in {"", "0", "off", "false", "no"}

# "AI-generated image vs genuine" (Islem's "Model Y"): not delivered yet. If it ever arrives
# (io1_resnet50_ai_vs_real.pth, convention idx 0 = REAL / idx 1 = AI), we use it; otherwise we
# fall back to the trained model above (which can also recognize synthetic portraits).
_AI_DEDICATED = os.path.join(_DATA, "io1_resnet50_ai_vs_real.pth")
IO1_AI_WEIGHTS = os.environ.get("IO1_AI_WEIGHTS") or (_AI_DEDICATED if os.path.isfile(_AI_DEDICATED) else None)
ENABLE_LLAVA = os.environ.get("IO1_ENABLE_LLAVA", "off").strip().lower() not in {"", "0", "off", "false", "no"}
MAX_FRAMES_SCAN = int(os.environ.get("IO1_MAX_FRAMES", "10"))

# ESPRIT publication: the verdict must come from a 100% local model. The OpenAI vision
# backend (openai_vision.py) is kept around for the chatbot module only — it is no longer
# called from the analyze functions unless explicitly re-enabled with IO1_USE_OPENAI=on.
USE_OPENAI = os.environ.get("IO1_USE_OPENAI", "off").strip().lower() in {"on", "1", "true", "yes"}

# Decision threshold for the deepfake ensemble (best_ResNet50 + resnet50_deepfake).
# Both Islem models lean toward FAKE on some out-of-distribution real photographs (around
# p_fake≈0.55), so we raise the FAKE cut-off slightly above naive 0.50 argmax. The AI
# consensus path catches the GAN/AI imagery that this stricter ensemble cut-off may miss.
DEEPFAKE_FAKE_THRESHOLD = float(os.environ.get("IO1_DEEPFAKE_THRESHOLD", "0.60"))

_IMAGENET_MEAN = [0.485, 0.456, 0.406]
_IMAGENET_STD = [0.229, 0.224, 0.225]

# ─── Lazy heavy deps ────────────────────────────────────────────────────────
np = cv2 = torch = nn = F = Image = transforms = tv_models = None
_HEAVY_DEPS_LOADED = False


def _ensure_heavy_deps():
    global np, cv2, torch, nn, F, Image, transforms, tv_models, _HEAVY_DEPS_LOADED
    if _HEAVY_DEPS_LOADED:
        return
    try:
        import numpy as _np
        import cv2 as _cv2
        import torch as _torch
        import torch.nn as _nn
        import torch.nn.functional as _F
        from PIL import Image as _Image, ImageFile as _ImageFile
        from torchvision import transforms as _transforms
        from torchvision import models as _tv_models
        _Image.MAX_IMAGE_PIXELS = None
        _ImageFile.LOAD_TRUNCATED_IMAGES = True
    except ImportError as e:
        raise RuntimeError(
            f"Module io1 — missing ML dependencies ({e}). "
            "Install: pip install -r backend/requirements.txt"
        ) from e
    np, cv2, torch, nn, F, Image, transforms, tv_models = (
        _np, _cv2, _torch, _nn, _F, _Image, _transforms, _tv_models
    )
    _HEAVY_DEPS_LOADED = True


# ─── Globals populated by init() ────────────────────────────────────────────
# Each model bundle: {"model":..., "layer":..., "fake_idx":int, "real_idx":int, "src":str}
_M_VIDEO = None      # deepfake on video (frames)
_M_DEEPFAKE = None   # deepfake on image
_M_AI = None         # AI-generated image vs genuine
_transform = None
_face_cascades: list = []
_mtcnn = None        # facenet-pytorch MTCNN — primary face detector (matches Islem's training)
_llava = None
LOADED = False
INFO: dict = {}


# ============================================================================
def _load_resnet50(path: str):
    """Loads a ResNet50, detecting the head (plain Linear or Dropout+Linear)."""
    sd = None
    try:
        sd = torch.load(path, map_location=DEVICE)
    except Exception:
        sd = torch.load(path, map_location=DEVICE, weights_only=False)
    if isinstance(sd, dict) and "state_dict" in sd and "fc.weight" not in sd and "fc.1.weight" not in sd:
        sd = sd["state_dict"]
    m = tv_models.resnet50(weights=None)
    n_in = m.fc.in_features
    if "fc.1.weight" in sd:                       # Dropout + Linear head
        n_out = int(sd["fc.1.weight"].shape[0])
        m.fc = nn.Sequential(nn.Dropout(0.3), nn.Linear(n_in, n_out))
    elif "fc.weight" in sd:                       # plain Linear head
        n_out = int(sd["fc.weight"].shape[0])
        m.fc = nn.Linear(n_in, n_out)
    else:
        raise RuntimeError("Unexpected ResNet50 state_dict (no fc layer).")
    m.load_state_dict(sd)
    m.to(DEVICE).eval()
    return m


def _bundle(path, fake_idx, real_idx):
    if not os.path.isfile(path):
        return None
    m = _load_resnet50(path)
    return {"model": m, "layer": m.layer4[-1], "fake_idx": fake_idx, "real_idx": real_idx,
            "src": os.path.basename(path)}


def init() -> dict:
    global _M_VIDEO, _M_DEEPFAKE, _M_AI, _transform, _face_cascades, _mtcnn, _llava, LOADED, INFO
    if LOADED:
        return INFO
    _ensure_heavy_deps()

    # index conventions (cf. Islem's inference.py)
    _M_VIDEO = _bundle(IO1_VIDEO_WEIGHTS, fake_idx=0, real_idx=1)        # trained ResNet50: 0=FAKE, 1=REAL
    # Dedicated image detector: loaded only if explicitly requested (otherwise it over-predicts "FAKE").
    _M_DEEPFAKE = _bundle(IO1_DEEPFAKE_WEIGHTS, fake_idx=1, real_idx=0) if USE_IMAGE_DEEPFAKE else None
    if _M_DEEPFAKE is None:
        _M_DEEPFAKE = _M_VIDEO                                           # fallback: trained model, on the face crop
    # Dedicated "AI vs genuine" detector if present; otherwise fall back to the trained model (handles synthetic portraits).
    _M_AI = _bundle(IO1_AI_WEIGHTS, fake_idx=1, real_idx=0) if (IO1_AI_WEIGHTS and os.path.isfile(IO1_AI_WEIGHTS)) else None
    if _M_AI is None:
        _M_AI = _M_VIDEO

    _transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(_IMAGENET_MEAN, _IMAGENET_STD),
    ])

    _face_cascades = []
    for name in ("haarcascade_frontalface_default.xml", "haarcascade_frontalface_alt2.xml"):
        try:
            c = cv2.CascadeClassifier(cv2.data.haarcascades + name)
            if not c.empty():
                _face_cascades.append(c)
        except Exception:
            pass

    # MTCNN — primary face detector. Settings copied from Islem's official inference
    # (islem/fake_images_detection/inference.py): image_size=224, margin=20, post_process=False.
    # Falls back to OpenCV Haar if facenet-pytorch isn't available. This was the missing piece —
    # the ResNet50 was trained on MTCNN crops with these exact settings, so any mismatch produced
    # unreliable deepfake verdicts.
    _mtcnn = None
    try:
        from facenet_pytorch import MTCNN as _MTCNN
        _mtcnn = _MTCNN(
            image_size=224, margin=20, keep_all=False,
            post_process=False, device=DEVICE,
        )
        print("[io1] MTCNN face detector ready (facenet-pytorch, image_size=224 margin=20)")
    except Exception as e:
        print(f"[io1] MTCNN unavailable ({type(e).__name__}: {e}) — falling back to OpenCV Haar")

    llava_status = "off"
    if ENABLE_LLAVA:
        try:
            from transformers import AutoProcessor, LlavaForConditionalGeneration
            proc = AutoProcessor.from_pretrained("llava-hf/llava-1.5-7b-hf")
            kwargs = {"device_map": "auto"}
            try:
                import bitsandbytes  # noqa: F401
                if torch.cuda.is_available():
                    kwargs["load_in_4bit"] = True
            except Exception:
                pass
            vlm = LlavaForConditionalGeneration.from_pretrained("llava-hf/llava-1.5-7b-hf", **kwargs)
            _llava = (proc, vlm)
            llava_status = "llava-1.5-7b" + (" (4-bit)" if kwargs.get("load_in_4bit") else "")
        except Exception as e:
            _llava = None
            llava_status = f"unavailable ({type(e).__name__})"

    if _M_VIDEO is None and _M_DEEPFAKE is None and _M_AI is None:
        # No model → build an empty ResNet50 anyway so we don't crash
        m = tv_models.resnet50(weights=None)
        m.fc = nn.Linear(m.fc.in_features, 2)
        m.to(DEVICE).eval()
        _M_VIDEO = {"model": m, "layer": m.layer4[-1], "fake_idx": 0, "real_idx": 1, "src": "random init (no weights)"}
    # Systematic fallback to the trained model for image routing (if no dedicated model is available).
    if _M_DEEPFAKE is None:
        _M_DEEPFAKE = _M_VIDEO
    if _M_AI is None:
        _M_AI = _M_VIDEO

    LOADED = True
    _shared = _M_VIDEO["src"] if _M_VIDEO else "—"
    _df_src = _M_DEEPFAKE["src"] if _M_DEEPFAKE else "—"
    if _M_DEEPFAKE is _M_VIDEO:
        _df_src += " (shared trained model — dedicated image detector disabled: IO1_USE_IMAGE_DEEPFAKE=on to enable it)"
    _ai_src = _M_AI["src"] if _M_AI else "—"
    if _M_AI is _M_VIDEO:
        _ai_src += " (shared trained model — no dedicated \"AI vs genuine\" model)"
    if USE_OPENAI:
        try:
            from . import openai_vision as ov
            _verdict_backend = f"OpenAI · {ov.model_name()}" if ov.available() else f"local ResNet50 ({_shared})"
        except Exception:
            _verdict_backend = f"local ResNet50 ({_shared})"
    else:
        _verdict_backend = f"local ResNet50 ({_shared})"
    if _mtcnn is not None:
        _face_det_name = "MTCNN (facenet-pytorch) + Haar fallback" if _face_cascades else "MTCNN (facenet-pytorch)"
    else:
        _face_det_name = "opencv haar" if _face_cascades else "none (center-crop fallback)"
    INFO = {
        "device": DEVICE,
        "verdict_backend": _verdict_backend,
        "video_deepfake_model": _shared,
        "image_deepfake_model": _df_src,
        "ai_generated_model": _ai_src,
        "input_resolution": "224x224",
        "gradcam_layer": "layer4[-1]",
        "face_detector": _face_det_name,
        "text_explainer": llava_status if _llava else "geometric analysis of the heatmap",
    }
    return INFO


# ============================================================================
# Helpers
# ============================================================================
def _to_b64_png(arr_uint8_rgb) -> str:
    im = Image.fromarray(arr_uint8_rgb.astype("uint8"), mode="RGB")
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _detect_face_box(frame_rgb):
    """Locate the largest face in the frame. Tries MTCNN first (matches Islem's training
    distribution), falls back to OpenCV Haar. Returns (x, y, w, h) or None."""
    # 1) MTCNN — preferred (matches Islem's training distribution).
    # Per Islem's official inference: pick the face with the HIGHEST probability (not largest area)
    # — this avoids picking up incidental large objects MTCNN sometimes mistakes for faces.
    if _mtcnn is not None:
        try:
            from PIL import Image as _PIL
            pil = _PIL.fromarray(frame_rgb.astype("uint8"), mode="RGB")
            boxes, probs = _mtcnn.detect(pil)
            if boxes is not None and len(boxes) > 0 and probs is not None:
                idx = int(np.argmax(probs))
                x1, y1, x2, y2 = [float(v) for v in boxes[idx]]
                H, W = frame_rgb.shape[:2]
                x1 = max(0, x1); y1 = max(0, y1)
                x2 = min(W - 1, x2); y2 = min(H - 1, y2)
                if (x2 - x1) > 20 and (y2 - y1) > 20:
                    return (int(round(x1)), int(round(y1)), int(round(x2 - x1)), int(round(y2 - y1)))
        except Exception as e:
            print(f"[io1] MTCNN detect failed ({type(e).__name__}: {e}) — trying Haar")

    # 2) OpenCV Haar fallback
    if not _face_cascades:
        return None
    gray = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2GRAY)
    best = None
    for casc in _face_cascades:
        faces = casc.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(48, 48))
        for (x, y, w, h) in faces:
            if best is None or w * h > best[2] * best[3]:
                best = (int(x), int(y), int(w), int(h))
        if best is not None:
            break
    return best


def _crop_face(frame_rgb, box, margin: float | None = None):
    """Crop the face region.

    margin: extra fraction of the bbox to include on each side. Default is 0 when MTCNN was
    used (matches Islem's training distribution exactly), 0.20 when only Haar was available
    (Haar bboxes tend to clip the chin/forehead, so a small margin recovers them).
    """
    H, W = frame_rgb.shape[:2]
    if box is None:
        side = min(H, W)
        return frame_rgb[(H - side) // 2:(H - side) // 2 + side, (W - side) // 2:(W - side) // 2 + side], None
    # Match Islem's official inference (`fake_images_detection/inference.py`):
    # he adds a 15% margin around the MTCNN bbox before resizing to 224×224.
    if margin is None:
        margin = 0.15 if _mtcnn is not None else 0.20
    x, y, w, h = box
    mx, my = int(w * margin), int(h * margin)
    x0, y0 = max(0, x - mx), max(0, y - my)
    x1, y1 = min(W, x + w + mx), min(H, y + h + my)
    return frame_rgb[y0:y1, x0:x1], (x0, y0, x1 - x0, y1 - y0)


def _gradcam(model, target_layer, input_tensor, target_class: int):
    acts, grads = {}, {}
    h1 = target_layer.register_forward_hook(lambda _m, _i, o: acts.__setitem__("v", o.detach()))
    try:
        h2 = target_layer.register_full_backward_hook(lambda _m, gi, go: grads.__setitem__("v", go[0].detach()))
    except Exception:
        h2 = target_layer.register_backward_hook(lambda _m, gi, go: grads.__setitem__("v", go[0].detach()))
    try:
        model.zero_grad(set_to_none=True)
        with torch.enable_grad():
            logits = model(input_tensor)
            probs = torch.softmax(logits, dim=1)
            logits[0, target_class].backward()
        a, g = acts["v"][0], grads["v"][0]
        w = g.mean(dim=(1, 2))
        cam = torch.relu((w[:, None, None] * a).sum(dim=0))
        cam = cam - cam.min()
        denom = cam.max()
        if float(denom) > 1e-8:
            cam = cam / denom
        cam = F.interpolate(cam.unsqueeze(0).unsqueeze(0), size=(224, 224), mode="bilinear", align_corners=False)[0, 0]
        return cam.cpu().numpy(), probs.detach()[0].cpu().numpy()
    finally:
        h1.remove(); h2.remove()


def _colorize(cam01):
    cm = (cam01 * 255).clip(0, 255).astype("uint8")
    return cv2.cvtColor(cv2.applyColorMap(cm, cv2.COLORMAP_JET), cv2.COLOR_BGR2RGB)


def _overlay(base224_uint8, cam01, alpha: float = 0.45):
    heat = _colorize(cam01).astype("float32")
    out = (1 - alpha) * base224_uint8.astype("float32") + alpha * heat
    return out.clip(0, 255).astype("uint8")


def _heatmap_stats(cam01):
    H, W = cam01.shape
    total = float(cam01.sum())
    if total < 1e-8:
        return {"cx": 0.5, "cy": 0.5, "central_fraction": 0.0, "spread": 1.0, "pattern": "diffuse"}
    ys, xs = np.mgrid[0:H, 0:W].astype("float32")
    cx = float((xs * cam01).sum() / total) / (W - 1)
    cy = float((ys * cam01).sum() / total) / (H - 1)
    nx, ny = xs / (W - 1) - 0.5, ys / (H - 1) - 0.5
    dist = np.sqrt(nx * nx + ny * ny)
    central_fraction = float(cam01[dist <= 0.30].sum() / total)
    dcx, dcy = xs / (W - 1) - cx, ys / (H - 1) - cy
    spread = float(np.sqrt(((dcx * dcx + dcy * dcy) * cam01).sum() / total))
    if central_fraction >= 0.55 and abs(cx - 0.5) < 0.18 and abs(cy - 0.5) < 0.22:
        pattern = "centered"
    elif central_fraction <= 0.25:
        pattern = "peripheral" if spread > 0.28 else "off-center"
    else:
        pattern = "diffuse"
    return {"cx": round(cx, 3), "cy": round(cy, 3), "central_fraction": round(central_fraction, 3),
            "spread": round(spread, 3), "pattern": pattern}


def _zone_words(cx, cy, with_face: bool):
    s = "of the face" if with_face else "of the image"
    if cy < 0.36:
        vert = f"the top {s}" + (" (forehead, eyes)" if with_face else "")
    elif cy > 0.66:
        vert = f"the bottom {s}" + (" (mouth, chin)" if with_face else "")
    else:
        vert = f"the center {s}" + (" (eyes, nose, cheeks)" if with_face else "")
    if cx < 0.34:
        horiz = "left side"
    elif cx > 0.66:
        horiz = "right side"
    else:
        return vert
    return f"{vert}, {horiz}"


def _explain(task: str, is_fake: bool, conf: float, stats: dict, face_detected: bool) -> str:
    pct = round(conf * 100)
    if task == "image_ai_generated":
        zone = _zone_words(stats["cx"], stats["cy"], False)
        intro = "The analysis examined the whole image. "
        if stats["pattern"] in ("peripheral", "off-center"):
            where = "The clues considered are spread widely, mostly toward the edges. "
        elif stats["pattern"] == "diffuse":
            where = "The clues considered remain scattered across the whole image. "
        else:
            where = f"The clues considered are concentrated on {zone}. "
        if is_fake:
            interp = ("The detector finds texture regularities, overly smooth transitions and inconsistent details "
                      "typical of images fabricated by generative artificial intelligence. "
                      "The verdict leans toward a computer-generated image.")
        else:
            interp = ("Nothing suggests fabrication by artificial intelligence: grain, details and textures are "
                      "consistent with a photo genuinely captured by a device.")
        return intro + where + interp + f" Analysis confidence level: {pct}%."

    # deepfake tasks (video or image)
    s = "of the face" if face_detected else "of the image"
    zone = _zone_words(stats["cx"], stats["cy"], face_detected)
    intro = ("The analysis isolated the face present in the media and scrutinized it. "
             if face_detected else
             "No clear face was found: the analysis focused on the center of the image. ")
    if stats["pattern"] in ("peripheral", "off-center"):
        where = f"The regions that weighed most in the decision are spread widely, mostly toward the edges {s}. "
    elif stats["pattern"] == "diffuse":
        where = f"The regions that weighed in the decision remain scattered across the whole {s.replace('of the ', '')}. "
    else:
        where = f"The regions that weighed most in the decision are concentrated on {zone}. "
    if is_fake:
        if stats["pattern"] == "centered" and face_detected:
            interp = ("These hot zones are tightly grouped at the heart of the face — exactly where a face-swap "
                      "manipulation leaves the most traces. This supports the verdict: this face was "
                      "probably faked.")
        else:
            interp = (f"The detector finds inconsistencies suggesting manipulation. The verdict leans toward "
                      f"{('a faked face' if face_detected else 'faked content')} — to be confirmed with other clips.")
    else:
        if stats["pattern"] in ("peripheral", "off-center"):
            interp = ("These regions are shifted toward the edges and do not form the tight, central pattern typical "
                      "of a composite. This is consistent with authentic, unmanipulated content.")
        else:
            interp = ("No clear pattern of manipulation stands out: attention stays scattered. This is consistent with "
                      "authentic content.")
    return intro + where + interp + f" Analysis confidence level: {pct}%."


def _explain_llava(overlay_rgb_uint8) -> str | None:
    if not _llava:
        return None
    try:
        proc, vlm = _llava
        heatmap_pil = Image.fromarray(overlay_rgb_uint8.astype("uint8"), mode="RGB")
        prompt = (
            "USER: <image>\nYou are an expert AI forensic analyst looking at a Grad-CAM heatmap overlaid on a face.\n"
            "Task 1: Describe the exact location of the bright red/yellow hot zones on the image without guessing.\n"
            "Task 2: If the hot zones are tightly concentrated in the center of the face, conclude it is a 'FAKE' "
            "face-swap. If the hot zones are off-center, on the edges, or scattered, conclude it is a 'REAL' image.\n"
            "Be concise and factual. ASSISTANT:"
        )
        inputs = proc(text=prompt, images=heatmap_pil, return_tensors="pt").to(vlm.device)
        with torch.no_grad():
            gen = vlm.generate(**inputs, max_new_tokens=120, do_sample=True, temperature=0.4, top_p=0.9)
        return proc.batch_decode(gen, skip_special_tokens=True)[0].split("ASSISTANT:")[-1].strip() or None
    except Exception:
        return None


def _verdict_label(task: str, is_fake: bool, face_detected: bool) -> str:
    if task == "image_ai_generated":
        return "AI-generated image" if is_fake else "Authentic image"
    # deepfake tasks
    if face_detected:
        return "Faked face (deepfake)" if is_fake else "Authentic face"
    return "Content likely faked" if is_fake else "Content likely authentic"


# ============================================================================
# Core of the analysis
# ============================================================================
def _df_bundle_for(source_kind: str):
    """Chooses the deepfake model. By default it is always the trained ResNet50 (_M_VIDEO);
    _M_DEEPFAKE only differs if IO1_USE_IMAGE_DEEPFAKE=on was requested."""
    if source_kind == "video_frame" and _M_VIDEO is not None:
        return _M_VIDEO
    return _M_DEEPFAKE or _M_VIDEO or _M_AI


def _analyze_pil(img, source_kind: str, force: str | None = None) -> dict:
    """
    img : PIL.Image or RGB ndarray. source_kind ∈ {'image', 'video_frame'}.
    force : None=auto-routing · 'deepfake'=always the deepfake (face) detector
            · 'ai'=always the AI-generated image detector.
    """
    if hasattr(img, "convert"):
        rgb = np.array(img.convert("RGB"))
    else:
        rgb = np.asarray(img)
        if rgb.ndim == 2:
            rgb = np.stack([rgb] * 3, axis=-1)
        rgb = rgb[..., :3].astype("uint8")
    box = _detect_face_box(rgb)
    face_detected = box is not None
    crop_rgb, _ = _crop_face(rgb, box)   # face crop if box, otherwise center crop

    if force == "ai":
        bundle = _M_AI or _df_bundle_for(source_kind)
        task = "image_ai_generated" if _M_AI is not None else ("video_deepfake" if source_kind == "video_frame" else "image_deepfake")
        analyzed_rgb = rgb if _M_AI is not None else crop_rgb
        do_face_card = (_M_AI is None) and face_detected
    elif force == "deepfake":
        # If the user explicitly picked the face-deepfake mode but no face is in the image,
        # do NOT pretend to analyse it — the model would just see a meaningless center crop
        # and return garbage (typically FAKE because anything non-face is out of distribution).
        # The AI escalation step downstream will still get a chance to flag the whole image
        # as AI-generated if appropriate.
        if not face_detected and source_kind != "video_frame":
            return {
                "task": "image_deepfake",
                "verdict": "UNKNOWN",
                "verdict_class": "unknown",
                "verdict_label": "No face found in this image",
                "confidence": 0.0,
                "confidence_pct": 0,
                "risk_score": 0,
                "prob_fake": 0.0,
                "prob_real": 0.0,
                "face_detected": False,
                "face_box": None,
                "model_used": "—",
                "xai": {},
                "explanation": ("Face-deepfake detection requires at least one clearly visible face. "
                                "No face was found in this image — switch to the 'AI image' check if you "
                                "suspect the picture itself was generated by an AI image model."),
                "explanation_source": "info",
                "image_size": [int(rgb.shape[1]), int(rgb.shape[0])],
            }
        bundle = _df_bundle_for(source_kind)
        task = "video_deepfake" if source_kind == "video_frame" else "image_deepfake"
        analyzed_rgb = crop_rgb
        do_face_card = face_detected
    elif face_detected:
        # auto + face → deepfake
        bundle = _df_bundle_for(source_kind)
        task = "video_deepfake" if source_kind == "video_frame" else "image_deepfake"
        analyzed_rgb, do_face_card = crop_rgb, True
    else:
        # auto + no face → AI-vs-genuine if available, otherwise deepfake on center crop
        if _M_AI is not None:
            bundle, task, analyzed_rgb = _M_AI, "image_ai_generated", rgb
        else:
            bundle = _df_bundle_for(source_kind)
            task = "video_deepfake" if source_kind == "video_frame" else "image_deepfake"
            analyzed_rgb = crop_rgb
        do_face_card = False

    base_pil = Image.fromarray(analyzed_rgb.astype("uint8"), mode="RGB")
    base224 = np.array(base_pil.resize((224, 224)))
    input_tensor = _transform(base_pil).unsqueeze(0).to(DEVICE)

    cam01, probs = _gradcam(bundle["model"], bundle["layer"], input_tensor, target_class=bundle["fake_idx"])
    p_fake = float(probs[bundle["fake_idx"]])
    p_real = float(probs[bundle["real_idx"]])

    # Ensemble cross-check for face deepfake: run the *other* Islem model (best_ResNet50.pth) on
    # the same crop and average the two FAKE probabilities. This cancels each individual model's
    # bias — best_ResNet50 leans REAL, resnet50_deepfake (Model X) leans FAKE; the average is much
    # better calibrated. Only used when both models are present and we're on a face-deepfake task.
    if (task in ("image_deepfake", "video_deepfake")
            and _M_VIDEO is not None and _M_DEEPFAKE is not None
            and bundle is not _M_AI):
        try:
            other = _M_VIDEO if bundle is _M_DEEPFAKE else _M_DEEPFAKE
            with torch.no_grad():
                other_probs = torch.softmax(other["model"](input_tensor), dim=1)[0].cpu().numpy()
            other_p_fake = float(other_probs[other["fake_idx"]])
            p_fake = 0.5 * (p_fake + other_p_fake)
            p_real = 1.0 - p_fake
        except Exception as e:
            print(f"[io1] ensemble cross-check skipped ({type(e).__name__}: {e})")

    # For face-deepfake tasks apply the conservative threshold (Islem ensemble bias on real
    # photos sits around 0.55); for AI image-vs-genuine we keep simple argmax.
    if task in ("image_deepfake", "video_deepfake"):
        is_fake = p_fake >= DEEPFAKE_FAKE_THRESHOLD
    else:
        is_fake = p_fake >= p_real
    conf = p_fake if is_fake else p_real

    overlay = _overlay(base224, cam01)
    pure = _colorize(cam01)
    stats = _heatmap_stats(cam01)

    explanation, src = None, "analysis"
    if task in ("video_deepfake", "image_deepfake"):
        explanation = _explain_llava(overlay)
        if explanation:
            src = "llava"
    if not explanation:
        explanation = _explain(task, is_fake, conf, stats, face_detected)

    xai = {"gradcam_overlay": _to_b64_png(overlay), "gradcam_pure": _to_b64_png(pure), "hotzone": stats}
    if do_face_card:
        xai["face_crop"] = _to_b64_png(base224)

    return {
        "task": task,
        "verdict": ("FAKE" if is_fake else "REAL"),
        "verdict_class": "fake" if is_fake else "real",
        "verdict_label": _verdict_label(task, is_fake, face_detected),
        "confidence": round(conf, 4),
        "confidence_pct": round(conf * 100),
        "risk_score": round(p_fake * 100),
        "prob_fake": round(p_fake, 4),
        "prob_real": round(p_real, 4),
        "face_detected": face_detected,
        "face_box": list(box) if box is not None else None,
        "model_used": bundle["src"],
        "xai": xai,
        "explanation": explanation,
        "explanation_source": src,
        "image_size": [int(rgb.shape[1]), int(rgb.shape[0])],
    }


def _ai_unavailable_result(source: str) -> dict:
    return {
        "task": "ai_unavailable",
        "verdict": "UNKNOWN",
        "verdict_class": "unknown",
        "verdict_label": "Check not available yet",
        "confidence": 0.0,
        "confidence_pct": 0,
        "risk_score": 0,
        "face_detected": False,
        "model_used": "—",
        "xai": {},
        "explanation": ("Detection of AI-generated images is not available yet: the dedicated model has not been "
                        "put into service yet. Face deepfake detection, however, is fully operational."),
        "explanation_source": "info",
        "source": source,
        "frames_scanned": 0,
        "frames_with_face": 0,
    }


# ============================================================================
# OpenAI (vision) backend — main verdict when a key is configured
# ============================================================================
def openai_available() -> bool:
    if not USE_OPENAI:
        return False
    try:
        from . import openai_vision as ov
        return ov.available()
    except Exception:
        return False


def _task_from_category(category: str, face_detected: bool, source: str, mode: str = "auto") -> str:
    if source in ("video", "video_frame"):
        return "video_deepfake"
    # An explicit user choice (the tab they picked) wins over the model's own categorisation:
    # in "deepfake" mode we always present a face-deepfake analysis, in "ai" mode an AI-image one.
    if mode == "deepfake":
        return "image_deepfake"
    if mode == "ai":
        return "image_ai_generated"
    # mode == "auto" → let the model's category (then the presence of a face) decide
    c = (category or "").lower()
    if "deepfake" in c:
        return "image_deepfake"
    if "ai" in c or "generat" in c:
        return "image_ai_generated"
    if "edit" in c or "photoshop" in c or "retouch" in c:
        return "image_ai_generated"          # "edited" → "fabricated / retouched image" banner
    return "image_deepfake" if face_detected else "image_ai_generated"


def _openai_analyze(pil, source: str, mode: str = "auto") -> dict | None:
    """Analysis via OpenAI vision. Returns the result dict (standard io1 shape) or None if OpenAI
    is not configured. Raises an exception if the API call fails (→ the caller falls back to the local model)."""
    if not USE_OPENAI:
        return None
    from . import openai_vision as ov
    if not ov.available():
        return None
    rgb = np.array(pil.convert("RGB"))
    box = _detect_face_box(rgb)
    face_detected = box is not None
    # In explicit "deepfake" mode the user is telling us there's a face — prime the model accordingly.
    # In explicit "ai" mode the user suspects it's AI-generated — tell the model to scrutinise harder.
    o = ov.analyze(pil, hint_face=(face_detected or mode == "deepfake"), hint_ai=(mode == "ai"))
    if o is None:
        return None
    # the model can correct our Haar face detector (sometimes misses, or false positive)
    if o.get("has_face") is True:
        face_detected = True
    elif o.get("has_face") is False:
        # …but don't let it deny the face when the user explicitly chose the face-deepfake mode
        if mode == "deepfake":
            face_detected = True   # keep treating it as a face analysis (box stays whatever Haar found)
        else:
            face_detected, box = False, None

    is_fake = bool(o["is_fake"])
    task = _task_from_category(o.get("category"), face_detected, source, mode)
    conf = int(o["confidence_pct"])
    p_fake = round((conf / 100.0) if is_fake else (1.0 - conf / 100.0), 4)

    reason = (o.get("reason") or "").strip()
    if not reason:
        reason = ("The analysis found no sign of fabrication: this image appears to be a genuine photo."
                  if not is_fake else
                  "The analysis finds inconsistent elements suggesting a fabricated or retouched image.")
    clues = o.get("clues") or []
    explanation = reason.rstrip(" .") + ". Clues found: " + "; ".join(clues) + "." if clues else reason

    xai: dict = {}
    if task in ("image_deepfake", "video_deepfake") and box is not None:
        crop_rgb, _ = _crop_face(rgb, box)
        base224 = np.array(Image.fromarray(crop_rgb.astype("uint8"), mode="RGB").resize((224, 224)))
        xai["face_crop"] = _to_b64_png(base224)

    return {
        "task": task,
        "verdict": "FAKE" if is_fake else "REAL",
        "verdict_class": "fake" if is_fake else "real",
        "verdict_label": _verdict_label(task, is_fake, face_detected),
        "confidence": round(conf / 100.0, 4),
        "confidence_pct": conf,
        "risk_score": round(p_fake * 100),
        "prob_fake": p_fake,
        "prob_real": round(1.0 - p_fake, 4),
        "face_detected": face_detected,
        "face_box": list(box) if box is not None else None,
        "model_used": f"OpenAI · {o.get('model', 'gpt-4o')}",
        "category": o.get("category") or "",
        "xai": xai,
        "explanation": explanation,
        "explanation_source": "openai",
        "image_size": [int(rgb.shape[1]), int(rgb.shape[0])],
    }


def _ai_detector_escalation(pil, res: dict) -> dict:
    """Second opinion: run two dedicated AI-image classifiers (Organika + umm-maybe) and apply a
    2-tier consensus rule. Only ESCALATES (REAL → FAKE) — never flips a FAKE back to REAL.

    Empirically calibrated to catch most StyleGAN/diffusion faces (ThisPersonDoesNotExist style)
    while keeping the false-positive rate on real portraits near zero. See ai_detector.py header
    for the tuning rationale."""
    try:
        if res.get("verdict_class") == "fake":
            return res
        from . import ai_detector as aid
        r = aid.predict_ai(pil)
        if r is None or not r.get("escalate"):
            return res
        p1 = float(r["primary"])
        p2 = float(r["secondary"])
        tier = int(r["tier"])
        # Confidence reported on the escalated verdict — bound by the primary score (the one
        # carrying TPDNE recall) but never below 65%.
        cp = max(round(p1, 4), 0.65)
        pct = int(round(cp * 100))
        res["verdict"] = "FAKE"; res["verdict_class"] = "fake"
        res["task"] = "image_ai_generated"; res["category"] = "ai_generated"
        res["confidence"] = cp; res["confidence_pct"] = pct
        res["prob_fake"] = cp; res["prob_real"] = round(1.0 - cp, 4)
        res["risk_score"] = pct
        try:
            res["verdict_label"] = _verdict_label("image_ai_generated", True, res.get("face_detected", False))
        except Exception:
            res["verdict_label"] = "AI-generated image"
        base = (res.get("explanation") or "").rstrip(" .")
        tier_word = "strongly" if tier == 1 else "by consensus"
        res["explanation"] = ((base + ". ") if base else "") + (
            f"Two independent AI-image classifiers agree {tier_word} that this picture was generated by AI "
            f"(primary detector: {int(round(p1 * 100))}%, secondary: {int(round(p2 * 100))}%). This often catches "
            "generations — like StyleGAN portraits from ThisPersonDoesNotExist — that the face-deepfake model misses.")
        res["explanation_source"] = (res.get("explanation_source") or "") + "+ai_consensus"
        res["model_used"] = (res.get("model_used") or "") + " + AI-image consensus"
    except Exception as e:
        print(f"[io1] AI-detector escalation skipped ({type(e).__name__}: {e})")
    return res


def analyze_image(pil, mode: str = "auto") -> dict:
    """mode ∈ {'auto', 'deepfake', 'ai'} — explicitly chooses the detector."""
    if not LOADED:
        raise RuntimeError("Module io1 not initialized.")
    mode = (mode or "auto").strip().lower()

    # 1) OpenAI vision backend if a key is configured (much more reliable, especially for generative AI)
    try:
        res = _openai_analyze(pil, "image", mode)
    except Exception as e:
        print(f"[io1] OpenAI vision unavailable, falling back to the local model: {e}")
        res = None

    # 2) Fallback: local ResNet50 model
    if res is None:
        if mode == "ai" and _M_AI is None:
            return _ai_unavailable_result("image")
        force = None if mode == "auto" else ("ai" if mode == "ai" else "deepfake")
        res = _analyze_pil(pil, "image", force=force)

    res["source"] = "image"
    res["mode"] = mode
    res["frames_scanned"] = 1
    res["frames_with_face"] = 1 if res["face_detected"] else 0

    # 3) Run the dedicated AI-image classifier as a second opinion in EVERY mode. Needed because:
    #   - in mode='ai': the user explicitly suspects AI generation, escalate aggressively.
    #   - in mode='auto'/'deepfake': the deepfake ensemble was trained on face-swap deepfakes
    #     (FaceForensics style); it misses GAN-generated faces like ThisPersonDoesNotExist.
    #     The dima806 classifier fills that blind spot — without it, a TPDNE face goes through
    #     undetected even though it is clearly synthetic.
    # The escalation only flips REAL→FAKE (never the other way) with a conservative threshold,
    # so it doesn't false-positive on real portraits.
    res = _ai_detector_escalation(pil, res)
    res["frames_with_face"] = 1 if res["face_detected"] else 0
    return res


def analyze_video(path: str) -> dict:
    """Video → face deepfake detection only."""
    if not LOADED:
        raise RuntimeError("Module io1 not initialized.")
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        cap.release()
        raise RuntimeError("Unreadable video.")
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    idxs = sorted({int(i) for i in np.linspace(0, total - 1, min(MAX_FRAMES_SCAN, total))}) if total > 1 else list(range(MAX_FRAMES_SCAN))

    frames = []  # (rgb, has_face, area)
    for i in idxs:
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ok, fr = cap.read()
        if not ok or fr is None:
            continue
        rgb = cv2.cvtColor(fr, cv2.COLOR_BGR2RGB)
        box = _detect_face_box(rgb)
        frames.append((rgb, box is not None, (box[2] * box[3]) if box is not None else 0))
        if len(frames) >= MAX_FRAMES_SCAN:
            break
    if not frames:
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        ok, fr = cap.read()
        if ok and fr is not None:
            frames.append((cv2.cvtColor(fr, cv2.COLOR_BGR2RGB), False, 0))
    cap.release()
    if not frames:
        raise RuntimeError("No usable frame in the video.")

    with_face = [f for f in frames if f[1]]
    chosen = max(with_face, key=lambda f: f[2]) if with_face else frames[0]

    # 1) OpenAI vision backend on the chosen frame, if a key is configured
    result = None
    try:
        result = _openai_analyze(Image.fromarray(chosen[0].astype("uint8"), mode="RGB"), "video")
    except Exception as e:
        print(f"[io1] OpenAI vision (video) unavailable, falling back to the local model: {e}")
        result = None
    if result is None:
        result = _analyze_pil(chosen[0], "video_frame", force="deepfake")
    result["source"] = "video"
    result["frames_scanned"] = len(frames)
    result["frames_with_face"] = len(with_face)

    # aggregation: mean of p_fake over the frames with a face (only for the local model)
    if result.get("explanation_source") != "openai" and result["task"] in ("video_deepfake", "image_deepfake") and len(with_face) > 1:
        bundle = _M_VIDEO if (_M_VIDEO is not None) else _M_DEEPFAKE
        if bundle is not None:
            ps = [result["prob_fake"]]
            for (rgb, _hf, _a) in with_face:
                if rgb is chosen[0]:
                    continue
                try:
                    crop_rgb, _ = _crop_face(rgb, _detect_face_box(rgb))
                    t = _transform(Image.fromarray(crop_rgb.astype("uint8"), mode="RGB")).unsqueeze(0).to(DEVICE)
                    with torch.no_grad():
                        pr = torch.softmax(bundle["model"](t), dim=1)[0]
                    ps.append(float(pr[bundle["fake_idx"]]))
                except Exception:
                    pass
            if len(ps) > 1:
                result["aggregate_prob_fake"] = round(sum(ps) / len(ps), 4)
                result["aggregate_fake_ratio"] = round(sum(1 for p in ps if p >= 0.5) / len(ps), 3)
    return result
