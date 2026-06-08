"""FastAPI router for module io6 — Cosmetic Ads Fact-Checking (Yassmine)."""
import os
import shutil
import tempfile

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from . import pipeline as pl
from backend.shared.xai_narrative import attach_narrative

MODULE_INFO = {
    "id": "io6",
    "name": "Cosmetic Ads Fact-Check",
    "owner": "Yassmine",
    "status": "active",
    "endpoints": [
        "GET  /api/io6/health",
        "POST /api/io6/analyze/video",
    ],
}

router = APIRouter(prefix="/api/io6", tags=["io6 — cosmetic ads"])


def init_models() -> dict:
    """Called once at app startup."""
    return pl.init()


@router.get("/health")
def health():
    return {
        "module": "io6",
        "status": "ok" if pl.LOADED else "loading",
        "info": pl.INFO if pl.LOADED else {},
    }


@router.post("/analyze/video")
async def analyze_video_endpoint(video: UploadFile = File(...)):
    """Analyze a cosmetics advertising video to detect misleading claims."""
    suffix = os.path.splitext(video.filename or "")[1].lower() or ".mp4"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        shutil.copyfileobj(video.file, tmp)
        tmp_path = tmp.name
    try:
        res = pl.analyze_video(tmp_path)
        attach_narrative(res, "io6")
        return JSONResponse(res)
    except RuntimeError as e:
        raise HTTPException(503, str(e))
    except Exception as e:
        raise HTTPException(500, f"Pipeline error : {type(e).__name__}: {e}")
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
