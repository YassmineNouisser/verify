# API Reference — Verify Backend

Base URL : `http://localhost:8000`

Swagger interactif : `http://localhost:8000/docs`

## Endpoints transverses

| Méthode | Route | Description |
|---|---|---|
| `GET` | `/` | Liste de tous les modules et leurs endpoints |
| `GET` | `/health` | Status global (tous les modules) |
| `GET` | `/docs` | Swagger UI (OpenAPI 3) |

## Endpoints par module

Toutes les routes d'analyse retournent du **JSON**. Les réponses contiennent un champ `verdict` (texte
court, ex: `"FAKE"`/`"REAL"`/`"MISLEADING"`), un champ `confidence_pct` (entier 0-100), une
`explanation` en anglais clair, et un sous-objet `xai` avec des heatmaps en base64 PNG.

### io1 — Fake Media Detection

```http
GET  /api/io1/health
POST /api/io1/analyze/image       # multipart: image=<file>, mode=auto|deepfake|ai
POST /api/io1/analyze/video       # multipart: video=<file>
```

**Modes** :
- `auto` (défaut) : détecte un visage et route vers deepfake ; sinon vers AI-image
- `deepfake` : force la détection face-deepfake (refuse si aucun visage trouvé)
- `ai` : force la détection AI-image (whole image), avec escalation 2-détecteurs

**Réponse (extrait)** :
```json
{
  "verdict": "FAKE",
  "verdict_label": "AI-generated image",
  "confidence_pct": 97,
  "prob_fake": 0.97, "prob_real": 0.03,
  "task": "image_ai_generated",
  "face_detected": true, "face_box": [x, y, w, h],
  "model_used": "io1_resnet50.pth + AI-image consensus",
  "xai": { "gradcam_overlay": "<base64 PNG>", "face_crop": "<base64>" },
  "explanation": "Two independent AI-image classifiers agree...",
  "narrative": { "headline": "AI-generated image", "summary": "...", "signals": [...] }
}
```

### io2 — Visual Manipulation / Persuasion

```http
GET  /api/io2/health
POST /api/io2/analyze/image       # multipart: image=<file>
POST /api/io2/analyze/video       # multipart: video=<file>  (analyse la 1ère frame)
```

**Verdicts** : `AUTHENTIC` · `SUSPECT` · `MANIPULATIVE` · `HIGHLY MANIPULATIVE`

**Réponse (extrait)** :
```json
{
  "score_global": 0.73,
  "label": "MANIPULATIVE", "label_color": "#F97316",
  "scores_modules": { "nlp": 0.85, "clickbait": 0.61, "urgence": 0.95, "manipnet": 0.73 },
  "texte": { "extrait": "LIMITED TIME ONLY", "tone": "alarmist", "label_nlp": "Manipulator" },
  "techniques": ["limited-time", "percent-off", "fomo"],
  "bounding_boxes": [{"class": "limited-time", "score": 0.9, "box": [120, 30, 280, 70]}],
  "xai": { "bbox_overlay": "<base64>", "gradient_saliency": "<base64>" }
}
```

### io3 — Image↔Caption Coherence

```http
GET  /api/io3/health
POST /api/io3/analyze/image       # multipart: image=<file>, text=<caption>
POST /api/io3/analyze/video       # multipart: video=<file>, text=<caption>
```

**Verdicts** : `COHERENT` (≥0.25) · `SUSPECT` (0.15-0.25) · `INCOHERENT` (<0.15)

**Réponse (extrait)** :
```json
{
  "verdict": "INCOHERENT",
  "score_global": 0.11,
  "scores": { "clip": 0.18, "sam": 0.22, "whisper": 0.5, "yolo": 0.0, "ocr": 0.0 },
  "objects_detected": ["dog", "person"],
  "ocr_text": "Welcome to the park",
  "xai": { "gradcam_base64": "<...>", "waterfall_base64": "<...>", "shap": { ... } }
}
```

### io4 — Image Tampering (Photoshop forensics)

```http
GET  /api/io4/health
POST /api/io4/analyze/image       # multipart: image=<file>
POST /api/io4/analyze/compare     # multipart: image=<suspect>, reference=<original>
```

**Verdicts** : `AUTHENTIC` · `FAKE` (sous-classe : `Inpainting` · `Copy-move` · `Splicing` · `Enhancement`)

**Réponse (extrait)** :
```json
{
  "verdict": "FAKE", "verdict_class": "Splicing",
  "predicted_class": "Splicing", "max_confidence": 0.78,
  "region": "top right",
  "ela_score": 0.67, "noise_score": 0.55, "jpeg_ghost_score": 0.42,
  "fused_score": 0.61, "signals_agreement": 2,
  "clues": ["ELA shows a compact bright patch", "JPEG ghost detected at quality 75"],
  "xai": { "tamper_mask_overlay": "<base64>", "gradcam_overlay": "<base64>" }
}
```

### io5 — Caption Fidelity

```http
GET  /api/io5/health
POST /api/io5/analyze             # multipart: file=<image>, text=<caption>
```

**Verdicts** : `FAITHFUL` · `PARTIAL` · `MISLEADING`

**Réponse (extrait)** :
```json
{
  "verdict": "MISLEADING", "verdict_color": "#E53E3E",
  "score": 0.21, "confidence": 0.92,
  "raw_clip_similarity": 0.13, "calibrated_similarity": 0.14,
  "ocr_overlap": 0.0, "tone_gap": 0.55,
  "phrase_breakdown": [
    {"phrase": "UFO landing white house", "score": 0.08, "supported": false}
  ],
  "unsupported_phrases": ["UFO landing white house", "Breaking news"],
  "xai": { "clip_saliency": "<base64>" }
}
```

### io6 — Cosmetic Ads Fact-Check

```http
GET  /api/io6/health
POST /api/io6/analyze/video       # multipart: video=<file>  (vidéo MP4 d'une pub cosmétique)
```

**Verdicts** : `RELIABLE` (trust_score≥50) · `MISLEADING` (<50)

**Réponse (extrait)** :
```json
{
  "global_verdict": "MISLEADING", "trust_score": 32.4,
  "transcript": "L'Oréal Revitalift reduces wrinkles by 40% in 7 days...",
  "language": "en",
  "claims": [
    {
      "claim": "reduces wrinkles by 40% in 7 days",
      "verdict": "FALSE", "confidence": 0.9, "severity": "high",
      "evidence": [
        {"source": "Decisive_PostProcessor", "rule_type": "FAUX_pattern",
         "description": "Time-bound claim without substantiation", "eu_article": "EU 655/2013 art. 4.4"}
      ],
      "eu_articles": ["EU 655/2013 art. 4.4", "EU 655/2013 art. 4.2"]
    }
  ],
  "stats": { "total": 8, "n_true": 3, "n_false": 4, "n_to_verify": 1 },
  "eu_articles_cited": ["EU 655/2013 art. 4.2", "EU 655/2013 art. 4.4"]
}
```

## Codes HTTP

| Code | Sens |
|---|---|
| `200` | OK — réponse JSON |
| `400` | Bad request — input manquant ou format invalide (ex: io5 sans `text`) |
| `500` | Erreur interne du pipeline — détails dans le message |
| `503` | Module pas encore prêt (en cours de chargement initial) |

## CORS

L'API autorise tous les origines (`Access-Control-Allow-Origin: *`) pour faciliter le développement
avec Live Server. En production, restreindre à votre domaine via le middleware FastAPI.
