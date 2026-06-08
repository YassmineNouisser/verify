# Verify — Backend unifié

Une seule API FastAPI qui héberge les **6 modules** d'analyse de la plateforme Verify.

```
backend/
├── main.py                       ← entrypoint FastAPI (mount des 6 routers)
├── requirements.txt
├── shared/
│   └── device.py                 ← détection GPU/CPU partagée
└── modules/
    ├── io1_ai_generated/         ← stub (TBD)
    ├── io2_persuasion/           ← stub (TBD)
    ├── io3_coherence/            ← Youssef — V4.1, opérationnel
    │   ├── router.py
    │   └── pipeline.py
    ├── io4_photoshop/            ← stub (TBD)
    ├── io5_caption_fidelity/     ← stub (TBD)
    └── io6_cosmetic_ads/         ← stub (TBD)
```

## Lancement

```bash
# Depuis la racine du repo (pas depuis backend/)
pip install -r backend/requirements.txt
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

Premier démarrage : 30–60 s (chargement des modèles `active`).
La doc Swagger est à `http://localhost:8000/docs`.

## Endpoints

| Route | Description |
|---|---|
| `GET /` | Liste des modules + leurs endpoints |
| `GET /health` | Status global de tous les modules |
| `GET /docs` | Swagger UI auto-générée |

Par module :

| Module | Owner | Endpoints |
|---|---|---|
| **io1** AI-Generated Media | TBD | `GET /api/io1/health` · `POST /api/io1/analyze` *(501)* |
| **io2** Persuasion | TBD | `GET /api/io2/health` · `POST /api/io2/analyze` *(501)* |
| **io3** **Image-Caption Coherence** | **Youssef** | `GET /api/io3/health` · `POST /api/io3/analyze/image` · `POST /api/io3/analyze/video` |
| **io4** Photoshop Forensics | TBD | `GET /api/io4/health` · `POST /api/io4/analyze` *(501)* |
| **io5** Caption Fidelity | TBD | `GET /api/io5/health` · `POST /api/io5/analyze` *(501)* |
| **io6** Cosmetic Ads | TBD | `GET /api/io6/health` · `POST /api/io6/analyze` *(501)* |

## Variables d'environnement

| Variable | Description |
|---|---|
| `LOAD_MODULES=io3,io1` | Limite quels modules sont chargés au démarrage (par défaut : tous les modules `active`). Pratique en dev pour économiser la VRAM. |
| `FORCE_DEVICE=cpu` | Force le CPU même si un GPU est disponible. |
| `CLIP_FINETUNED_PATH=...` | (io3) Chemin vers le checkpoint CLIP fine-tuné (sinon CLIP de base). |
| `SAM_CHECKPOINT=...` | (io3) Chemin vers `sam_vit_b_01ec64.pth` (sinon fallback grille). |
| `YOLO_WEIGHTS=yolov8m.pt` | (io3) Poids YOLOv8m. |
| `WHISPER_MODEL=small` | (io3) Variante Whisper. |
| `ENABLE_SAM=off` | (io3) Désactiver SAM même si le checkpoint existe. |

## Comment ajouter un nouveau module

Chaque dossier `modules/ioX_*/` suit le même contrat :

1. **`pipeline.py`** — toutes les fonctions de chargement / inférence. Expose au minimum :
   ```python
   LOADED = False
   INFO = {}
   def init() -> dict: ...        # idempotent, charge les modèles
   def analyze_xxx(...) -> dict:  # tes endpoints d'analyse
   ```

2. **`router.py`** — un `APIRouter(prefix="/api/ioX")` avec :
   ```python
   MODULE_INFO = {"id": "ioX", "name": "...", "owner": "...", "status": "active", "endpoints": [...]}
   def init_models(): return pipeline.init()
   @router.get("/health")
   @router.post("/analyze")  # ou /analyze/image, /analyze/video, etc.
   ```

3. **`__init__.py`** — réexporter `router`, `init_models`, `MODULE_INFO`.

4. Quand tu passes le `status` de `"stub"` à `"active"` dans `MODULE_INFO`, le module sera chargé au démarrage.

5. Côté frontend, ajouter l'entrée correspondante dans `assets/js/coherence.js` (variable `MODULES`) ou créer un fichier JS dédié.

## Pré-requis système

- Python ≥ 3.10
- `ffmpeg` accessible dans le PATH (utilisé par io3 pour extraire l'audio des vidéos)
- GPU NVIDIA recommandé (≥ 4 Go VRAM) — fallback CPU automatique
