"""FastAPI router for module io4 — Image Tampering Detection (Rayen)."""
import os
import shutil
import tempfile

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from PIL import Image

from . import pipeline as pl
from backend.shared.xai_narrative import attach_narrative

MODULE_INFO = {
    "id": "io4",
    "name": "Image Tampering Detection",
    "owner": "Rayen",
    "status": "active",
    "endpoints": [
        "GET  /api/io4/health",
        "POST /api/io4/analyze/image",
        "POST /api/io4/analyze/compare",
    ],
}

router = APIRouter(prefix="/api/io4", tags=["io4 — tampering"])


def init_models() -> dict:
    return pl.init()


@router.get("/health")
def health():
    return {
        "module": "io4",
        "status": "ok" if pl.LOADED else "loading",
        "info": pl.INFO if pl.LOADED else {},
    }


@router.post("/analyze/image")
async def analyze_image_endpoint(image: UploadFile = File(...)):
    suffix = os.path.splitext(image.filename or "")[1].lower() or ".jpg"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        shutil.copyfileobj(image.file, tmp)
        tmp_path = tmp.name
    try:
        pil = Image.open(tmp_path).convert("RGB")
        res = pl.analyze_image(pil)
        attach_narrative(res, "io4", thumb=pil)
        return JSONResponse(res)
    except RuntimeError as e:
        raise HTTPException(503, str(e))
    except Exception as e:
        raise HTTPException(500, f"Pipeline error: {type(e).__name__}: {e}")
    finally:
        try: os.unlink(tmp_path)
        except OSError: pass


@router.post("/analyze/compare")
async def analyze_compare_endpoint(image: UploadFile = File(...), reference: UploadFile = File(...)):
    """Compare a *suspect* image (`image`) against a known *original* (`reference`)."""
    paths = []
    try:
        for up in (image, reference):
            suffix = os.path.splitext(up.filename or "")[1].lower() or ".jpg"
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                shutil.copyfileobj(up.file, tmp)
                paths.append(tmp.name)
        sus = Image.open(paths[0]).convert("RGB")
        ref = Image.open(paths[1]).convert("RGB")
        res = pl.compare_images(ref, sus)
        attach_narrative(res, "io4", thumb=sus)
        return JSONResponse(res)
    except RuntimeError as e:
        raise HTTPException(503, str(e))
    except Exception as e:
        raise HTTPException(500, f"Pipeline error: {type(e).__name__}: {e}")
    finally:
        for p in paths:
            try: os.unlink(p)
            except OSError: pass
