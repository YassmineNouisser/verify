"""
Pipeline IO6 — Cosmetic Ads Fact-Checking (Yassmine).

Inspired by notebook V3:
    Whisper (ASR) → YOLOv8n (detection) → EasyOCR (on-screen text) →
    Phi-3 (claim extraction, optional) → multi-source verification
    (KB regex + fake claims + ingredients DB + category rules + MiniLM
    semantic) → Decisive Post-Processor (EU 655/2013) → trust score.

Compliance: EU 655/2013 art. 4.2/4.4 + EU AI Act 2024 art. 13.

Heavy models (Phi-3, MiniLM) loaded on demand. If a dependency is
missing, we degrade gracefully (sentence-split extraction, no semantic
matching).
"""
from __future__ import annotations

import os
import re
import json
import shutil
import subprocess
import tempfile
import time
import warnings
from collections import Counter
from pathlib import Path
from typing import Optional

from backend.shared.device import DEVICE

warnings.filterwarnings("ignore")

# ─── Config ────────────────────────────────────────────────────────────────
# Speed-first defaults (the io6 pipeline runs Whisper + YOLO + OCR + (Phi-3) + MiniLM
# on a video — heavy on CPU). Override any of these with the IO6_* env vars for quality.
WHISPER_MODEL = os.environ.get("IO6_WHISPER_MODEL", "tiny")   # tiny ≈10× faster than "small"; bump to base/small/medium for accuracy
YOLO_WEIGHTS = os.environ.get("IO6_YOLO_WEIGHTS", "yolov8n.pt")
PHI3_MODEL = os.environ.get("IO6_PHI3_MODEL", "microsoft/Phi-3-mini-4k-instruct")
ENABLE_PHI3 = os.environ.get("IO6_ENABLE_PHI3", "off")        # LLM claim-extraction is the biggest CPU sink → off by default (regex fallback is used); set "auto" to re-enable
ENABLE_MINILM = os.environ.get("IO6_ENABLE_MINILM", "auto")  # "auto" | "off"
SEMANTIC_THRESHOLD = float(os.environ.get("IO6_SEMANTIC_THRESHOLD", "0.60"))
KB_PATH = os.environ.get("IO6_KB_PATH", str(Path(__file__).parent.parent.parent / "data" / "IO6_Base_Reference_V3_FULL.xlsx"))
FRAME_FPS = float(os.environ.get("IO6_FRAME_FPS", "0.7"))     # sample ~1 frame every 1.4 s
MAX_FRAMES = int(os.environ.get("IO6_MAX_FRAMES", "12"))      # cap OCR/YOLO work (was 30)

# ESPRIT publication: claim extraction stays 100% local (KB regex + MiniLM semantic match).
# The OpenAI path (openai_claims.py) is preserved for the chatbot but disabled here unless
# explicitly re-enabled with IO6_USE_OPENAI=on.
USE_OPENAI = os.environ.get("IO6_USE_OPENAI", "off").strip().lower() in {"on", "1", "true", "yes"}

# ─── Lazy heavy deps ───────────────────────────────────────────────────────
np = cv2 = torch = None
_HEAVY_DEPS_LOADED = False


def _ensure_heavy_deps():
    global np, cv2, torch, _HEAVY_DEPS_LOADED
    if _HEAVY_DEPS_LOADED:
        return
    try:
        import numpy as _np
        import cv2 as _cv2
        import torch as _torch
    except ImportError as e:
        raise RuntimeError(
            f"Module io6 — missing ML dependencies ({e}). "
            "Install: pip install -r backend/requirements.txt"
        ) from e
    np, cv2, torch = _np, _cv2, _torch
    _HEAVY_DEPS_LOADED = True


# ─── Globals populated by init() ───────────────────────────────────────────
_whisper_model = None
_yolo_model = None
_ocr_reader = None
_phi3_model = None
_phi3_tokenizer = None
_minilm_model = None
_kb = {}  # patterns, fake_claims, products, synonyms, category_rules, ingredients, brands, certifications
_known_fake_embeddings = None
LOADED = False
INFO: dict = {}


# ============================================================================
# KB LOADING — Excel reference from notebook
# ============================================================================
def _load_knowledge_base(path: str) -> dict:
    """Read the 8 sheets of the Excel KB used by the notebook."""
    if not os.path.exists(path):
        print(f"[io6] ⚠️  KB Excel not found: {path} — falling back to hardcoded patterns")
        return _hardcoded_kb_fallback()
    try:
        import pandas as pd
        kb = {}
        kb["patterns"] = pd.read_excel(path, sheet_name="Global_Patterns").dropna(subset=["pattern_regex"])
        kb["patterns"] = kb["patterns"][kb["patterns"]["pattern_id"].astype(str).str.match(r"^[A-Z]+\d+")]
        kb["fake_claims"] = pd.read_excel(path, sheet_name="Global_Fake_Claims").dropna(subset=["claim_text"])
        kb["products"] = pd.read_excel(path, sheet_name="Products").dropna(subset=["product_name"])
        kb["synonyms"] = pd.read_excel(path, sheet_name="Synonyms").dropna(subset=["canonical_form"])
        kb["category_rules"] = pd.read_excel(path, sheet_name="Category_Rules").dropna(subset=["category"])
        kb["ext_ingredients"] = pd.read_excel(path, sheet_name="Extended_Ingredients").dropna(subset=["ingredient_inci"])
        kb["ext_brands"] = pd.read_excel(path, sheet_name="Extended_Brands").dropna(subset=["brand_name"])
        kb["ext_certifications"] = pd.read_excel(path, sheet_name="Extended_Certifications").dropna(subset=["certification"])

        # Build ingredient set from products + extended sheet
        ingredients = set()
        for ings in kb["products"]["ingredients"].dropna():
            for ing in str(ings).split("|"):
                ing = ing.strip().lower()
                if ing and len(ing) > 2:
                    ingredients.add(ing)
        for ing in kb["ext_ingredients"]["ingredient_inci"].dropna():
            ingredients.add(str(ing).strip().lower())
        kb["ingredients"] = ingredients

        # Brand set
        kb["brands"] = set(str(b).strip().lower() for b in kb["ext_brands"]["brand_name"].dropna())
        for b in kb["products"]["brand"].dropna():
            kb["brands"].add(str(b).strip().lower())

        print(f"[io6]   → KB loaded: {len(kb['patterns'])} patterns, "
              f"{len(kb['fake_claims'])} fake claims, "
              f"{len(kb['products'])} products, "
              f"{len(kb['ingredients'])} ingredients, "
              f"{len(kb['brands'])} brands")
        return kb
    except Exception as e:
        print(f"[io6] ⚠️  Error reading KB: {e} — falling back to hardcoded patterns")
        return _hardcoded_kb_fallback()


def _hardcoded_kb_fallback() -> dict:
    """Minimal KB if Excel is unavailable. Just the Decisive Post-Processor patterns."""
    return {
        "patterns": None,
        "fake_claims": None,
        "products": None,
        "ingredients": set(),
        "brands": {"loreal", "l'oreal", "nivea", "garnier", "olay", "dior", "chanel", "vichy"},
        "category_rules": None,
        "synonyms": {},
        "ext_ingredients": None,
        "ext_certifications": None,
    }


# ============================================================================
# DECISIVE POST-PROCESSOR PATTERNS — embedded from notebook cell 47
# ============================================================================
FAUX_PATTERNS = [
    (r'\b\d+\s*(day|jour|hour|heure|week|semaine|month|mois)s?\b',
     "Time-bound claim without substantiation", "EU 655/2013 art. 4.4", "high", 0.85),
    (r'\bin\s*\d+\s*(day|jour|hour|heure|minute|second)',
     "Time-bound effect claim", "EU 655/2013 art. 4.4", "high", 0.85),
    (r'\ben\s*\d+\s*(jour|heure|seconde)',
     "Quantified time claim", "EU 655/2013 art. 4.4", "high", 0.85),
    (r'\d+\s*%\s*(more|less|reduction|fewer|moins|plus|de)?',
     "Unsubstantiated percentage claim", "EU 655/2013 art. 4.2", "high", 0.85),
    (r'(?:reduc|diminu|elimin)\w*\s*\d+\s*%',
     "Quantified reduction claim", "EU 655/2013 art. 4.2", "high", 0.90),
    (r'\b\d+\s*x?\s*(more|times|fois|plus)\b',
     "Multiplier without evidence", "EU 655/2013 art. 4.2", "high", 0.85),
    (r'\b(double|triple|quadruple)s?\b',
     "Comparative multiplier without evidence", "EU 655/2013 art. 4.2", "medium", 0.80),
    (r'\b(cure|guéri|heal|treat|soigne)\w*\s+(rid|wrink|tach|spot|acn|eczem)',
     "Medical claim forbidden in cosmetics", "EU 1223/2009", "critical", 0.95),
    (r'\b(remove|elimin|effac|erase|eradicat)\w*\s+(rid|wrink|tach|spot)',
     "Absolute removal claim forbidden", "EU 655/2013 art. 4.5", "critical", 0.92),
    (r'\b(miracle|miraculeu|magique|magical|magic)\w*',
     "Magical vocabulary forbidden", "EU 655/2013 art. 4.5", "high", 0.90),
    (r'\b(instantan|immédiat|immediate|instant)\w*',
     "Instantaneous effect not substantiated", "EU 655/2013 art. 4.4", "high", 0.80),
    (r'\b(meilleur|best|number\s*one|n[°o]\s*1|le\s*plus|the\s*most)\b',
     "Absolute superlative without evidence", "EU 655/2013 art. 4.5", "high", 0.80),
    (r'\b100\s*%\s*(natural|naturel|effective|efficac)',
     "Absolute percentage claim", "EU 655/2013 art. 4.2", "high", 0.90),
    (r'\b(forever|à\s*jamais|permanent)\s*(young|jeune|wrinkle.free)',
     "Permanent effect claim", "EU 655/2013 art. 4.4", "critical", 0.92),
    (r'\b(reverse|inverse|stop|arret)\s+(aging|vieill|temps|time)',
     "Reversal of aging biologically impossible", "EU 1223/2009", "critical", 0.94),
]

VRAI_PATTERNS = [
    (r'\b(nivea|l[\'\s]?oréal|loreal|garnier|olay|chanel|dior|maybelline|mac|estée\s*lauder|clinique|lancôme|sk[-\s]?ii|shiseido|biotherm|vichy|la\s*roche[-\s]?posay|avene|caudalie|kiehl|origins|fresh|tatcha|yves\s*saint\s*laurent|ysl|bobbi\s*brown|nars|laura\s*mercier|too\s*faced|urban\s*decay|benefit|smashbox|elizabeth\s*arden|revlon|cover\s*girl|max\s*factor|rimmel|bourjois)\b',
     "Verified cosmetic brand", "KB", "info", 0.78),
    (r'\b(coenzyme|q10|hyaluronic|hyaluronique|retinol|vitamin|peptide|ceramide|créatine|creatine|niacinamide|salicylic|glycolic|lactic|kojic|azelaic|ferulic|aha|bha|squalane|argan|jojoba|shea|aloe|collagen|elastin|caffeine|tocopherol)\b',
     "Verified INCI ingredient", "KB", "info", 0.80),
    (r'\b(skincare|skin\s*care|cosm[ée]tique|cosmetic|cream|crème|serum|sérum|lotion|gel|baume|balm|moisturizer|cleanser|toner|essence|mask|masque|sunscreen|spf)\b',
     "Cosmetic product category", "KB", "info", 0.72),
    (r'\b(?:fps|spf|ipf)\s*\d+\b',
     "SPF/FPS factual specification", "regulated", "info", 0.85),
    (r'\b(hydrat|nourish|nourrir|moisturiz|protect|protég|softens?|adoucit|smooth|lisse|illumin|brighten|even\s*out|matifie?)\w*\b',
     "Standard cosmetic claim allowed by EU 655/2013", "EU 655/2013", "info", 0.72),
    (r'\banti[-\s]?(rid|wrinkle|age|aging|âge)\w*',
     "Anti-aging product category (regulated)", "EU 655/2013", "info", 0.74),
    (r'\b(elastici[té][ty]?|firmness|fermeté|suppleness|souplesse|radiance|éclat|luminosity|luminosité)\b',
     "Standard cosmetic property", "KB", "info", 0.70),
    (r'\b(ecocert|cosmos|bdih|cruelty[-\s]?free|vegan|paraben[-\s]?free|sulfate[-\s]?free)\b',
     "Verified certification", "KB", "info", 0.78),
]

NUM_WORDS = {
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
    "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
    "ten": "10", "twenty": "20", "thirty": "30", "fifty": "50", "hundred": "100",
    "un": "1", "deux": "2", "trois": "3", "quatre": "4", "cinq": "5",
    "sept": "7", "huit": "8", "neuf": "9", "dix": "10",
}


# ============================================================================
# INIT — load all (lazy) models
# ============================================================================
def init() -> dict:
    global _whisper_model, _yolo_model, _ocr_reader
    global _phi3_model, _phi3_tokenizer, _minilm_model, _known_fake_embeddings
    global _kb, LOADED, INFO
    if LOADED:
        return INFO

    _ensure_heavy_deps()

    print(f"[io6] Device: {DEVICE}")
    print(f"[io6] Loading Whisper {WHISPER_MODEL}…")
    import whisper as _whisper
    _whisper_model = _whisper.load_model(WHISPER_MODEL, device=DEVICE)

    print(f"[io6] Loading YOLOv8 ({YOLO_WEIGHTS})…")
    from ultralytics import YOLO
    _yolo_model = YOLO(YOLO_WEIGHTS)
    _yolo_model.to(DEVICE)

    print("[io6] Loading EasyOCR (fr + en)…")
    import easyocr
    _ocr_reader = easyocr.Reader(["fr", "en"], gpu=(DEVICE == "cuda"), verbose=False)

    print(f"[io6] Loading Knowledge Base from {KB_PATH}…")
    _kb = _load_knowledge_base(KB_PATH)

    minilm_status = "off"
    if ENABLE_MINILM != "off":
        try:
            from sentence_transformers import SentenceTransformer
            _minilm_model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
            _minilm_model.to(DEVICE)
            if _kb.get("fake_claims") is not None:
                texts = _kb["fake_claims"]["claim_text"].dropna().tolist()
                _known_fake_embeddings = _minilm_model.encode(texts, convert_to_tensor=True, show_progress_bar=False)
                minilm_status = f"ready ({len(texts)} fake claims pre-encoded)"
            else:
                minilm_status = "ready (no KB fake claims to encode)"
            print(f"[io6]   → MiniLM {minilm_status}")
        except Exception as e:
            print(f"[io6]   → MiniLM unavailable ({e}) — semantic match disabled")
            minilm_status = f"unavailable ({type(e).__name__})"

    phi3_status = "off"
    if ENABLE_PHI3 != "off":
        try:
            from transformers import AutoTokenizer, AutoModelForCausalLM
            print(f"[io6] Loading Phi-3 ({PHI3_MODEL}) — may take 1–2 min…")
            _phi3_tokenizer = AutoTokenizer.from_pretrained(PHI3_MODEL)
            if _phi3_tokenizer.pad_token is None:
                _phi3_tokenizer.pad_token = _phi3_tokenizer.eos_token
            _phi3_model = AutoModelForCausalLM.from_pretrained(
                PHI3_MODEL,
                torch_dtype=torch.float16 if DEVICE == "cuda" else torch.float32,
                device_map="auto" if DEVICE == "cuda" else None,
                attn_implementation="eager",
                low_cpu_mem_usage=True,
            )
            _phi3_model.eval()
            phi3_status = "ready"
            print(f"[io6]   → Phi-3 loaded")
        except Exception as e:
            print(f"[io6]   → Phi-3 unavailable ({type(e).__name__}: {e}) — falling back to sentence-split")
            phi3_status = f"unavailable ({type(e).__name__})"

    INFO = {
        "device": DEVICE,
        "whisper": WHISPER_MODEL,
        "yolo": YOLO_WEIGHTS,
        "ocr": "easyocr (fr, en)",
        "kb": "loaded" if _kb.get("patterns") is not None else "fallback",
        "minilm": minilm_status,
        "phi3": phi3_status,
    }
    LOADED = True
    print(f"[io6] ✅ Pipeline IO6 ready on {DEVICE}\n")
    return INFO


# ============================================================================
# CLAIM EXTRACTION
# ============================================================================
def _generate_phi3(prompt: str, max_new: int = 300, temperature: float = 0.1) -> str:
    if _phi3_model is None:
        raise RuntimeError("Phi-3 not loaded")
    messages = [{"role": "user", "content": prompt}]
    encoded = _phi3_tokenizer.apply_chat_template(
        messages, return_tensors="pt", add_generation_prompt=True, return_dict=True
    )
    input_ids = encoded["input_ids"].to(DEVICE)
    attention_mask = encoded.get("attention_mask")
    if attention_mask is not None:
        attention_mask = attention_mask.to(DEVICE)
    with torch.no_grad():
        output = _phi3_model.generate(
            input_ids=input_ids, attention_mask=attention_mask,
            max_new_tokens=max_new, do_sample=(temperature > 0),
            temperature=max(temperature, 0.01),
            pad_token_id=_phi3_tokenizer.pad_token_id,
            eos_token_id=_phi3_tokenizer.eos_token_id,
        )
    return _phi3_tokenizer.decode(output[0][input_ids.shape[1]:], skip_special_tokens=True).strip()


def _extract_claims_phi3(transcript: str, ocr_texts: list) -> list:
    overlay = " | ".join(ocr_texts[:20])
    combined = f"AUDIO: {transcript[:600]}\nSCREEN: {overlay}"
    prompt = (
        f"Extract claims from this advertisement as JSON array.\n\n{combined}\n\n"
        'JSON format: [{"claim":"...","type":"efficacy","source":"audio"}]\n\nJSON:'
    )
    raw = _generate_phi3(prompt, max_new=600, temperature=0.1)
    return _parse_json_array(raw)


def _parse_json_array(text: str) -> list:
    text = re.sub(r"```(?:json)?\s*", "", text)
    text = re.sub(r"```", "", text)
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end == -1:
        return []
    js = text[start:end + 1].strip()
    try:
        out = json.loads(js)
        return [c for c in out if isinstance(c, dict) and "claim" in c]
    except json.JSONDecodeError:
        claims = []
        for obj in re.findall(r"\{[^{}]*\}", js):
            try:
                o = json.loads(obj)
                if "claim" in o:
                    claims.append(o)
            except json.JSONDecodeError:
                continue
        return claims


def _extract_claims_fallback(transcript: str, ocr_texts: list) -> list:
    """Sentence-split based extraction when Phi-3 isn't available."""
    claims = []
    seen = set()
    if transcript:
        for sent in re.split(r"(?<=[.!?])\s+|\n+", transcript):
            sent = sent.strip().rstrip(".!?,;:")
            if 4 <= len(sent.split()) <= 30 and sent.lower() not in seen:
                seen.add(sent.lower())
                claims.append({"claim": sent, "type": "general", "source": "audio"})
    for txt in ocr_texts[:15]:
        s = txt.strip().rstrip(".!?,;:")
        if 2 <= len(s.split()) <= 20 and s.lower() not in seen:
            seen.add(s.lower())
            claims.append({"claim": s, "type": "general", "source": "screen"})
    return claims[:20]


def _normalize_numbers(text: str) -> str:
    pattern = r"\b(" + "|".join(NUM_WORDS.keys()) + r")\b"
    text = re.sub(pattern, lambda m: NUM_WORDS.get(m.group(0).lower(), m.group(0)), text, flags=re.IGNORECASE)
    text = re.sub(r"(\d+)\s+times\s+more", r"\1x more", text, flags=re.IGNORECASE)
    text = re.sub(r"(\d+)\s+fois\s+plus", r"\1x plus", text, flags=re.IGNORECASE)
    return text


# ============================================================================
# VERIFICATION — KB rules + regex + semantic
# ============================================================================
def _verify_claim(claim_obj: dict) -> dict:
    """Combine KB checks + decisive post-processor for a single claim."""
    text = claim_obj.get("claim", "").strip()
    text_lower = text.lower()
    norm_text = _normalize_numbers(text_lower)

    evidence = []
    reasons = []
    verdict = "TO_VERIFY"
    confidence = 0.40
    severity = "info"
    eu_articles = set()

    # 1. KB regex patterns
    if _kb.get("patterns") is not None:
        for _, row in _kb["patterns"].iterrows():
            pat = str(row.get("pattern_regex", ""))
            if not pat or pat == "nan":
                continue
            try:
                if re.search(pat, norm_text):
                    sev = str(row.get("severity", "medium"))
                    desc = str(row.get("description", ""))
                    evidence.append({
                        "source": "KB.Global_Patterns",
                        "pattern_id": str(row.get("pattern_id", "")),
                        "category": str(row.get("category", "")),
                        "severity": sev,
                        "description": desc,
                    })
                    reasons.append(f"Pattern {row.get('pattern_id')} ({sev}): {desc}")
                    if sev in ("high", "critical"):
                        verdict = "FALSE"
                        confidence = max(confidence, 0.90)
                        severity = sev
            except re.error:
                continue

    # 2. Fake claims regex
    if _kb.get("fake_claims") is not None:
        for _, row in _kb["fake_claims"].iterrows():
            pat = str(row.get("regex_pattern", ""))
            if not pat or pat == "nan":
                continue
            try:
                if re.search(pat, norm_text):
                    sev = str(row.get("severity", "medium"))
                    evidence.append({
                        "source": "KB.Fake_Claims",
                        "claim_id": str(row.get("claim_id", "")),
                        "category": str(row.get("category", "")),
                        "severity": sev,
                        "matched_fake_claim": str(row.get("claim_text", "")),
                    })
                    reasons.append(f"Fake claim {row.get('claim_id')}: \"{row.get('claim_text')}\"")
                    verdict = "FALSE"
                    confidence = max(confidence, 0.92)
                    if sev in ("high", "critical"):
                        severity = sev
            except re.error:
                continue

    # 3. MiniLM semantic match
    if _minilm_model is not None and _known_fake_embeddings is not None:
        try:
            from sentence_transformers import util
            emb = _minilm_model.encode(text, convert_to_tensor=True)
            sims = util.cos_sim(emb, _known_fake_embeddings)[0]
            best_idx = int(sims.argmax())
            best = float(sims[best_idx])
            if best >= SEMANTIC_THRESHOLD:
                row = _kb["fake_claims"].iloc[best_idx]
                evidence.append({
                    "source": "MiniLM.Semantic",
                    "matched_claim_id": str(row.get("claim_id", "")),
                    "matched_claim_text": str(row.get("claim_text", "")),
                    "similarity": round(best, 3),
                    "severity": str(row.get("severity", "medium")),
                })
                reasons.append(f"Semantic similarity {best:.3f} with: \"{row.get('claim_text')}\"")
                if verdict == "TO_VERIFY":
                    verdict = "FALSE"
                    confidence = max(confidence, 0.75)
        except Exception as e:
            evidence.append({"source": "MiniLM.Semantic", "error": str(e)})

    # 4. Ingredients lookup
    found_ings = []
    for ing in _kb.get("ingredients", set()):
        if len(ing) > 3 and ing in text_lower:
            found_ings.append(ing)
    if found_ings:
        for ing in found_ings[:5]:
            evidence.append({"source": "KB.Ingredients", "ingredient": ing})
        reasons.append(f"KB ingredients: {', '.join(found_ings[:5])}")
        if verdict == "TO_VERIFY":
            verdict = "TRUE"
            confidence = max(confidence, 0.65)

    # 5. Brand lookup
    found_brands = [b for b in _kb.get("brands", set()) if b in text_lower and len(b) > 2]
    if found_brands:
        for b in found_brands[:3]:
            evidence.append({"source": "KB.Brands", "brand": b})
        if verdict == "TO_VERIFY":
            verdict = "TRUE"
            confidence = max(confidence, 0.60)

    # 6. Decisive Post-Processor (priority — encodes EU 655/2013)
    if not (verdict in ("TRUE", "FALSE") and confidence >= 0.70):
        # Try FAUX patterns first
        for pat, reason, eu_ref, sev, conf in FAUX_PATTERNS:
            if re.search(pat, norm_text, re.IGNORECASE):
                verdict = "FALSE"
                confidence = max(confidence, conf)
                severity = sev
                evidence.append({
                    "source": "Decisive_PostProcessor",
                    "rule_type": "FAUX_pattern",
                    "description": reason,
                    "eu_article": eu_ref,
                    "severity": sev,
                })
                reasons.append(f"[Decisive PP] {reason} ({eu_ref})")
                eu_articles.add(eu_ref)
                break

        if verdict != "FALSE":
            for pat, reason, eu_ref, sev, conf in VRAI_PATTERNS:
                if re.search(pat, norm_text, re.IGNORECASE):
                    if verdict == "TO_VERIFY":
                        verdict = "TRUE"
                        confidence = max(confidence, conf)
                    evidence.append({
                        "source": "Decisive_PostProcessor",
                        "rule_type": "VRAI_pattern",
                        "description": reason,
                        "eu_article": eu_ref,
                        "severity": sev,
                    })
                    reasons.append(f"[Decisive PP] {reason} ({eu_ref})")
                    if eu_ref != "KB":
                        eu_articles.add(eu_ref)
                    break

    # Collect all EU article refs from evidence
    for e in evidence:
        ref = e.get("eu_article")
        if ref and ref != "KB":
            eu_articles.add(ref)

    # ─── BINARY MODE — presumption of innocence ────────────────────────────
    # Without explicit negative evidence, we accept the claim (verdict TRUE).
    # Only claims that match a FAUX_pattern, a fake_claim, or the MiniLM
    # semantic similarity are set to FALSE. Neutral claims (generic text,
    # marketing fluff) stay TRUE by default.
    if verdict == "TO_VERIFY":
        verdict = "TRUE"
        confidence = max(confidence, 0.50)
        evidence.append({
            "source": "Decisive_PostProcessor",
            "rule_type": "VRAI_default",
            "description": "Neutral claim — no violation detected",
            "severity": "info",
        })
        reasons.append("[Default TRUE] No EU 655/2013 violation — claim accepted by default")

    return {
        "claim": text,
        "type": claim_obj.get("type", "general"),
        "source": claim_obj.get("source", "unknown"),
        "verdict": verdict,
        "confidence": round(confidence, 3),
        "severity": severity,
        "evidence": evidence,
        "reasons": reasons,
        "eu_articles": sorted(eu_articles),
    }


# ============================================================================
# VIDEO PROCESSING — ffmpeg + frames
# ============================================================================
def _ffmpeg_extract(video_path: str, work_dir: str) -> tuple:
    audio_path = os.path.join(work_dir, "audio.wav")
    frames_dir = os.path.join(work_dir, "frames")
    os.makedirs(frames_dir, exist_ok=True)

    subprocess.run(
        ["ffmpeg", "-y", "-i", video_path, "-vn", "-ar", "16000", "-ac", "1",
         audio_path, "-loglevel", "error"],
        check=False,
    )
    subprocess.run(
        ["ffmpeg", "-y", "-i", video_path, "-vf", f"fps={FRAME_FPS}",
         os.path.join(frames_dir, "frame_%04d.jpg"), "-loglevel", "error"],
        check=False,
    )
    frames = sorted(Path(frames_dir).glob("*.jpg"))
    if len(frames) > MAX_FRAMES:
        # Keep evenly-distributed sample
        step = len(frames) // MAX_FRAMES
        frames = frames[::step][:MAX_FRAMES]
    return audio_path, [str(f) for f in frames]


def _whisper_transcribe(audio_path: str) -> dict:
    if not os.path.exists(audio_path) or os.path.getsize(audio_path) < 1000:
        return {"text": "", "language": "unknown", "has_audio": False}
    res = _whisper_model.transcribe(audio_path, fp16=(DEVICE == "cuda"))
    return {
        "text": res["text"].strip(),
        "language": res.get("language", "unknown"),
        "has_audio": True,
    }


def _yolo_classes(frames: list) -> dict:
    counts = Counter()
    for fp in frames:
        results = _yolo_model(fp, conf=0.3, verbose=False, device=DEVICE)
        for r in results:
            for box in r.boxes:
                counts[r.names[int(box.cls)]] += 1
    return dict(counts)


def _ocr_unique_texts(frames: list) -> list:
    unique = set()
    for fp in frames:
        try:
            for _bbox, text, conf in _ocr_reader.readtext(fp, detail=1, paragraph=False):
                if conf >= 0.4 and len(text.strip()) >= 2:
                    unique.add(text.strip())
        except Exception:
            continue
    return sorted(unique)


# ============================================================================
# TRUST SCORE & GLOBAL VERDICT
# ============================================================================
def _compute_trust(verified: list) -> tuple:
    """Binary global verdict: RELIABLE or MISLEADING (no intermediate)."""
    if not verified:
        # Empty ad: no claim, considered reliable by default
        return 100.0, "RELIABLE"
    score_map = {"TRUE": 100.0, "FALSE": 0.0}
    pts = sum(score_map.get(c["verdict"], 50.0) * c["confidence"] for c in verified)
    norm = sum(c["confidence"] for c in verified) or 1.0
    trust = pts / norm
    # Simple threshold — majority of TRUE claims (>= 50 trust) → RELIABLE
    global_v = "RELIABLE" if trust >= 50 else "MISLEADING"
    return round(trust, 1), global_v


# ============================================================================
# PIPELINE — public entry point
# ============================================================================
def analyze_video(video_path: str) -> dict:
    init()
    timings = {}
    work_dir = tempfile.mkdtemp(prefix="io6_")
    try:
        # Step 1 — ffmpeg
        t0 = time.time()
        audio_path, frames = _ffmpeg_extract(video_path, work_dir)
        timings["ffmpeg"] = round(time.time() - t0, 1)

        # Step 2 — Whisper
        t0 = time.time()
        audio = _whisper_transcribe(audio_path)
        timings["whisper"] = round(time.time() - t0, 1)

        # Step 3 — YOLO
        t0 = time.time()
        yolo_classes = _yolo_classes(frames) if frames else {}
        timings["yolo"] = round(time.time() - t0, 1)

        # Step 4 — OCR
        t0 = time.time()
        ocr_texts = _ocr_unique_texts(frames) if frames else []
        timings["ocr"] = round(time.time() - t0, 1)

        # Step 5+6 — Claim extraction & EU-criteria verification.
        # Prefer OpenAI (much more reliable than the local Phi-3 / regex+KB path, which on CPU
        # often extracts nothing → "trust 100%"); fall back to the local path if no key.
        t0 = time.time()
        verified = None
        summary = ""
        extraction_method = None
        if USE_OPENAI:
            try:
                from . import openai_claims as ocm
                if ocm.available():
                    oc = ocm.evaluate(audio["text"], ocr_texts, yolo_classes)
                    if oc is not None:
                        verified = oc["claims"]
                        trust_score, global_verdict = oc["trust_score"], oc["global_verdict"]
                        all_eu = oc["eu_articles_cited"]
                        summary = oc.get("summary", "")
                        extraction_method = "openai"
            except Exception as e:
                print(f"[io6] OpenAI claim eval unavailable, falling back to the local path: {e}")
                verified = None
        if verified is None:
            if _phi3_model is not None:
                try:
                    raw_claims = _extract_claims_phi3(audio["text"], ocr_texts)
                    extraction_method = "phi3"
                except Exception as e:
                    print(f"[io6] Phi-3 extraction failed ({e}) — fallback")
                    raw_claims = _extract_claims_fallback(audio["text"], ocr_texts)
                    extraction_method = "fallback"
            else:
                raw_claims = _extract_claims_fallback(audio["text"], ocr_texts)
                extraction_method = "fallback"
            verified = []
            for c in raw_claims[:25]:
                try:
                    verified.append(_verify_claim(c))
                except Exception as e:
                    verified.append({
                        "claim": c.get("claim", ""), "verdict": "TO_VERIFY",
                        "confidence": 0.4, "severity": "info",
                        "evidence": [{"source": "ERROR", "description": str(e)}],
                        "reasons": [f"Verification error: {e}"],
                        "eu_articles": [],
                    })
            trust_score, global_verdict = _compute_trust(verified)
            all_eu = sorted({a for c in verified for a in c.get("eu_articles", [])})
        timings["claims"] = round(time.time() - t0, 1)

        n_true = sum(1 for c in verified if c["verdict"] == "TRUE")
        n_false = sum(1 for c in verified if c["verdict"] == "FALSE")
        n_to_verify = sum(1 for c in verified if c["verdict"] == "TO_VERIFY")

        return {
            "global_verdict": global_verdict,
            "trust_score": trust_score,
            "summary": summary,
            "transcript": audio["text"],
            "language": audio["language"],
            "has_audio": audio["has_audio"],
            "frames_count": len(frames),
            "yolo_classes": yolo_classes,
            "ocr_texts": ocr_texts,
            "claims": verified,
            "stats": {
                "total": len(verified),
                "n_true": n_true,
                "n_false": n_false,
                "n_to_verify": n_to_verify,
            },
            "eu_articles_cited": all_eu,
            "extraction_method": extraction_method,
            "timings_s": timings,
            "total_time_s": round(sum(timings.values()), 1),
        }
    finally:
        try:
            shutil.rmtree(work_dir, ignore_errors=True)
        except Exception:
            pass
