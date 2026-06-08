"""
Verify — Main backend.

A single FastAPI app that mounts the 6 modules. Run with:

    cd <repo>
    uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

Useful environment variables:
    LOAD_MODULES="io3"           # load only certain modules at startup
                                  # (default: all `active` modules)
    FORCE_DEVICE="cpu"           # force CPU even if a GPU is available
    YOLO_WEIGHTS=...             # see backend/modules/io3_coherence/pipeline.py
"""
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from backend.modules.io1_ai_generated import router as io1_router, init_models as io1_init, MODULE_INFO as io1_info
from backend.modules.io2_persuasion import router as io2_router, init_models as io2_init, MODULE_INFO as io2_info
from backend.modules.io3_coherence import router as io3_router, init_models as io3_init, MODULE_INFO as io3_info
from backend.modules.io4_photoshop import router as io4_router, init_models as io4_init, MODULE_INFO as io4_info
from backend.modules.io5_caption_fidelity import router as io5_router, init_models as io5_init, MODULE_INFO as io5_info
from backend.modules.io6_cosmetic_ads import router as io6_router, init_models as io6_init, MODULE_INFO as io6_info
from backend.modules.chatbot import router as chat_router, MODULE_INFO as chat_info

MODULES = [
    ("io1", io1_router, io1_init, io1_info),
    ("io2", io2_router, io2_init, io2_info),
    ("io3", io3_router, io3_init, io3_info),
    ("io4", io4_router, io4_init, io4_info),
    ("io5", io5_router, io5_init, io5_info),
    ("io6", io6_router, io6_init, io6_info),
]


def _load_set() -> set:
    """`LOAD_MODULES=io3,io1` → {'io3','io1'}. Empty → all `active` modules."""
    raw = os.environ.get("LOAD_MODULES", "").strip()
    if raw:
        return {m.strip().lower() for m in raw.split(",") if m.strip()}
    return {mid for mid, _r, _i, info in MODULES if info.get("status") == "active"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    to_load = _load_set()
    print(f"[startup] Modules to load: {sorted(to_load) or '(none)'}")
    for mid, _router, init, info in MODULES:
        if mid in to_load and info.get("status") == "active":
            print(f"[startup] → init {mid} ({info['name']})")
            try:
                init()
            except Exception as e:
                print(f"[startup] ⚠️  {mid} failed to load: {e}")
    yield
    print("[shutdown] bye")


app = FastAPI(
    title="Verify — Multi-Modal Disinformation Detection API",
    description="Unified backend for the 6 analysis modules of the Verify site.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — static front end served locally or via file://
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Mount module routers
for _mid, router, _init, _info in MODULES:
    app.include_router(router)

# Chatbot — no model to initialise, just mount the router.
app.include_router(chat_router)


# ────────── Root endpoints ──────────
@app.get("/api")
def api_root():
    return {
        "name": "Verify Backend",
        "version": "1.0.0",
        "modules": [info for _mid, _r, _i, info in MODULES] + [chat_info],
        "endpoints": {
            "global_health": "GET /health",
            "module_health": "GET /api/<module_id>/health",
            "openapi_docs":  "GET /docs",
        },
    }


@app.get("/health")
def health():
    """Global status — all modules at once."""
    statuses = []
    for mid, _r, _init, info in MODULES:
        try:
            from importlib import import_module
            mod_pl = import_module(f"backend.modules.{_module_pkg(mid)}.pipeline")
            loaded = getattr(mod_pl, "LOADED", False)
            mod_info = getattr(mod_pl, "INFO", {})
        except Exception:
            loaded = False
            mod_info = {}
        statuses.append({
            "id": mid,
            "name": info["name"],
            "owner": info.get("owner", "TBD"),
            "status": "ok" if loaded else info.get("status", "stub"),
            "info": mod_info,
        })
    return {"status": "ok", "modules": statuses}


def _module_pkg(mid: str) -> str:
    pkg_map = {
        "io1": "io1_ai_generated", "io2": "io2_persuasion",
        "io3": "io3_coherence",    "io4": "io4_photoshop",
        "io5": "io5_caption_fidelity", "io6": "io6_cosmetic_ads",
    }
    return pkg_map[mid]


# ────────── Static frontend (mounted LAST so /api/* and /health take precedence) ──────────
# When the project is run as one container (HuggingFace Space, Docker), serve the static
# HTML/CSS/JS from the repo root so the jury hits a single URL for everything. In local dev
# you can still use Live Server on :5500 alongside this — both work.
_FRONTEND_DIR = Path(__file__).resolve().parent.parent
if (_FRONTEND_DIR / "index.html").is_file():
    @app.get("/")
    def _index():
        return FileResponse(str(_FRONTEND_DIR / "index.html"))
    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIR), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), reload=True)
