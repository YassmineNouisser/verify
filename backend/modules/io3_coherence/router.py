"""FastAPI router for module io3 — Cross-Modal Coherence (Youssef)."""
import os
import shutil
import tempfile

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from PIL import Image

from . import pipeline as pl
from backend.shared.xai_narrative import attach_narrative

MODULE_INFO = {
    "id": "io3",
    "name": "Image–Caption Coherence",
    "owner": "Youssef",
    "status": "active",
    "endpoints": [
        "GET  /api/io3/health",
        "POST /api/io3/analyze/image",
        "POST /api/io3/analyze/video",
    ],
}

router = APIRouter(prefix="/api/io3", tags=["io3 — coherence"])


def init_models() -> dict:
    """Called once at app startup."""
    return pl.init()


@router.get("/health")
def health():
    return {
        "module": "io3",
        "status": "ok" if pl.LOADED else "loading",
        "info": pl.INFO if pl.LOADED else {},
    }


@router.post("/analyze/image")
async def analyze_image_endpoint(image: UploadFile = File(...), text: str = Form(...)):
    if not text.strip():
        raise HTTPException(400, "The 'text' field is required.")
    suffix = os.path.splitext(image.filename or "")[1].lower() or ".jpg"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        shutil.copyfileobj(image.file, tmp)
        tmp_path = tmp.name
    try:
        pil = Image.open(tmp_path).convert("RGB")
        res = pl.analyze_image(pil, tmp_path, text)
        attach_narrative(res, "io3", thumb=pil, extra_text=text)
        return JSONResponse(res)
    except RuntimeError as e:
        raise HTTPException(503, str(e))
    finally:
        try: os.unlink(tmp_path)
        except OSError: pass


@router.post("/analyze/video")
async def analyze_video_endpoint(video: UploadFile = File(...), text: str = Form(...)):
    if not text.strip():
        raise HTTPException(400, "The 'text' field is required.")
    suffix = os.path.splitext(video.filename or "")[1].lower() or ".mp4"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        shutil.copyfileobj(video.file, tmp)
        tmp_path = tmp.name
    try:
        res = pl.analyze_video(tmp_path, text)
        attach_narrative(res, "io3", extra_text=text)
        return JSONResponse(res)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(503, str(e))
    finally:
        try: os.unlink(tmp_path)
        except OSError: pass
