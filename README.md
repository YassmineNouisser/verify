---
title: Verify
emoji: 🔍
colorFrom: red
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
short_description: Multimodal disinformation detection — 6 ML modules + chatbot
license: apache-2.0
---

# Verify — Plateforme multimodale de détection de désinformation

## Description

**Verify** est une plateforme web qui vérifie l'authenticité de contenus visuels (image, vidéo, texte, publicité)
en analysant en parallèle **six dimensions** distinctes de la désinformation :

1. **io1 — Fake Media** : détection deepfake (face-swap) + images générées par IA (StyleGAN, DALL-E, Midjourney)
2. **io2 — Visual Manipulation** : détection des images persuasives/clickbait (texte alarmiste, urgence forcée, mise en scène)
3. **io3 — Image↔Caption Coherence** : vérifie la cohérence entre une image/vidéo et sa légende
4. **io4 — Image Tampering** : forensique photoshop (ELA + analyse de bruit + JPEG ghost)
5. **io5 — Caption Fidelity** : vérifie si une légende décrit fidèlement le contenu d'une image
6. **io6 — Cosmetic Ads Fact-Check** : audit réglementaire EU 655/2013 sur les publicités cosmétiques

Tous les modules tournent **100% en local** — aucune API externe n'est requise pour produire un verdict.
Le backend est une seule API FastAPI qui monte les 6 modules ; le frontend est statique (HTML + JavaScript).

## Technologies utilisées

| Couche | Stack |
|---|---|
| **Frontend** | HTML5 · CSS3 · Vanilla JavaScript (pas de framework) |
| **Backend** | Python 3.11 · FastAPI · Uvicorn |
| **IA / ML** | PyTorch · TorchVision · HuggingFace Transformers · open_clip · Ultralytics YOLO · OpenAI Whisper · EasyOCR · facenet-pytorch (MTCNN) · sentence-transformers |
| **Connaissances** | Pandas + OpenPyXL (knowledge base Excel pour io6) |
| **Forensique** | Pure NumPy + Pillow (io4 ELA / noise / JPEG ghost — sans modèle) |

## Prérequis

- **Python 3.11+** (testé sur 3.11.15)
- **ffmpeg** dans le PATH (utilisé par io3 et io6 pour extraire l'audio des vidéos)
- **~4 Go RAM disponible** (les 6 modules chargent ~3 Go de modèles en mémoire au démarrage)
- Premier démarrage : ~3-5 minutes (téléchargement automatique des modèles HuggingFace, ~2 Go)
- Démarrages suivants : ~30 secondes (tout est caché localement)

> ⚠️ **Modèles pré-entraînés non versionnés** : les poids `.pt`/`.pth` ne sont pas inclus dans le repo
> (taille > 250 Mo combinée + politique ESPRIT/GitHub). Voir la section **Installation** ci-dessous.

## Installation

```bash
# 1. Cloner le repo
git clone https://github.com/USERNAME/Esprit-PI-CLASSE-2526-Verify.git
cd Esprit-PI-CLASSE-2526-Verify

# 2. Créer l'environnement Python
python3.11 -m venv .venv
source .venv/bin/activate          # macOS / Linux
# .venv\Scripts\activate            # Windows

# 3. Installer les dépendances backend
pip install -r backend/requirements.txt

# 4. Télécharger les poids ResNet50 d'Islem (io1) — non versionnés
python scripts/download_models.py

# 5. (Optionnel) Configurer les variables d'environnement
cp .env.example .env
# Éditez .env si vous voulez activer le chatbot OpenAI ou ajuster un seuil.
```

## Lancement

```bash
# Backend (terminal 1)
uvicorn backend.main:app --host 0.0.0.0 --port 8000

# Frontend (terminal 2) — au choix :
python -m http.server 5500          # serveur HTTP statique
# OU : extension "Live Server" dans VSCode (clic-droit sur index.html → "Open with Live Server")
```

Ensuite ouvrez votre navigateur sur **http://127.0.0.1:5500/index.html**.

La doc Swagger de l'API est disponible sur **http://127.0.0.1:8000/docs**.

## Variables d'environnement

Voir [`.env.example`](.env.example) pour la liste complète. Les principales :

| Variable | Description |
|---|---|
| `LOAD_MODULES=io3,io1` | Limite quels modules sont chargés au démarrage (default : tous). Pratique en dev pour économiser la mémoire. |
| `FORCE_DEVICE=cpu` | Force le CPU même si un GPU est disponible. |
| `OPENAI_API_KEY=sk-...` | (Optionnel) Active le module chatbot uniquement. **N'affecte pas les verdicts** des 6 modules d'analyse. |
| `IO1_DEEPFAKE_THRESHOLD=0.60` | Seuil de décision FAKE pour l'ensemble ResNet50 d'Islem. |
| `IO4_ELA_QUALITY=90` | Qualité JPEG utilisée par ELA dans io4. |
| `IO6_WHISPER_MODEL=tiny` | Variante Whisper pour io6 (`tiny` rapide, `small`/`medium` plus précis). |

## Démo

- **Site déployé** : Non disponible (déploiement local uniquement pour cette livraison)
- **Vidéo de démonstration** : voir [`demo/`](demo/) (à fournir par l'équipe)
- **Diagrammes d'architecture** : voir [`docs/`](docs/)
- **Description commerciale** : [`Verify_Description_Commerciale.pdf`](Verify_Description_Commerciale.pdf)

## Performances des modèles

| Module | Backend | Performance | Source |
|--------|---------|------------|--------|
| io1 deepfake | ResNet50 ensemble (Islem) + MTCNN | ~97% acc sur FaceForensics | [`islem/`](islem/) |
| io1 AI-image | Consensus Organika/sdxl + umm-maybe (HF) | ~66% recall sur TPDNE, ~0% FP sur photos réelles | tuned empirically |
| io2 NLP | DistilRoBERTa fine-tuned clickbait | ~99% acc sur Webis Clickbait 2017 | `valurank/distilroberta-clickbait` |
| io2 visuel | CLIP ViT-B/32 zero-shot | calibration manuelle | OpenAI CLIP |
| io3 cohérence | CLIP ViT-L/14 + YOLOv8m fusion | F1 ~0.85 sur dataset interne | [`youssef/`](youssef/) |
| io4 forensique | ELA + Noise + JPEG ghost (sans modèle) | détection compositing/inpainting localisé | méthode classique |
| io5 fidelity | CLIP ViT-B/32 + EasyOCR | calibrée sur paires CC3M | sigmoid calibration |
| io6 cosmétique | Whisper + KB Excel + MiniLM semantic | 25 patterns / 33 fake claims / 145 ingrédients | [`yassmine/`](yassmine/) |

## Structure du projet

```
Verify/
├── README.md                       ← ce fichier
├── .env.example                    ← variables d'environnement
├── .gitignore
├── index.html, verifier.html, ...  ← frontend statique
├── assets/                         ← CSS, JS, images
├── backend/                        ← API FastAPI
│   ├── main.py                     ← entrypoint
│   ├── requirements.txt
│   ├── shared/                     ← code commun (device, narration XAI)
│   ├── data/                       ← KB Excel io6 (poids .pth téléchargés via script)
│   └── modules/
│       ├── io1_ai_generated/
│       ├── io2_persuasion/
│       ├── io3_coherence/
│       ├── io4_photoshop/
│       ├── io5_caption_fidelity/
│       └── io6_cosmetic_ads/
├── scripts/
│   └── download_models.py          ← téléchargement automatique des poids
├── docs/                           ← diagrammes architecture, doc API
├── demo/                           ← captures et vidéos de démo
├── islem/, malek/, youssef/, rayen/, yassmine/   ← notebooks et docs des contributeurs
└── ios images/                     ← jeu d'images de référence pour la démo
```

## Auteurs

| Nom | Module | Année | Tuteur |
|---|---|---|---|
| Yassmine Nouisser  | io6 — Cosmetic Ads Fact-Check + intégration globale | 2025-2026 | *(à compléter)* |
| Islem              | io1 — Fake Media Detection (deepfake + AI) | 2025-2026 | *(à compléter)* |
| Malek Tirellil     | io2 — Visual Manipulation Detection         | 2025-2026 | *(à compléter)* |
| Youssef            | io3 — Image-Caption Coherence               | 2025-2026 | *(à compléter)* |
| Rayen              | io4 — Image Tampering Detection             | 2025-2026 | *(à compléter)* |
| Maryem             | (contribution complémentaire)               | 2025-2026 | *(à compléter)* |

Classe : *(à compléter)* — Groupe : *(à compléter)*

---

## Documentation supplémentaire

- [`backend/README.md`](backend/README.md) — détails techniques de l'API
- [`docs/architecture.md`](docs/architecture.md) — architecture système et flux de données
- [`docs/api.md`](docs/api.md) — référence des endpoints
- [`docs/modules.md`](docs/modules.md) — détails par module
- [`AI_Investigate_Report_COMPLETE.pdf`](AI_Investigate_Report_COMPLETE.pdf) — rapport d'enquête initial
- [`Verify_Description_Commerciale.pdf`](Verify_Description_Commerciale.pdf) — pitch commercial

## Licence

Projet académique — ESPRIT School of Engineering, année universitaire 2025-2026.
