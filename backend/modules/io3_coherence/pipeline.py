"""
Pipeline V4.1 — Cross-Modal Coherence (Objective 2).
Models : CLIP ViT-L/14 + YOLOv8m + EasyOCR + SAM (optional) + Whisper.
XAI    : Grad-CAM, Waterfall, SHAP modality attribution.

All models are loaded once via `init()` and then stored in the module.
"""
from __future__ import annotations

import io
import os
import base64
import warnings
from typing import Optional

from backend.shared.device import DEVICE

warnings.filterwarnings("ignore")

# ─── Heavy imports loaded lazily so that the API can boot without the ML stack
# (smoke test, stub mode). `_ensure_heavy_deps()` is called from init() and
# raises a clear error if anything is missing. ──────────────────────────────
np = cv2 = torch = F = Image = plt = None
_HEAVY_DEPS_LOADED = False
_HEAVY_DEPS_ERR: Optional[str] = None


def _ensure_heavy_deps() -> None:
    global np, cv2, torch, F, Image, plt, _HEAVY_DEPS_LOADED, _HEAVY_DEPS_ERR
    if _HEAVY_DEPS_LOADED:
        return
    try:
        import numpy as _np
        import cv2 as _cv2
        import torch as _torch
        import torch.nn.functional as _F
        from PIL import Image as _Image
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as _plt
    except ImportError as e:
        _HEAVY_DEPS_ERR = str(e)
        raise RuntimeError(
            f"Module io3 — missing ML dependencies ({e}). "
            "Install: pip install -r backend/requirements.txt"
        ) from e
    np, cv2, torch, F, Image, plt = _np, _cv2, _torch, _F, _Image, _plt
    _HEAVY_DEPS_LOADED = True

# ─── Config (env vars) ─────────────────────────────────────────────────────
CLIP_FINETUNED_PATH = os.environ.get("CLIP_FINETUNED_PATH", "clip_finetuned_coherence.pth")
SAM_CHECKPOINT = os.environ.get("SAM_CHECKPOINT", "sam_vit_b_01ec64.pth")
YOLO_WEIGHTS = os.environ.get("YOLO_WEIGHTS", "yolov8m.pt")
WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "small")
ENABLE_SAM = os.environ.get("ENABLE_SAM", "auto")  # "auto" | "off"

WEIGHTS = {"CLIP": 0.40, "SAM": 0.25, "Whisper": 0.15, "YOLO": 0.10, "OCR": 0.10}

# Globals populated by init()
_clip_model = None
_clip_preprocess = None
_clip_tokenizer = None
_yolo_model = None
_ocr_reader = None
_whisper_model = None
_sam_mask_generator = None
SAM_AVAILABLE = False
LOADED = False
INFO: dict = {}

KEYWORD_MAP = {
    "dog": "dog", "cat": "cat", "car": "car", "bike": "bicycle",
    "bicycle": "bicycle", "man": "person", "woman": "person",
    "boy": "person", "girl": "person", "child": "person",
    "people": "person", "baby": "person", "person": "person",
    "truck": "truck", "motorcycle": "motorcycle", "horse": "horse",
    "bird": "bird", "boat": "boat", "bench": "bench",
    "skateboard": "skateboard", "surfboard": "surfboard",
    "umbrella": "umbrella", "bus": "bus", "train": "train",
    "plane": "airplane", "airplane": "airplane",
    "ball": "sports ball", "phone": "cell phone", "laptop": "laptop",
    "computer": "laptop", "book": "book", "bottle": "bottle",
    "cup": "cup", "chair": "chair", "table": "dining table",
    "chien": "dog", "chat": "cat", "voiture": "car", "vélo": "bicycle",
}

STOP_WORDS = {
    "the", "a", "an", "is", "are", "in", "on", "at", "to", "of", "and", "or",
    "for", "with", "it", "this", "that", "was", "were", "be", "been", "has",
    "have", "had", "do", "does", "did", "will", "would", "can", "could", "i",
    "you", "he", "she", "they", "we", "my", "your", "his", "her", "its",
    "le", "la", "les", "un", "une", "de", "du", "des", "et",
}


# ============================================================================
# INITIALIZATION
# ============================================================================
def init() -> dict:
    """Loads all models. Idempotent."""
    global _clip_model, _clip_preprocess, _clip_tokenizer
    global _yolo_model, _ocr_reader, _whisper_model
    global _sam_mask_generator, SAM_AVAILABLE, LOADED, INFO
    if LOADED:
        return INFO

    _ensure_heavy_deps()
    print(f"[io3] Device: {DEVICE}")
    print("[io3] Loading CLIP ViT-L/14…")
    import open_clip
    _clip_model, _, _clip_preprocess = open_clip.create_model_and_transforms(
        "ViT-L-14", pretrained="laion2b_s32b_b82k"
    )
    _clip_tokenizer = open_clip.get_tokenizer("ViT-L-14")
    if os.path.exists(CLIP_FINETUNED_PATH):
        _clip_model.load_state_dict(torch.load(CLIP_FINETUNED_PATH, map_location=DEVICE))
        print(f"[io3]   → fine-tuned model loaded: {CLIP_FINETUNED_PATH}")
    _clip_model = _clip_model.to(DEVICE).eval()

    print("[io3] Loading YOLOv8m…")
    from ultralytics import YOLO
    _yolo_model = YOLO(YOLO_WEIGHTS)
    _yolo_model.to(DEVICE)

    print("[io3] Loading EasyOCR (en + fr)…")
    import easyocr
    _ocr_reader = easyocr.Reader(["en", "fr"], gpu=(DEVICE == "cuda"), verbose=False)

    print(f"[io3] Loading Whisper {WHISPER_MODEL}…")
    import whisper
    _whisper_model = whisper.load_model(WHISPER_MODEL, device=DEVICE)

    if ENABLE_SAM != "off" and os.path.exists(SAM_CHECKPOINT):
        try:
            from segment_anything import sam_model_registry, SamAutomaticMaskGenerator
            sam = sam_model_registry["vit_b"](checkpoint=SAM_CHECKPOINT).to(DEVICE)
            _sam_mask_generator = SamAutomaticMaskGenerator(
                model=sam, points_per_side=16, pred_iou_thresh=0.86,
                stability_score_thresh=0.92, min_mask_region_area=1000,
            )
            SAM_AVAILABLE = True
            print("[io3]   → SAM ViT-B loaded")
        except Exception as e:
            print(f"[io3]   → SAM unavailable ({e}), falling back to 3x3 grid")

    INFO = {
        "device": DEVICE,
        "clip": "ViT-L/14 (laion2b_s32b_b82k)" + (" [fine-tuned]" if os.path.exists(CLIP_FINETUNED_PATH) else ""),
        "yolo": YOLO_WEIGHTS,
        "ocr": "easyocr (en, fr)",
        "sam": "ViT-B" if SAM_AVAILABLE else "fallback grid 3x3",
        "whisper": WHISPER_MODEL,
    }
    LOADED = True
    print(f"[io3] ✅ All models ready on {DEVICE}")
    return INFO


# ============================================================================
# CLIP helpers — note: no @torch.no_grad() at module level (lazy imports)
# ============================================================================
def _encode_image(image) -> "np.ndarray":
    with torch.no_grad():
        img_tensor = _clip_preprocess(image.convert("RGB")).unsqueeze(0).to(DEVICE)
        features = _clip_model.encode_image(img_tensor)
        return F.normalize(features, dim=-1).cpu().numpy().flatten()


def _encode_text(text: str) -> "np.ndarray":
    with torch.no_grad():
        tokens = _clip_tokenizer([text]).to(DEVICE)
        features = _clip_model.encode_text(tokens)
        return F.normalize(features, dim=-1).cpu().numpy().flatten()


# ============================================================================
# YOLO
# ============================================================================
def _detect_objects(image_path: str, confidence: float = 0.4):
    results = _yolo_model(image_path, conf=confidence, verbose=False, device=DEVICE)
    detections = []
    for r in results:
        for box in r.boxes:
            detections.append({"class": r.names[int(box.cls)], "confidence": float(box.conf)})
    return detections


def _yolo_match_score(detections, text: str):
    detected = set(d["class"] for d in detections)
    text_lower = text.lower()
    matches, mismatches, checked = [], [], set()
    for kw, coco in KEYWORD_MAP.items():
        if kw in text_lower and coco not in checked:
            checked.add(coco)
            (matches if coco in detected else mismatches).append(coco)
    spec_m = [m for m in matches if m != "person"]
    spec_mm = [m for m in mismatches if m != "person"]
    total = len(spec_m) + len(spec_mm)
    score = len(spec_m) / total if total else 0.5
    return score, [d["class"] for d in detections]


# ============================================================================
# OCR
# ============================================================================
def _extract_ocr(image_path: str, min_conf: float = 0.3):
    results = _ocr_reader.readtext(image_path)
    parts = [t for _, t, c in results if c >= min_conf]
    return {"has_text": bool(parts), "full_text": " ".join(parts), "num_segments": len(parts)}


def _ocr_match_score(ocr_result, claimed_text: str):
    if not ocr_result["has_text"]:
        return 0.5, ""
    ocr_w = set(ocr_result["full_text"].lower().split()) - STOP_WORDS
    txt_w = set(claimed_text.lower().split()) - STOP_WORDS
    if not ocr_w:
        return 0.5, ocr_result["full_text"]
    return len(ocr_w & txt_w) / len(ocr_w), ocr_result["full_text"]


# ============================================================================
# SAM segmentation (with grid fallback)
# ============================================================================
def _sam_segment(pil_image: Image.Image, text: str, max_segments: int = 10):
    img_np = np.array(pil_image.convert("RGB"))
    txt_emb = _encode_text(text)

    if SAM_AVAILABLE:
        try:
            masks = _sam_mask_generator.generate(img_np)
            masks = sorted(masks, key=lambda x: x["area"], reverse=True)[:max_segments]
            scores = []
            for m in masks:
                x, y, w, h = m["bbox"]; margin = 10
                x1, y1 = max(0, x - margin), max(0, y - margin)
                x2 = min(img_np.shape[1], x + w + margin)
                y2 = min(img_np.shape[0], y + h + margin)
                region = pil_image.crop((x1, y1, x2, y2))
                scores.append(float(np.dot(_encode_image(region), txt_emb)))
            mean_s = float(np.mean(scores)) if scores else 0.0
            std_s = float(np.std(scores)) if scores else 0.0
            incoh = sum(1 for s in scores if s < mean_s - std_s)
            seg = max(0.0, min(1.0, mean_s * 2))
            if incoh >= 3:
                seg *= 0.7
            return {"method": "SAM", "num_segments": len(scores), "mean": mean_s, "incoherent": incoh, "score": seg}
        except Exception:
            pass

    # 3x3 grid fallback
    w, h = pil_image.size
    cw, ch = w // 3, h // 3
    scores = []
    for r in range(3):
        for c in range(3):
            region = pil_image.crop((c * cw, r * ch, min((c + 1) * cw, w), min((r + 1) * ch, h)))
            scores.append(float(np.dot(_encode_image(region), txt_emb)))
    mean_s = float(np.mean(scores)); std_s = float(np.std(scores))
    incoh = sum(1 for s in scores if s < mean_s - std_s)
    seg = max(0.0, min(1.0, mean_s * 2))
    if incoh >= 3:
        seg *= 0.7
    return {"method": "grid", "num_segments": 9, "mean": mean_s, "incoherent": incoh, "score": seg}


# ============================================================================
# Whisper / video
# ============================================================================
def _transcribe_video_audio(video_path: str):
    audio_path = video_path + ".wav"
    os.system(f'ffmpeg -y -i "{video_path}" -vn -acodec pcm_s16le -ar 16000 -ac 1 "{audio_path}" 2>/dev/null')
    if not os.path.exists(audio_path) or os.path.getsize(audio_path) < 1000:
        return {"has_audio": False, "text": "", "language": ""}
    try:
        result = _whisper_model.transcribe(audio_path, fp16=(DEVICE == "cuda"))
        return {"has_audio": True, "text": result["text"].strip(), "language": result.get("language", "unknown")}
    finally:
        if os.path.exists(audio_path):
            try: os.unlink(audio_path)
            except OSError: pass


def _extract_keyframes(video_path: str, max_frames: int = 6):
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total <= 0 or fps <= 0:
        cap.release()
        return []
    n = min(max_frames, max(3, int(total / fps / 2)))
    interval = max(1, total // n)
    kfs = []
    for i in range(n):
        cap.set(cv2.CAP_PROP_POS_FRAMES, i * interval)
        ret, frame = cap.read()
        if ret:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            kfs.append({"image": Image.fromarray(rgb), "time": (i * interval) / fps})
    cap.release()
    return kfs


# ============================================================================
# XAI
# ============================================================================
def _gradcam(pil_image: Image.Image, text: str):
    img_tensor = _clip_preprocess(pil_image.convert("RGB")).unsqueeze(0).to(DEVICE)
    text_tokens = _clip_tokenizer([text]).to(DEVICE)
    visual = _clip_model.visual
    target = visual.transformer.resblocks[-1].ln_1
    activations, gradients = {}, {}
    h1 = target.register_forward_hook(lambda m, i, o: activations.update({"v": o.detach()}))
    h2 = target.register_full_backward_hook(lambda m, gi, go: gradients.update({"v": go[0].detach()}))

    img_f = _clip_model.encode_image(img_tensor)
    txt_f = _clip_model.encode_text(text_tokens)
    img_f = img_f / img_f.norm(dim=-1, keepdim=True)
    txt_f = txt_f / txt_f.norm(dim=-1, keepdim=True)
    sim = (img_f * txt_f).sum()
    _clip_model.zero_grad()
    sim.backward()
    h1.remove(); h2.remove()

    grads = gradients["v"]; acts = activations["v"]
    if grads.dim() == 3:
        if grads.shape[1] == 1: grads = grads.squeeze(1); acts = acts.squeeze(1)
        elif grads.shape[0] == 1: grads = grads.squeeze(0); acts = acts.squeeze(0)
    weights = (grads * acts).sum(dim=-1)
    patches = weights[1:]
    n = patches.shape[0]; grid = int(np.sqrt(n))
    if grid * grid != n:
        return None
    cam = patches.reshape(grid, grid).cpu().float().numpy()
    cam = np.abs(cam)
    if cam.max() > 0: cam /= cam.max()
    img_np = np.array(pil_image.convert("RGB"))
    cam_r = cv2.resize(cam, (img_np.shape[1], img_np.shape[0]), interpolation=cv2.INTER_CUBIC)
    cam_r = cv2.GaussianBlur(cam_r, (15, 15), 0)
    if cam_r.max() > 0: cam_r /= cam_r.max()
    return {"cam": cam_r, "image": img_np, "score": float(sim.item())}


def _gradcam_to_b64(g) -> Optional[str]:
    if g is None:
        return None
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    axes[0].imshow(g["image"]); axes[0].set_title("Original image"); axes[0].axis("off")
    axes[1].imshow(g["cam"], cmap="jet", vmin=0, vmax=1); axes[1].set_title("Heatmap"); axes[1].axis("off")
    axes[2].imshow(g["image"]); axes[2].imshow(g["cam"], cmap="jet", alpha=0.5, vmin=0, vmax=1)
    axes[2].set_title(f"CLIP score: {g['score']:.3f}"); axes[2].axis("off")
    plt.tight_layout()
    return _fig_to_b64(fig)


def _fig_to_b64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("ascii")


def _waterfall_b64(scores: dict, verdict: str, text: str) -> str:
    components = [
        ("CLIP (40%)",    scores["clip"]    * WEIGHTS["CLIP"]),
        ("SAM (25%)",     scores["sam"]     * WEIGHTS["SAM"]),
        ("Whisper (15%)", scores["whisper"] * WEIGHTS["Whisper"]),
        ("YOLO (10%)",    scores["yolo"]    * WEIGHTS["YOLO"]),
        ("OCR (10%)",     scores["ocr"]     * WEIGHTS["OCR"]),
    ]
    names = [c[0] for c in components]
    values = [c[1] for c in components]
    cumul = np.cumsum([0.0] + values)
    colors = ["#7F77DD", "#D4537E", "#BA7517", "#378ADD", "#D85A30"]
    fig, ax = plt.subplots(figsize=(11, 4.5))
    for i, (name, v) in enumerate(zip(names, values)):
        ax.bar(i, v, bottom=cumul[i], color=colors[i], width=0.6, edgecolor="white", linewidth=1)
        ax.text(i, cumul[i] + v / 2, f"{v:.3f}", ha="center", va="center", fontsize=10, fontweight="bold", color="white")
        if i < len(values) - 1:
            ax.plot([i + 0.3, i + 0.7], [cumul[i + 1], cumul[i + 1]], color="gray", linewidth=0.8, linestyle="--")
    total = float(cumul[-1])
    vc = "#16a34a" if verdict == "COHERENT" else "#f59e0b" if verdict == "SUSPECT" else "#dc2626"
    ax.bar(len(values), total, color=vc, width=0.6, edgecolor="white", linewidth=1)
    ax.text(len(values), total / 2, f"{total:.3f}", ha="center", va="center", fontsize=12, fontweight="bold", color="white")
    ax.axhline(y=0.25, color="#16a34a", linestyle=":", alpha=0.6)
    ax.axhline(y=0.15, color="#dc2626", linestyle=":", alpha=0.6)
    ax.set_xticks(range(len(names) + 1))
    ax.set_xticklabels(names + [f"TOTAL\n[{verdict}]"], fontsize=9)
    ax.set_ylabel("Cumulative score")
    ax.set_title(f'Waterfall — "{text[:60]}…"', fontweight="bold")
    plt.tight_layout()
    return _fig_to_b64(fig)


def _shap_attribution(scores: dict, full_score: float, verdict: str):
    contribs = {k: round(WEIGHTS[k] * scores[k.lower() if k != "Whisper" else "whisper"], 4) for k in ("CLIP", "SAM", "Whisper", "YOLO", "OCR")}
    return {
        "contributions": contribs,
        "individual_scores": {k: round(v, 4) for k, v in scores.items()},
        "full_score": round(full_score, 4),
        "verdict": verdict,
    }


def _verdict_image(s: float) -> str:
    return "COHERENT" if s >= 0.25 else "SUSPECT" if s >= 0.15 else "INCOHERENT"


def _verdict_video(s: float) -> str:
    return "COHERENT" if s >= 0.22 else "SUSPECT" if s >= 0.12 else "INCOHERENT"


# ============================================================================
# Public pipelines
# ============================================================================
def analyze_image(pil_image: Image.Image, image_path: str, text: str) -> dict:
    init()
    img_emb = _encode_image(pil_image)
    txt_emb = _encode_text(text)
    clip_score = float(np.dot(img_emb, txt_emb))

    detections = _detect_objects(image_path)
    yolo_score, objects = _yolo_match_score(detections, text)

    ocr_result = _extract_ocr(image_path)
    ocr_score, ocr_text = _ocr_match_score(ocr_result, text)

    sam_result = _sam_segment(pil_image, text)
    sam_score = sam_result["score"]
    whisper_score = 0.5  # N/A for image

    combined = (
        WEIGHTS["CLIP"]    * clip_score +
        WEIGHTS["SAM"]     * sam_score +
        WEIGHTS["Whisper"] * whisper_score +
        WEIGHTS["YOLO"]    * yolo_score +
        WEIGHTS["OCR"]     * ocr_score
    )
    verdict = _verdict_image(combined)
    scores = {"clip": clip_score, "sam": sam_score, "whisper": whisper_score, "yolo": yolo_score, "ocr": ocr_score}

    gradcam_b64 = waterfall_b64 = None
    try: gradcam_b64 = _gradcam_to_b64(_gradcam(pil_image, text))
    except Exception as e: print(f"[io3][warn] Grad-CAM: {e}")
    try: waterfall_b64 = _waterfall_b64(scores, verdict, text)
    except Exception as e: print(f"[io3][warn] Waterfall: {e}")

    return {
        "verdict": verdict,
        "score_global": round(combined, 4),
        "scores": {k: round(v, 4) for k, v in scores.items()},
        "objects_detected": objects,
        "ocr_text": ocr_text,
        "segmentation": {
            "method": sam_result["method"],
            "num_segments": sam_result["num_segments"],
            "mean": round(sam_result["mean"], 4),
            "incoherent": sam_result["incoherent"],
        },
        "xai": {
            "gradcam_base64": gradcam_b64,
            "waterfall_base64": waterfall_b64,
            "shap": _shap_attribution(scores, combined, verdict),
        },
    }


def analyze_video(video_path: str, text: str) -> dict:
    init()
    keyframes = _extract_keyframes(video_path, max_frames=8)
    if not keyframes:
        raise ValueError("Unable to extract keyframes from the video.")
    main_kf = keyframes[len(keyframes) // 2]["image"]

    audio = _transcribe_video_audio(video_path)

    all_objects = set()
    for kf in keyframes:
        kf_path = video_path + "_kf.jpg"
        kf["image"].save(kf_path)
        try:
            for d in _detect_objects(kf_path):
                all_objects.add(d["class"])
        finally:
            try: os.unlink(kf_path)
            except OSError: pass
    objects_list = list(all_objects)

    ocr_texts = []
    for kf in keyframes[:3]:
        kf_path = video_path + "_kf_ocr.jpg"
        kf["image"].save(kf_path)
        try:
            r = _extract_ocr(kf_path)
            if r["has_text"]:
                ocr_texts.append(r["full_text"])
        finally:
            try: os.unlink(kf_path)
            except OSError: pass
    ocr_text = " ".join(ocr_texts)

    text_emb = _encode_text(text)
    kf_embs = [_encode_image(kf["image"]) for kf in keyframes]
    mean_img_emb = np.mean(kf_embs, axis=0)
    mean_img_emb = mean_img_emb / (np.linalg.norm(mean_img_emb) + 1e-8)
    audio_emb = _encode_text(audio["text"][:200]) if (audio["has_audio"] and len(audio["text"]) > 5) else None

    kf_scores = [float(np.dot(text_emb, e)) for e in kf_embs]
    s_text_image = 0.7 * float(max(kf_scores)) + 0.3 * float(np.mean(kf_scores))
    s_text_audio = float(np.dot(text_emb, audio_emb)) if audio_emb is not None else 0.0
    s_audio_image = float(np.dot(audio_emb, mean_img_emb)) if audio_emb is not None else 0.0
    if len(kf_embs) >= 2:
        s_temporal = float(np.mean([float(np.dot(kf_embs[i], kf_embs[i + 1])) for i in range(len(kf_embs) - 1)]))
    else:
        s_temporal = 1.0

    text_lower = text.lower()
    obj_match = obj_total = 0; checked = set()
    for kw, coco in KEYWORD_MAP.items():
        if kw in text_lower and coco not in checked:
            checked.add(coco); obj_total += 1
            if coco in objects_list: obj_match += 1
    s_objects = obj_match / obj_total if obj_total else 0.0

    if ocr_text:
        ow = set(ocr_text.lower().split()) - STOP_WORDS
        tw = set(text_lower.split()) - STOP_WORDS
        s_ocr = (len(ow & tw) / len(ow)) if ow else 0.0
    else:
        s_ocr = 0.0

    if audio_emb is not None:
        score_global = (0.40 * s_text_image + 0.20 * s_text_audio + 0.10 * s_audio_image
                        + 0.10 * s_temporal + 0.10 * s_objects + 0.10 * s_ocr)
    else:
        score_global = (0.55 * s_text_image + 0.15 * s_temporal + 0.15 * s_objects + 0.15 * s_ocr)
    verdict = _verdict_video(score_global)

    cross_scores = {
        "text_image":  round(s_text_image, 4),
        "text_audio":  round(s_text_audio, 4),
        "audio_image": round(s_audio_image, 4),
        "temporal":    round(s_temporal, 4),
        "objects":     round(s_objects, 4),
        "ocr":         round(s_ocr, 4),
    }

    gradcam_b64 = waterfall_b64 = None
    try: gradcam_b64 = _gradcam_to_b64(_gradcam(main_kf, text))
    except Exception as e: print(f"[io3][warn] Grad-CAM video: {e}")
    waterfall_scores = {
        "clip": s_text_image, "sam": s_temporal,
        "whisper": s_text_audio if audio_emb is not None else 0.5,
        "yolo": s_objects, "ocr": s_ocr,
    }
    try: waterfall_b64 = _waterfall_b64(waterfall_scores, verdict, text)
    except Exception as e: print(f"[io3][warn] Waterfall video: {e}")

    return {
        "verdict": verdict,
        "score_global": round(score_global, 4),
        "scores": cross_scores,
        "audio_transcription": audio["text"],
        "audio_language": audio["language"],
        "has_audio": audio["has_audio"],
        "objects_detected": objects_list,
        "ocr_text": ocr_text,
        "keyframes_count": len(keyframes),
        "kf_clip_scores": [round(s, 3) for s in kf_scores],
        "xai": {
            "gradcam_base64": gradcam_b64,
            "waterfall_base64": waterfall_b64,
            "shap": _shap_attribution(waterfall_scores, score_global, verdict),
        },
    }
