"""FastAPI router for module io5 — Caption Fidelity."""
import os
import shutil
import tempfile

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from PIL import Image

from . import pipeline as pl
from backend.shared.xai_narrative import attach_narrative

MODULE_INFO = {
    "id": "io5",
    "name": "Caption Fidelity",
    "owner": "Verify team",
    "status": "active",
    "endpoints": [
        "GET  /api/io5/health",
        "POST /api/io5/analyze (image + caption)",
    ],
}

router = APIRouter(prefix="/api/io5", tags=["io5 — caption fidelity"])


def init_models() -> dict:
    return pl.init()


@router.get("/health")
def health():
    return {
        "module": "io5",
        "status": "ok" if pl.LOADED else "loading",
        "info": pl.INFO if pl.LOADED else {},
    }


@router.post("/analyze")
async def analyze_endpoint(file: UploadFile = File(...), text: str = Form(...)):
    suffix = os.path.splitext(file.filename or "")[1].lower() or ".jpg"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name
    try:
        pil = Image.open(tmp_path).convert("RGB")
        res = pl.analyze(pil, text)
        attach_narrative(res, "io5", thumb=pil)
        return JSONResponse(res)
    except RuntimeError as e:
        raise HTTPException(503, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Pipeline error: {type(e).__name__}: {e}")
    finally:
        try: os.unlink(tmp_path)
        except OSError: pass
