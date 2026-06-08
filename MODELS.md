# Verify — Models inventory

Exhaustive list of every model and trained weight file used by the Verify platform.
Total disk footprint after first run: **~4 Go** (cached in `~/.cache/huggingface/` and `~/.cache/torch/`).
Combined in-memory footprint when all modules are loaded: **~3 Go RAM**.

Files **with a download URL** = auto-fetched from HuggingFace Hub on first use (no manual setup).
Files **without** a URL = hosted on HuggingFace Hub by the Verify team (see `scripts/download_models.py`).

## io1 — Fake Media Detection (deepfake & AI-generated)

| Model | Type | Size | Source | Auto-download? |
|---|---|---|---|---|
| `io1_resnet50.pth` (Islem's `best_ResNet50.pth`) | ResNet50 fine-tuned for face-deepfake (idx 0=FAKE) | 94 Mo | HuggingFace Hub (Verify Dataset) | ⚙️ `scripts/download_models.py` |
| `io1_resnet50_deepfake.pth` (Islem's `resnet50_deepfake.pth` / Model X) | ResNet50 + Dropout+Linear head (idx 0=REAL) | 94 Mo | HuggingFace Hub (Verify Dataset) | ⚙️ `scripts/download_models.py` |
| **MTCNN** (`facenet-pytorch`) | Face detector (3 stages: PNet/RNet/ONet) | 6 Mo | embedded in `facenet-pytorch` pip package | ✅ pip install |
| **Organika/sdxl-detector** | ViT image classifier for SDXL/diffusion AI images | 86 Mo | [`Organika/sdxl-detector`](https://huggingface.co/Organika/sdxl-detector) | ✅ HuggingFace |
| **umm-maybe/AI-image-detector** | ViT image classifier (precision-tuned) | 86 Mo | [`umm-maybe/AI-image-detector`](https://huggingface.co/umm-maybe/AI-image-detector) | ✅ HuggingFace |

## io2 — Visual Manipulation / Persuasion

| Model | Type | Size | Source | Auto-download? |
|---|---|---|---|---|
| **microsoft/trocr-base-printed** | Vision-Encoder + GPT-2 Decoder (OCR for screen text) | 558 Mo | [`microsoft/trocr-base-printed`](https://huggingface.co/microsoft/trocr-base-printed) | ✅ HuggingFace |
| **valurank/distilroberta-clickbait** | DistilRoBERTa fine-tuned for clickbait detection (binary) | 330 Mo | [`valurank/distilroberta-clickbait`](https://huggingface.co/valurank/distilroberta-clickbait) | ✅ HuggingFace |
| **open_clip ViT-B-32** (openai pretrained) | CLIP for zero-shot "clickbait visual style" scoring | 150 Mo | [`openai/clip-vit-base-patch32`](https://huggingface.co/openai/clip-vit-base-patch32) | ✅ open_clip |
| **Helsinki-NLP/opus-mt-fr-en** | MarianMT FR→EN (so the EN-only clickbait model receives EN) | 300 Mo | [`Helsinki-NLP/opus-mt-fr-en`](https://huggingface.co/Helsinki-NLP/opus-mt-fr-en) | ✅ HuggingFace |
| **EasyOCR** (EN + FR) | Text detection + recognition (CRAFT + CRNN) | 100 Mo | embedded in `easyocr` pip package | ✅ pip install |

## io3 — Image-Caption Coherence

| Model | Type | Size | Source | Auto-download? |
|---|---|---|---|---|
| **open_clip ViT-L-14** (laion2b_s32b_b82k) | CLIP large for image↔text similarity | 890 Mo | [`laion/CLIP-ViT-L-14-laion2B-s32B-b82K`](https://huggingface.co/laion/CLIP-ViT-L-14-laion2B-s32B-b82K) | ✅ open_clip |
| **YOLOv8m** (`yolov8m.pt`) | Object detection — 80 COCO classes | 52 Mo | [Ultralytics releases](https://github.com/ultralytics/assets/releases) | ✅ ultralytics |
| **EasyOCR** (EN + FR) | reused from io2 | shared | — | ✅ |
| **Whisper small** (`small.pt`) | OpenAI Whisper audio transcription | 470 Mo | [`openai-whisper` pip package](https://github.com/openai/whisper) | ✅ pip install |
| **SAM ViT-B** (optional) | Segment Anything for region scoring | 375 Mo | [`sam_vit_b_01ec64.pth`](https://dl.fbaipublicfiles.com/segment_anything/sam_vit_b_01ec64.pth) | ⚙️ manual download (else 3×3 grid fallback) |

## io4 — Image Tampering (Photoshop forensics)

| Model | Type | Size | Source | Auto-download? |
|---|---|---|---|---|
| **None** (pure model-free forensics) | ELA + Noise residual + JPEG ghost | 0 Mo | implemented in [`backend/modules/io4_photoshop/forensics.py`](backend/modules/io4_photoshop/forensics.py) | ✅ pure NumPy |

## io5 — Caption Fidelity

| Model | Type | Size | Source | Auto-download? |
|---|---|---|---|---|
| **open_clip ViT-B-32** (openai) | CLIP for image↔caption + per-phrase scoring | shared with io2 | — | ✅ |
| **EasyOCR** (EN + FR) | reused from io2 | shared | — | ✅ |

## io6 — Cosmetic Ads Fact-Check

| Model | Type | Size | Source | Auto-download? |
|---|---|---|---|---|
| **Whisper tiny** | Audio transcription (rapid version for ads) | 75 Mo | [`openai-whisper` pip package](https://github.com/openai/whisper) | ✅ pip install |
| **YOLOv8n** (`yolov8n.pt`) | Object detection (lightweight) | 7 Mo | [Ultralytics releases](https://github.com/ultralytics/assets/releases) — versioned in repo | ✅ committed |
| **EasyOCR** (FR + EN) | reused from io2 | shared | — | ✅ |
| **paraphrase-multilingual-MiniLM-L12-v2** | Sentence embeddings (semantic match with KB fake claims) | 470 Mo | [`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2) | ✅ HuggingFace |
| **IO6_Base_Reference_V3_FULL.xlsx** (Yassmine's KB) | Regulatory knowledge base — 25 patterns, 33 fake claims, 145 ingredients, 93 brands | 33 Ko | versioned in `backend/data/` | ✅ committed |

## chatbot — Verify Assistant

| Service | Type | Size | Source | Auto-download? |
|---|---|---|---|---|
| **OpenAI gpt-4o-mini** | Topic-restricted assistant via OpenAI API | n/a (remote) | requires `OPENAI_API_KEY` env var | ☁️ remote API |

The chatbot is **the only component that hits an external API**. The 6 detection modules above
all run 100% locally. On HuggingFace Spaces the key is set as a "Secret" (encrypted, never in the code).

## Narrative layer (cross-module, post-processing)

| Service | Type | Source |
|---|---|---|
| **OpenAI gpt-4o-mini** | Rewrites every module's raw result into plain-English narrative | ☁️ remote API (optional — disable with `IO_XAI_NARRATIVE=off`) |

The narrative layer is **optional**: if `OPENAI_API_KEY` is not set, modules return their raw
local explanation only. Set `IO_XAI_NARRATIVE=off` to disable explicitly.

---

## How to obtain Islem's `.pth` weights

The two ResNet50 checkpoints used by io1 (`io1_resnet50.pth` and `io1_resnet50_deepfake.pth`) are
not versioned in this repo because each file weighs ~94 MB (GitHub's per-file limit is 100 MB but
combined size kills clone speed).

They are hosted as a private HuggingFace Dataset by the Verify team. To download them locally:

```bash
# Either: download via the helper script, with the URLs set in .env or exported
export IO1_RESNET50_URL=https://huggingface.co/datasets/<verify_user>/verify-weights/resolve/main/best_ResNet50.pth
export IO1_RESNET50_DEEPFAKE_URL=https://huggingface.co/datasets/<verify_user>/verify-weights/resolve/main/resnet50_deepfake.pth
python scripts/download_models.py

# Or, on a HuggingFace Space: the Dockerfile pulls them automatically using HUGGINGFACE_HUB_TOKEN
# (set as a Secret in Space settings → so the file stays private).
```

## Auto-download summary

After running `pip install -r backend/requirements.txt` and starting the backend once,
**12 of 14 components self-install** from public sources. Only Islem's 2 `.pth` files need a manual
step (the download script).
