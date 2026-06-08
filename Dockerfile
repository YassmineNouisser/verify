# ─── Verify — single-container deployment for HuggingFace Spaces ────────────
# Serves the FastAPI backend (6 detection modules + chatbot) AND the static frontend
# from the same container, on port 7860 (HuggingFace Spaces standard).
#
# Pre-downloads the heavy HuggingFace models at BUILD time so the Space cold-start
# stays under ~60 s instead of ~10 min on first user request.
#
# Required Space "Secrets" (set in Space Settings → Variables and secrets):
#   OPENAI_API_KEY              for the chatbot module (optional but recommended)
#   IO1_RESNET50_URL            HF dataset URL for Islem's best_ResNet50.pth
#   IO1_RESNET50_DEEPFAKE_URL   HF dataset URL for Islem's resnet50_deepfake.pth
#   HUGGINGFACE_HUB_TOKEN       only if the weights dataset is private

FROM python:3.11-slim

# ─── System packages ────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        libgl1 \
        libglib2.0-0 \
        build-essential \
        wget \
        curl \
    && rm -rf /var/lib/apt/lists/*

# ─── Layout & user ──────────────────────────────────────────────────────────
# HF Spaces runs the container as a non-root user with UID 1000.
RUN useradd -m -u 1000 verify
USER verify
WORKDIR /home/verify/app

# Caches inside the user's home so HF Spaces persistent storage (if enabled) keeps them.
ENV HOME=/home/verify \
    HF_HOME=/home/verify/.cache/huggingface \
    TORCH_HOME=/home/verify/.cache/torch \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# ─── Python dependencies (cached layer) ─────────────────────────────────────
COPY --chown=verify:verify backend/requirements.txt backend/requirements.txt
RUN pip install --user --upgrade pip \
 && pip install --user -r backend/requirements.txt

ENV PATH="/home/verify/.local/bin:${PATH}"

# ─── Pre-warm the HuggingFace cache during build (saves cold-start time) ────
# This pulls the heaviest models so the first user request doesn't trigger a 5-minute
# download. Each line is independent — comment out any model you want to lazy-load.
RUN python -c "\
from open_clip import create_model_and_transforms, get_tokenizer; \
create_model_and_transforms('ViT-B-32', pretrained='openai'); \
create_model_and_transforms('ViT-L-14', pretrained='laion2b_s32b_b82k'); \
print('CLIP models cached')" \
 && python -c "\
from transformers import AutoTokenizer, AutoModelForSequenceClassification, \
    AutoModelForImageClassification, AutoImageProcessor, \
    TrOCRProcessor, VisionEncoderDecoderModel, MarianTokenizer, MarianMTModel; \
TrOCRProcessor.from_pretrained('microsoft/trocr-base-printed'); \
VisionEncoderDecoderModel.from_pretrained('microsoft/trocr-base-printed'); \
AutoTokenizer.from_pretrained('valurank/distilroberta-clickbait'); \
AutoModelForSequenceClassification.from_pretrained('valurank/distilroberta-clickbait'); \
AutoImageProcessor.from_pretrained('Organika/sdxl-detector'); \
AutoModelForImageClassification.from_pretrained('Organika/sdxl-detector'); \
AutoImageProcessor.from_pretrained('umm-maybe/AI-image-detector'); \
AutoModelForImageClassification.from_pretrained('umm-maybe/AI-image-detector'); \
MarianTokenizer.from_pretrained('Helsinki-NLP/opus-mt-fr-en'); \
MarianMTModel.from_pretrained('Helsinki-NLP/opus-mt-fr-en'); \
print('HF transformers cached')" \
 && python -c "\
import whisper; whisper.load_model('tiny'); whisper.load_model('small'); \
print('Whisper cached')" \
 && python -c "\
from sentence_transformers import SentenceTransformer; \
SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'); \
print('MiniLM cached')"

# ─── EasyOCR models (download to a known place) ─────────────────────────────
RUN python -c "\
import easyocr; easyocr.Reader(['en', 'fr'], gpu=False, verbose=False); \
print('EasyOCR models cached')"

# ─── Application code ───────────────────────────────────────────────────────
COPY --chown=verify:verify . .

# ─── Pull Islem's .pth weights (private HF Dataset) ─────────────────────────
# The download script reads IO1_RESNET50_URL & IO1_RESNET50_DEEPFAKE_URL from env.
# Failing silently here keeps `docker build` reproducible without the secrets — the
# runtime will retry on startup using the Space's Secrets.
RUN python scripts/download_models.py || echo "[build] weights not downloaded (will retry at runtime)"

# ─── Runtime ────────────────────────────────────────────────────────────────
EXPOSE 7860
ENV PORT=7860

# Use a startup wrapper so we can retry the weights download with the Space secrets
# (which are NOT available during `docker build` — only at runtime).
CMD ["bash", "-c", "python scripts/download_models.py || true && uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
