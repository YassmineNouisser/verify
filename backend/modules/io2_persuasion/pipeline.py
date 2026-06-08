"""Pipeline io2 — Visual Manipulation / Persuasion Detection (Malek).

ESPRIT-publication build: all signals come from local models that are **actually trained for the
task**, so the pipeline produces a meaningful verdict without any external API call.

  Text path (audio/image text → manipulation score):
    SO1-A  TrOCR (microsoft/trocr-base-printed)        — extracts on-screen text
    SO1-B  DistilRoBERTa fine-tuned for clickbait      — real binary classifier on clickbait
           (valurank/distilroberta-clickbait, drop-in replacement for Malek's missing weights)

  Image path (raw image → visual clickbait score):
    SO2    CLIP ViT-B/32 zero-shot                     — scores "sensational / clickbait thumbnail"
           vs "ordinary informational image" directly from text prompts

  Urgency path (regex + OCR boxes):
    SO4    EasyOCR + curated urgency-keyword regex     — replaces Malek's untrained DETR.
           Detects "LIMITED TIME", "ONLY 3 LEFT", percent-off, countdown patterns, etc.

  Fusion: ManipNet-style weighted sum (no trained fusion weights — heuristic).

The OpenAI vision backend (openai_vision.py) stays in the package for the chatbot module but is
not called from analyze_image unless IO2_USE_OPENAI=on is explicitly set.
"""
from __future__ import annotations

import base64
import io
import os
import re
import warnings
from typing import Optional

from backend.shared.device import DEVICE

warnings.filterwarnings("ignore")

# ─── Config ─────────────────────────────────────────────────────────────────
TROCR_MODEL = os.environ.get("IO2_TROCR_MODEL", "microsoft/trocr-base-printed")
# Real fine-tuned clickbait classifier (drop-in for Malek's missing so1b_roberta_weights.pt)
CLICKBAIT_MODEL = os.environ.get("IO2_CLICKBAIT_MODEL", "valurank/distilroberta-clickbait")
CLIP_MODEL = os.environ.get("IO2_CLIP_MODEL", "ViT-B-32")
CLIP_PRETRAINED = os.environ.get("IO2_CLIP_PRETRAINED", "openai")
ENABLE_TRANSLATION = os.environ.get("IO2_ENABLE_TRANSLATION", "auto")  # auto|off

USE_OPENAI = os.environ.get("IO2_USE_OPENAI", "off").strip().lower() in {"on", "1", "true", "yes"}

# Severity bands (per readme spec)
LABEL_BANDS = [
    (0.0, 0.4, "AUTHENTIC",            "#22C55E"),
    (0.4, 0.6, "SUSPECT",              "#F59E0B"),
    (0.6, 0.8, "MANIPULATIVE",         "#F97316"),
    (0.8, 1.01, "HIGHLY MANIPULATIVE", "#E53E3E"),
]

# Fusion weights (no trained ManipNet — text signal is the most reliable)
FUSION_WEIGHTS = {"nlp": 0.45, "clickbait": 0.30, "urgence": 0.25}

# ─── Urgency lexicon (EN + FR) ─────────────────────────────────────────────
# Each entry: (regex pattern, severity 0-1, label)
URGENCY_PATTERNS = [
    (r"\b(limited\s*time|temps\s*limit[ée]|offre\s*limit[ée])\b",           0.90, "limited-time"),
    (r"\b(only|seulement|plus\s*que|reste\s*plus\s*que)\s*\d+\s*(left|restant|en\s*stock)?\b", 0.85, "scarcity"),
    (r"\b(now|maintenant|d[ée]p[êe]chez|hurry|act\s*fast|vite|quick)\b",    0.55, "act-now"),
    (r"\b(buy\s*now|achetez|order\s*now|commandez|sign\s*up\s*now)\b",      0.65, "call-to-action"),
    (r"\b(today\s*only|aujourd['’]hui\s*seulement|24\s*h(ours)?\s*only)\b", 0.90, "today-only"),
    (r"\b(\d{1,2}\s*:\s*\d{2}(?:\s*:\s*\d{2})?)\b",                          0.50, "countdown"),
    (r"\b-?\d{1,2}\s*%\s*(off|de\s*r[ée]duction|discount|rabais)\b",         0.55, "percent-off"),
    (r"\b(free|gratuit|gratuite|free\s*shipping|livraison\s*gratuite)\b",   0.40, "free-claim"),
    (r"\b(?:exclusive|exclusif|exclusivit[ée])\b",                            0.45, "exclusivity"),
    (r"\b(?:guaranteed|garantie?|100\s*%\s*(?:guaranteed|garanti))\b",        0.50, "guarantee"),
    (r"\b(?:secret|miracle|miraculeux|magique|magical|unbelievable|incroyable)\b", 0.70, "sensational"),
    (r"\b(?:shocking|choquant|stunning|amazing|incredible|unreal)\b",        0.55, "sensational"),
    (r"!{2,}|\?{2,}",                                                         0.35, "excess-punctuation"),
    (r"\b(don['’]t\s*miss|ne\s*manquez\s*pas|ratez\s*pas)\b",               0.60, "fomo"),
    (r"\b(?:warning|attention|alert|alerte|urgent|emergency)\b",              0.55, "alarm"),
]

# CLIP zero-shot prompts for the visual-clickbait scorer
CLIP_POSITIVE_PROMPTS = [
    "a sensational clickbait advertisement thumbnail with bold text and urgent visuals",
    "a manipulative social-media advert with shock-value imagery",
    "a misleading promotional banner with persuasive call-to-action",
]
CLIP_NEGATIVE_PROMPTS = [
    "an ordinary informational photograph",
    "a neutral product photo on a plain background",
    "a candid amateur photograph with no advertising intent",
]

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
            f"Module io2 — missing ML dependencies ({e}). "
            "Install: pip install -r backend/requirements.txt"
        ) from e
    np, cv2, torch, nn, F, Image, plt = _np, _cv2, _torch, _nn, _F, _Image, _plt
    _HEAVY_DEPS_LOADED = True


# ─── Globals populated by init() ────────────────────────────────────────────
_trocr_processor = None
_trocr_model = None
_clickbait_tokenizer = None
_clickbait_model = None
_clickbait_fake_idx = 1  # which logit index corresponds to "clickbait/manipulative"
_clip_model = None
_clip_preprocess = None
_clip_tokenizer = None
_clip_positive_emb = None
_clip_negative_emb = None
_ocr_reader = None
_translator = None
LOADED = False
INFO: dict = {}


# ============================================================================
# INIT
# ============================================================================
def init() -> dict:
    global _trocr_processor, _trocr_model
    global _clickbait_tokenizer, _clickbait_model, _clickbait_fake_idx
    global _clip_model, _clip_preprocess, _clip_tokenizer, _clip_positive_emb, _clip_negative_emb
    global _ocr_reader, _translator
    global LOADED, INFO
    if LOADED:
        return INFO

    _ensure_heavy_deps()
    print(f"[io2] Device: {DEVICE}")

    # ─── 1. TrOCR (HuggingFace auto-download) ──────────────────────────────
    print(f"[io2] Loading TrOCR ({TROCR_MODEL})…")
    from transformers import TrOCRProcessor, VisionEncoderDecoderModel
    _trocr_processor = TrOCRProcessor.from_pretrained(TROCR_MODEL)
    _trocr_model = VisionEncoderDecoderModel.from_pretrained(TROCR_MODEL).to(DEVICE).eval()

    # ─── 2. Clickbait classifier — real pre-trained model ──────────────────
    print(f"[io2] Loading clickbait classifier ({CLICKBAIT_MODEL})…")
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
    _clickbait_tokenizer = AutoTokenizer.from_pretrained(CLICKBAIT_MODEL)
    _clickbait_model = AutoModelForSequenceClassification.from_pretrained(CLICKBAIT_MODEL).to(DEVICE).eval()
    # Detect which class index means "clickbait" (label names vary by checkpoint)
    id2label = getattr(_clickbait_model.config, "id2label", {}) or {}
    _clickbait_fake_idx = 1
    for idx, name in id2label.items():
        n = str(name).strip().lower()
        if any(k in n for k in ("clickbait", "click_bait", "manipulative", "fake", "spam", "label_1")):
            _clickbait_fake_idx = int(idx)
            break

    # ─── 3. CLIP ViT-B/32 zero-shot for visual clickbait ────────────────────
    print(f"[io2] Loading CLIP {CLIP_MODEL} ({CLIP_PRETRAINED}) for visual clickbait scoring…")
    import open_clip
    _clip_model, _, _clip_preprocess = open_clip.create_model_and_transforms(CLIP_MODEL, pretrained=CLIP_PRETRAINED)
    _clip_tokenizer = open_clip.get_tokenizer(CLIP_MODEL)
    _clip_model = _clip_model.to(DEVICE).eval()
    with torch.no_grad():
        pos = _clip_tokenizer(CLIP_POSITIVE_PROMPTS).to(DEVICE)
        neg = _clip_tokenizer(CLIP_NEGATIVE_PROMPTS).to(DEVICE)
        _clip_positive_emb = F.normalize(_clip_model.encode_text(pos), dim=-1)
        _clip_negative_emb = F.normalize(_clip_model.encode_text(neg), dim=-1)

    # ─── 4. EasyOCR for urgency-keyword localisation ────────────────────────
    print("[io2] Loading EasyOCR (en + fr) for urgency-keyword detection…")
    import easyocr
    _ocr_reader = easyocr.Reader(["en", "fr"], gpu=(DEVICE == "cuda"), verbose=False)

    # ─── 5. Optional translator (FR → EN) so the EN-only clickbait model gets EN ────
    # The HF pipeline API dropped the "translation" task in newer versions, so call the
    # MarianMT model directly. The tuple stored in _translator is (tokenizer, model).
    translator_status = "off"
    if ENABLE_TRANSLATION != "off":
        try:
            from transformers import MarianTokenizer, MarianMTModel
            tok = MarianTokenizer.from_pretrained("Helsinki-NLP/opus-mt-fr-en")
            mdl = MarianMTModel.from_pretrained("Helsinki-NLP/opus-mt-fr-en").to(DEVICE).eval()
            _translator = (tok, mdl)
            translator_status = "Helsinki-NLP/opus-mt-fr-en"
            print(f"[io2]   → {translator_status} loaded")
        except Exception as e:
            print(f"[io2]   → Translator unavailable ({type(e).__name__}: {e}) — text kept as is")
            translator_status = f"unavailable ({type(e).__name__})"

    INFO = {
        "device": DEVICE,
        "trocr": TROCR_MODEL,
        "clickbait_classifier": f"{CLICKBAIT_MODEL} (fake_idx={_clickbait_fake_idx})",
        "clip_zero_shot": f"open_clip {CLIP_MODEL} ({CLIP_PRETRAINED})",
        "urgency_detector": "EasyOCR + curated regex (EN + FR)",
        "fusion": "heuristic weighted sum (no trained ManipNet)",
        "translator": translator_status,
        "verdict_backend": "local (clickbait classifier + CLIP zero-shot + urgency regex)",
    }
    LOADED = True
    print(f"[io2] ✅ Pipeline io2 ready on {DEVICE}")
    return INFO


# ============================================================================
# SO1-A — TrOCR text extraction
# ============================================================================
def extract_text_trocr(pil_image) -> str:
    inputs = _trocr_processor(pil_image.convert("RGB"), return_tensors="pt").to(DEVICE)
    with torch.no_grad():
        gen_ids = _trocr_model.generate(inputs.pixel_values, max_length=128)
    return _trocr_processor.batch_decode(gen_ids, skip_special_tokens=True)[0].strip()


# ============================================================================
# SO1-B — Clickbait NLP classifier
# ============================================================================
def translate_to_english(text: str) -> str:
    if not text or _translator is None:
        return text
    if not re.search(r"[éèêëàâîïôöùûüç]|\b(le|la|les|un|une|des|et|ou|à|pour)\b", text.lower()):
        return text  # already English-ish
    try:
        tok, mdl = _translator
        enc = tok(text[:300], return_tensors="pt", truncation=True, max_length=128).to(DEVICE)
        with torch.no_grad():
            gen = mdl.generate(**enc, max_length=128)
        return tok.decode(gen[0], skip_special_tokens=True) or text
    except Exception:
        return text


def classify_text_clickbait(text: str) -> dict:
    if not text:
        return {"score": 0.0, "label": "No text", "text_en": ""}
    text_en = translate_to_english(text)
    enc = _clickbait_tokenizer(
        text_en[:512], max_length=128, padding="max_length", truncation=True, return_tensors="pt",
    )
    with torch.no_grad():
        logits = _clickbait_model(
            input_ids=enc["input_ids"].to(DEVICE),
            attention_mask=enc["attention_mask"].to(DEVICE),
        ).logits
        probs = F.softmax(logits, dim=-1)[0]
    score = float(probs[_clickbait_fake_idx].item())
    label = "Manipulator" if score >= 0.5 else "Neutral"
    return {"score": score, "label": label, "text_en": text_en}


# ============================================================================
# SO2 — Visual clickbait via CLIP zero-shot
# ============================================================================
def classify_clickbait_clip(pil_image) -> float:
    """Returns probability in [0,1] that the image looks like a clickbait/manipulative thumbnail."""
    with torch.no_grad():
        img = _clip_preprocess(pil_image.convert("RGB")).unsqueeze(0).to(DEVICE)
        img_emb = F.normalize(_clip_model.encode_image(img), dim=-1)
        # Mean similarity to each prompt bank
        sim_pos = (img_emb @ _clip_positive_emb.T).mean().item()
        sim_neg = (img_emb @ _clip_negative_emb.T).mean().item()
    # Softmax over the two means → calibrated probability
    a = float(np.exp(sim_pos * 100.0))
    b = float(np.exp(sim_neg * 100.0))
    return float(a / (a + b + 1e-8))


# ============================================================================
# SO4 — Urgency-keyword detection (EasyOCR + regex)
# ============================================================================
def detect_urgency_via_ocr(pil_image) -> tuple:
    """Returns (urgency_score, boxes) where boxes is a list of {class, score, box:[x1,y1,x2,y2]}.

    Method: EasyOCR extracts all visible text + bounding boxes; we test each piece against the
    URGENCY_PATTERNS list; matched fragments are emitted with their severity as score.
    """
    arr = np.asarray(pil_image.convert("RGB"))
    try:
        ocr = _ocr_reader.readtext(arr, detail=1, paragraph=False)
    except Exception:
        ocr = []

    boxes = []
    severities = []
    for bbox, text, conf in ocr:
        if conf < 0.35 or not text:
            continue
        txt_lower = text.lower().strip()
        for pat, sev, label in URGENCY_PATTERNS:
            if re.search(pat, txt_lower, re.IGNORECASE):
                xs = [p[0] for p in bbox]
                ys = [p[1] for p in bbox]
                boxes.append({
                    "class": label,
                    "score": round(float(sev), 3),
                    "box": [round(float(min(xs)), 1), round(float(min(ys)), 1),
                            round(float(max(xs)), 1), round(float(max(ys)), 1)],
                    "text": text.strip(),
                })
                severities.append(sev)
                break

    if not severities:
        urgency = 0.0
    else:
        # Combine: max severity, mildly boosted by count (more urgent cues = stronger signal)
        max_sev = max(severities)
        boost = min(0.20, 0.05 * (len(severities) - 1))
        urgency = float(min(1.0, max_sev + boost))
    return urgency, boxes


# ============================================================================
# Fusion → label
# ============================================================================
def manipnet_fuse(scores: dict) -> float:
    return (
        FUSION_WEIGHTS["nlp"] * scores["nlp"]
        + FUSION_WEIGHTS["clickbait"] * scores["clickbait"]
        + FUSION_WEIGHTS["urgence"] * scores["urgence"]
    )


def label_from_score(score: float) -> tuple:
    for lo, hi, label, color in LABEL_BANDS:
        if lo <= score < hi:
            return label, color
    return LABEL_BANDS[-1][2], LABEL_BANDS[-1][3]


# ============================================================================
# XAI — render OCR boxes with their urgency classification
# ============================================================================
def _fig_to_b64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, bbox_inches="tight", pad_inches=0.1)
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("ascii")


def render_bboxes(pil_image, boxes: list) -> Optional[str]:
    if not boxes:
        return None
    img = np.array(pil_image.convert("RGB"))
    palette = [(220, 38, 38), (245, 158, 11), (29, 78, 216), (124, 58, 237), (190, 24, 93)]
    for i, b in enumerate(boxes):
        x1, y1, x2, y2 = [int(round(v)) for v in b["box"]]
        color = palette[i % len(palette)]
        cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
        label = f"{b['class']} {b['score']:.2f}"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_DUPLEX, 0.5, 1)
        cv2.rectangle(img, (x1, max(0, y1 - th - 6)), (x1 + tw + 8, y1), color, -1)
        cv2.putText(img, label, (x1 + 4, y1 - 4), cv2.FONT_HERSHEY_DUPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.imshow(img); ax.axis("off")
    fig.subplots_adjust(0, 0, 1, 1)
    return _fig_to_b64(fig)


def clip_saliency_b64(pil_image) -> Optional[str]:
    """Gradient saliency map: backprop the (positive - negative) similarity score onto pixels."""
    try:
        img = _clip_preprocess(pil_image.convert("RGB")).unsqueeze(0).to(DEVICE)
        img.requires_grad_(True)
        img_emb = F.normalize(_clip_model.encode_image(img), dim=-1)
        score = (img_emb @ _clip_positive_emb.T).mean() - (img_emb @ _clip_negative_emb.T).mean()
        _clip_model.zero_grad()
        score.backward()
        sal = img.grad.detach().abs().squeeze(0).mean(0).cpu().numpy()  # H×W
        sal = (sal - sal.min()) / (sal.max() - sal.min() + 1e-8)
        # Upscale to image size and colourise
        orig = np.array(pil_image.convert("RGB"))
        H, W = orig.shape[:2]
        sal_up = cv2.resize(sal, (W, H), interpolation=cv2.INTER_CUBIC)
        heat = cv2.applyColorMap((sal_up * 255).astype(np.uint8), cv2.COLORMAP_INFERNO)
        heat = cv2.cvtColor(heat, cv2.COLOR_BGR2RGB)
        overlay = (0.55 * orig + 0.45 * heat).astype(np.uint8)
        fig, ax = plt.subplots(figsize=(5.4, 5.4))
        ax.imshow(overlay); ax.axis("off")
        fig.subplots_adjust(0, 0, 1, 1)
        return _fig_to_b64(fig)
    except Exception as e:
        print(f"[io2] CLIP saliency failed: {e}")
        return None


# ============================================================================
# VIDEO support — first frame
# ============================================================================
def extract_first_frame(video_path: str) -> "Image":
    cap = cv2.VideoCapture(video_path)
    ret, frame = cap.read()
    cap.release()
    if not ret:
        raise ValueError("Unable to read the first frame of the video.")
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb)


# ============================================================================
# PIPELINE — public entry point
# ============================================================================
def analyze_image(pil_image) -> dict:
    init()

    # 1. SO1-A — text extraction
    text_raw = extract_text_trocr(pil_image)

    # 2. SO1-B — clickbait NLP classifier (with optional FR → EN translation)
    nlp_result = classify_text_clickbait(text_raw)
    score_nlp = nlp_result["score"]

    # 3. SO2 — CLIP zero-shot for visual clickbait
    score_clickbait = classify_clickbait_clip(pil_image)

    # 4. SO4 — urgency-keyword detection (OCR + regex, replaces DETR)
    score_urgency, bboxes = detect_urgency_via_ocr(pil_image)

    # 5. Fusion
    scores = {"nlp": score_nlp, "clickbait": score_clickbait, "urgence": score_urgency}
    score_global = manipnet_fuse(scores)
    scores["manipnet"] = score_global

    # 6. Optional OpenAI override (off by default; preserved for the chatbot)
    explanation_source = "local"
    model_used = "local: clickbait classifier + CLIP zero-shot + urgency regex"
    techniques = sorted({b["class"] for b in bboxes})
    tone = "alarmist" if nlp_result["label"] != "Neutral" else "neutral"
    if USE_OPENAI:
        try:
            from . import openai_vision as ov
            if ov.available():
                ai = ov.analyze(pil_image, text_raw)
                if ai is not None:
                    score_global = round(ai["level"] / 100.0, 3)
                    tone = ai.get("text_tone", tone)
                    techniques = list(set(techniques + (ai.get("techniques") or [])))
                    scores["manipnet"] = score_global
                    explanation_source = "openai"
                    model_used = f"OpenAI · {ai.get('model', 'gpt-4o')}"
        except Exception as e:
            print(f"[io2] OpenAI override unavailable, staying on local: {e}")

    label, label_color = label_from_score(score_global)

    # Build explanation
    explain_bits = []
    pct_global = int(round(score_global * 100))
    explain_bits.append(
        f"The text extracted by TrOCR was scored as " +
        ("clickbait/manipulative" if score_nlp >= 0.5 else "neutral") +
        f" by the DistilRoBERTa classifier ({int(score_nlp*100)}%)."
    )
    explain_bits.append(
        f"CLIP zero-shot evaluated the image's framing as " +
        ("matching clickbait/sensational visual style" if score_clickbait >= 0.5 else "ordinary / non-sensational") +
        f" ({int(score_clickbait*100)}%)."
    )
    if bboxes:
        labels = sorted({b["class"] for b in bboxes})
        explain_bits.append(
            f"OCR + regex detected {len(bboxes)} urgency cue(s) on screen: {', '.join(labels)} "
            f"(severity {int(score_urgency*100)}%)."
        )
    else:
        explain_bits.append("No urgency / scarcity keywords were detected by OCR.")
    explain_bits.append(f"Fused manipulation score: {pct_global}% — label: {label}.")
    explanation = " ".join(explain_bits)

    # XAI — CLIP gradient saliency + OCR bbox overlay
    xai = {}
    try:
        saliency_b64 = clip_saliency_b64(pil_image)
        if saliency_b64:
            xai["gradient_saliency"] = saliency_b64
    except Exception as e:
        print(f"[io2][XAI] saliency failed: {e}")
    bbox_overlay = render_bboxes(pil_image, bboxes)
    if bbox_overlay:
        xai["bbox_overlay"] = bbox_overlay

    return {
        "score_global": round(score_global, 3),
        "label": label,
        "label_color": label_color,
        "scores_modules": {
            "nlp":       round(scores["nlp"], 3),
            "clickbait": round(scores["clickbait"], 3),
            "urgence":   round(score_urgency, 3),
            "manipnet":  round(score_global, 3),
        },
        "texte": {
            "extrait":    text_raw,
            "traduit_en": nlp_result.get("text_en", text_raw),
            "score_nlp":  round(scores["nlp"], 3),
            "label_nlp":  nlp_result["label"],
            "tone":       tone,
        },
        "techniques": techniques,
        "bounding_boxes": bboxes,
        "bbox_overlay_base64": bbox_overlay,
        "xai": xai,
        "explanation": explanation,
        "explanation_source": explanation_source,
        "model_used": model_used,
        "image_size": {"width": pil_image.size[0], "height": pil_image.size[1]},
    }


def analyze_video(video_path: str) -> dict:
    init()
    pil = extract_first_frame(video_path)
    result = analyze_image(pil)
    result["video_first_frame"] = True
    return result
