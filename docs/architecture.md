# Architecture — Verify

## Vue d'ensemble

Verify est une **architecture en deux couches** strictement découplées :

- **Frontend statique** (HTML/CSS/JavaScript vanilla, servi sur le port 5500)
- **Backend FastAPI** (Python, port 8000) qui héberge 6 modules ML indépendants

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                            NAVIGATEUR (utilisateur)                          │
│                       index.html → verifier-module.html                      │
└─────────────────────────────┬────────────────────────────────────────────────┘
                              │  HTTP (multipart/form-data)
                              ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                       FRONTEND STATIQUE (Live Server :5500)                  │
│              HTML · CSS · JavaScript (pas de framework, pas de build)        │
└─────────────────────────────┬────────────────────────────────────────────────┘
                              │  fetch(`http://localhost:8000/api/ioN/analyze/*`)
                              ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                    BACKEND FastAPI (uvicorn :8000)                           │
│                                                                              │
│   ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────┐  │
│   │ io1      │ │ io2      │ │ io3      │ │ io4      │ │ io5      │ │ io6  │  │
│   │ ResNet50 │ │ TrOCR +  │ │ CLIP +   │ │ ELA +    │ │ CLIP +   │ │ KB + │  │
│   │ + MTCNN  │ │ DistilR. │ │ YOLO +   │ │ Noise +  │ │ EasyOCR  │ │ Whisp│  │
│   │ + Org/UM │ │ + CLIP   │ │ Whisper  │ │ JPEG-G   │ │          │ │ +YOLO│  │
│   └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────┘  │
│        │            │            │            │            │           │     │
│        └────────────┴────────────┼────────────┴────────────┴───────────┘     │
│                                  ▼                                           │
│              backend/shared/ (device.py · xai_narrative.py)                  │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                ┌─────────────────────────────┐
                │  Hugging Face Hub (read-only │  ← cache local après 1er run
                │  download des modèles)       │
                └─────────────────────────────┘
```

## Flux d'une requête type

Exemple : l'utilisateur veut vérifier qu'une image n'est pas un deepfake.

1. **Navigateur** : l'utilisateur ouvre `verifier-module.html?m=io1`, glisse-dépose une image, clique "Analyze".
2. **JavaScript** (`assets/js/synthesis.js`) : construit un `FormData` `{image, mode: "deepfake"}`, fait
   `fetch("http://localhost:8000/api/io1/analyze/image", { method: POST, body: formData })`.
3. **FastAPI router** ([`backend/modules/io1_ai_generated/router.py`](../backend/modules/io1_ai_generated/router.py))
   reçoit la requête, sauve temporairement le fichier, appelle `pipeline.analyze_image(pil, mode)`.
4. **Pipeline** ([`backend/modules/io1_ai_generated/pipeline.py`](../backend/modules/io1_ai_generated/pipeline.py)) :
   - MTCNN détecte le visage
   - ResNet50 ensemble (best_ResNet50 + resnet50_deepfake) prédit `prob_fake`
   - Si `mode="ai"` ou `mode="auto"`, on appelle aussi le **consensus AI** (Organika + umm-maybe)
   - On agrège et on renvoie un dict avec verdict, scores, Grad-CAM heatmap (base64), explication
5. **Réponse JSON** : le frontend reçoit la réponse et affiche le verdict, la confiance, le heatmap.

## Choix d'architecture

### Pourquoi pas de framework frontend ?

- Le frontend est essentiellement un **mince enrobage UI autour de l'API** : drag-drop, bouton, JSON → HTML.
- Pas de SPA, pas de state global complexe, pas de build pipeline → 0 dépendance npm.
- Permet à n'importe quel évaluateur de **servir le site avec `python -m http.server`**.

### Pourquoi un backend unifié plutôt que 6 microservices ?

- Les 6 modules **partagent des modèles lourds** (CLIP est utilisé par io2, io3, io5) — mutualiser la
  RAM dans un seul process économise ~2 Go.
- Démarrage / déploiement plus simple : **un seul `uvicorn` à lancer**.
- L'isolation est assurée par les sous-paquets Python (`backend/modules/ioN_*`).

### Pourquoi 100% local (pas d'API LLM dans le verdict) ?

- **Exigence ESPRIT** : les projets étudiants doivent fonctionner sans dépendre d'un service tiers payant.
- **Reproductibilité** : un évaluateur peut cloner et tester sans avoir de clé API.
- La **clé OpenAI optionnelle** (`OPENAI_API_KEY`) n'est utilisée que par le module **chatbot**, pas
  par les 6 verdicts.

## Carte des modèles utilisés

| Modèle | Taille | Source | Utilisé par |
|---|---|---|---|
| `io1_resnet50.pth` (best_ResNet50, Islem) | 94 Mo | hébergé hors-repo (téléchargé via `scripts/download_models.py`) | io1 |
| `io1_resnet50_deepfake.pth` (Model X, Islem) | 94 Mo | idem | io1 |
| `Organika/sdxl-detector` | 86 Mo | HuggingFace auto-download | io1 |
| `umm-maybe/AI-image-detector` | 86 Mo | HuggingFace auto-download | io1 |
| MTCNN (facenet-pytorch) | 6 Mo | pip package | io1 |
| `microsoft/trocr-base-printed` | 558 Mo | HuggingFace auto-download | io2 |
| `valurank/distilroberta-clickbait` | 330 Mo | HuggingFace auto-download | io2 |
| CLIP `ViT-B-32` (openai) | 150 Mo | open_clip auto-download | io2, io5 |
| `Helsinki-NLP/opus-mt-fr-en` | 300 Mo | HuggingFace auto-download | io2 |
| CLIP `ViT-L-14` (laion2b) | 890 Mo | open_clip auto-download | io3 |
| `yolov8m.pt` | 52 Mo | versionné dans le repo (Ultralytics) | io3 |
| `yolov8n.pt` | 7 Mo | versionné dans le repo (Ultralytics) | io6 |
| EasyOCR (en+fr) | 100 Mo | auto-download | io2, io3, io5, io6 |
| Whisper `small` | 470 Mo | auto-download | io3 |
| Whisper `tiny` | 75 Mo | auto-download | io6 |
| `paraphrase-multilingual-MiniLM-L12-v2` | 470 Mo | auto-download | io6 |

**Total disque après premier run** : ~4 Go (cache HF dans `~/.cache/huggingface/`).
