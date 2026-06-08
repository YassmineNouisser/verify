# Modules — Détails techniques

Chaque module est un sous-paquet `backend/modules/ioN_*/` indépendant. Tous suivent le même contrat :

- `pipeline.py` — fonctions de chargement (`init()`) et d'inférence (`analyze_*`)
- `router.py` — `APIRouter` FastAPI exposant les endpoints
- `__init__.py` — réexporte `router`, `init_models`, `MODULE_INFO`

---

## io1 — Fake Media Detection (deepfake & AI-generated)

**Responsable** : Islem · **Statut** : production

### Pipeline
1. **MTCNN** (facenet-pytorch) — détection visage, crop 224×224 avec marge 20px (matche exactement
   l'entraînement d'Islem)
2. **ResNet50 ensemble** — moyenne des `prob_fake` de :
   - `io1_resnet50.pth` (best_ResNet50.pth d'Islem, linear head, idx 0=FAKE)
   - `io1_resnet50_deepfake.pth` (Model X d'Islem, dropout+linear head, idx 0=REAL)
   Le seuil de décision est **0.60** (au-dessus du naïf 0.50 pour compenser le biais OOD)
3. **AI consensus** (escalation REAL→FAKE) — pour rattraper les visages GAN/diffusion :
   - **Tier 1** : Organika/sdxl-detector ≥0.95 ET umm-maybe/AI-image-detector ≥0.20 → escalade
   - **Tier 2** : Organika ≥0.90 ET umm-maybe ≥0.40 → escalade

### XAI
- **Grad-CAM** sur `layer4[-1]` du ResNet50 → heatmap visualisant les régions qui ont pesé
- **Geometric heatmap analysis** → texte explicatif sans jargon ("zones concentrées au centre du visage")
- Optionnel : **LLaVA 1.5 7B** (4-bit, GPU requis) pour un commentaire libre

### Limites connues
- ~66% de recall sur TPDNE (StyleGAN3) — meilleur sur diffusion/DALL-E
- Modèles d'Islem entraînés sur FaceForensics → faux positifs possibles sur photos OOD

---

## io2 — Visual Manipulation / Persuasion

**Responsable** : Malek · **Statut** : production (modèles HF spécialisés en remplacement des poids
fine-tunés non livrés)

### Pipeline
1. **TrOCR** (microsoft/trocr-base-printed) — extraction du texte visible
2. **DistilRoBERTa fine-tuned clickbait** (valurank/distilroberta-clickbait) — score manipulation NLP
3. **CLIP ViT-B/32 zero-shot** — score visuel "clickbait/sensational" vs "ordinary informational"
   en comparant les similarités à 3 prompts positifs et 3 prompts négatifs
4. **EasyOCR + regex urgence** (FR/EN, 15 patterns) — détecte "LIMITED TIME", "ONLY 3 LEFT",
   countdown timers, "X% OFF", "SHOCKING", excès de ponctuation, etc.
5. **Fusion heuristique** : `0.45×nlp + 0.30×clickbait + 0.25×urgence`
6. **Optionnel** : MarianMT FR→EN pour faire passer le texte français au classifieur anglais

### XAI
- **Gradient saliency** sur CLIP (backprop de la différence positif-négatif)
- **Bounding boxes** sur les keywords d'urgence détectés par OCR

### Verdicts (4 bandes)
| Score | Label | Couleur |
|---|---|---|
| 0.0 - 0.4 | AUTHENTIC | vert |
| 0.4 - 0.6 | SUSPECT | jaune |
| 0.6 - 0.8 | MANIPULATIVE | orange |
| ≥ 0.8 | HIGHLY MANIPULATIVE | rouge |

---

## io3 — Image-Caption Coherence

**Responsable** : Youssef · **Statut** : production

### Pipeline (5 signaux fusionnés)
1. **CLIP ViT-L/14** (laion2b) — similarité directe image↔texte
2. **YOLOv8m** — détection d'objets, vérifie que les objets nommés dans le texte sont présents
3. **EasyOCR** — extraction du texte écran, cross-check avec la légende
4. **SAM ViT-B** (optional) — segmentation, score d'incohérence régionale ; fallback grille 3×3 sinon
5. **Whisper small** — transcription audio (vidéos uniquement)

### Fusion
- **Image** : `0.40×CLIP + 0.25×SAM + 0.15×Whisper + 0.10×YOLO + 0.10×OCR`
- **Vidéo** : pondération différente avec ajout de scores temporels et audio↔image

### XAI
- **Grad-CAM CLIP** sur `transformer.resblocks[-1].ln_1`
- **Waterfall chart** matplotlib des contributions des 5 modules
- **SHAP-style attribution** dictionary

---

## io4 — Image Tampering (Photoshop forensics)

**Responsable** : Rayen · **Statut** : production (forensique pure — pas de poids requis)

### Pipeline (3 signaux indépendants)
1. **ELA (Error-Level Analysis)** — re-sauvegarde JPEG quality=90, diff amplifié → détecte les
   régions ré-encodées différemment (splicing)
2. **Noise residual** — soustraction d'un filtre médian 3×3, std par bloc 32×32 → détecte les zones
   avec un bruit de capteur étranger (inpainting/paste)
3. **JPEG ghost** — re-save à 6 qualités (60-90), détecte les régions avec un minimum d'erreur à une
   qualité différente du reste (compression mismatch)

### Décision
- Fusion pondérée : `0.45×ELA + 0.30×noise + 0.25×ghost`
- Bonus +0.10 si ≥2 signaux accord (≥0.40 chacun)
- Verdict :
  - `< 0.35` → AUTHENTIC
  - `0.35-0.55` → AUTHENTIC sauf si ≥2 signaux accord → FAKE
  - `≥ 0.55` → FAKE

### Classes
- `Inpainting` — région remplie algorithmiquement
- `Copy-move` — partie dupliquée et collée
- `Splicing` — contenu d'une autre image inséré
- `Enhancement` — ajustements globaux (luminosité, contraste) cachant une édition

### Endpoint compare
`POST /api/io4/analyze/compare` — diff pixel-à-pixel entre suspect et original. Verdict très fiable
quand l'original est disponible.

---

## io5 — Caption Fidelity

**Responsable** : Verify team · **Statut** : production (nouveau)

### Pipeline (4 signaux)
1. **CLIP ViT-B/32** — similarité globale image↔caption (calibrée via sigmoid centré sur 0.20)
2. **CLIP per-phrase** — découpe la caption en noun phrases, score chaque fragment séparément →
   identifie quelles parties ne sont pas supportées par l'image
3. **EasyOCR cross-check** — mots de la caption qui apparaissent dans le texte écran de l'image
4. **Tone gap** — caption alarmiste sur image neutre = signal de fidélité dégradée

### Décision
- `score = calibrated_sim`
- Bonus +0.15×ocr_overlap si overlap ≥30%
- Malus -0.20×tone_gap si tone_gap ≥30%
- Verdict :
  - `≥ 0.60` → FAITHFUL
  - `0.40-0.60` → PARTIAL
  - `< 0.40` → MISLEADING

### Output
Le champ `unsupported_phrases` liste les fragments de la caption qui n'ont pas trouvé d'écho dans
l'image — particulièrement utile pour expliquer pourquoi une caption est jugée MISLEADING.

---

## io6 — Cosmetic Ads Fact-Check

**Responsable** : Yassmine · **Statut** : production

### Pipeline (4 phases)
1. **ffmpeg** — extraction audio (16 kHz mono WAV) et frames (1 par 1.4s, max 12)
2. **Whisper tiny** — transcription audio
3. **YOLOv8n** — détection objets + **EasyOCR** sur les frames pour texte écran
4. **Extraction de claims** :
   - Fallback : sentence-split + filtrage par longueur (mode rapide, défaut)
   - Optionnel : Phi-3 mini 4k (extraction LLM, mode `IO6_ENABLE_PHI3=on`)

### Vérification (5 sources)
- **KB Excel patterns** : 25 regex pour patterns globaux
- **KB Excel fake_claims** : 33 phrases mensongères connues + regex
- **MiniLM semantic** : similarité sémantique avec la base de fake claims pré-encodées
- **KB ingredients/brands** : whitelist de 145 ingrédients INCI et 93 marques cosmétiques validées
- **Decisive Post-Processor** : 15 patterns FAUX (interdits EU 655/2013, ex: "in 7 days", "100% effective",
  "miracle", "reduce wrinkles by X%") + 8 patterns VRAI (vocabulaire acceptable, marques connues)

### Trust score
Moyenne pondérée par confiance des verdicts TRUE/FALSE :
- ≥ 50 → RELIABLE
- < 50 → MISLEADING

### Articles EU cités
Chaque claim FALSE peut citer un article EU spécifique (ex: `EU 655/2013 art. 4.2` pour les claims
quantifiées non-substantiées, `EU 1223/2009` pour les claims médicales interdites). Le champ
`eu_articles_cited` agrège tous les articles violés.

### KB Excel
La base de connaissances est dans `backend/data/IO6_Base_Reference_V3_FULL.xlsx`, 8 feuilles :
`Global_Patterns`, `Global_Fake_Claims`, `Products`, `Synonyms`, `Category_Rules`,
`Extended_Ingredients`, `Extended_Brands`, `Extended_Certifications`.
