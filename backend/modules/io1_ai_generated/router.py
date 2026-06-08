"""FastAPI router for module io1 — Fake media detection (Islem)."""
import os
import shutil
import tempfile

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from PIL import Image

from . import pipeline as pl
from backend.shared.xai_narrative import attach_narrative

MODULE_INFO = {
    "id": "io1",
    "name": "Fake Media Detection (deepfake & AI-generated)",
    "owner": "Islem",
    "status": "active",
    "endpoints": [
        "GET  /api/io1/health",
        "POST /api/io1/analyze/video                 (face deepfake — video)",
        "POST /api/io1/analyze/image  [mode=deepfake|ai|auto]",
    ],
}

router = APIRouter(prefix="/api/io1", tags=["io1 — deepfake"])


def init_models() -> dict:
    return pl.init()


@router.get("/health")
def health():
    return {
        "module": "io1",
        "status": "ok" if pl.LOADED else "loading",
        "info": pl.INFO if pl.LOADED else {},
    }


@router.post("/analyze/video")
async def analyze_video_endpoint(video: UploadFile = File(...)):
    suffix = os.path.splitext(video.filename or "")[1].lower() or ".mp4"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        shutil.copyfileobj(video.file, tmp)
        tmp_path = tmp.name
    try:
        res = pl.analyze_video(tmp_path)
        attach_narrative(res, "io1")
        return JSONResponse(res)
    except RuntimeError as e:
        raise HTTPException(503, str(e))
    except Exception as e:
        raise HTTPException(500, f"Pipeline error : {type(e).__name__}: {e}")
    finally:
        try: os.unlink(tmp_path)
        except OSError: pass


@router.post("/analyze/image")
async def analyze_image_endpoint(image: UploadFile = File(...), mode: str = Form("auto")):
    suffix = os.path.splitext(image.filename or "")[1].lower() or ".jpg"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        shutil.copyfileobj(image.file, tmp)
        tmp_path = tmp.name
    try:
        pil = Image.open(tmp_path).convert("RGB")
        res = pl.analyze_image(pil, mode=mode)
        attach_narrative(res, "io1")
        return JSONResponse(res)
    except RuntimeError as e:
        raise HTTPException(503, str(e))
    except Exception as e:
        raise HTTPException(500, f"Pipeline error : {type(e).__name__}: {e}")
    finally:
        try: os.unlink(tmp_path)
        except OSError: pass
