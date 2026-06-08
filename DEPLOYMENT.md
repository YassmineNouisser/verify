# Verify — Free deployment guide (HuggingFace Spaces)

This guide deploys the **full Verify platform** (6 detection modules + chatbot + static frontend)
**on a single free HuggingFace Space**. The jury gets one public URL — e.g. `https://yassminenouisser-verify.hf.space` — that they can hit with their browser to test everything.

> **Total cost: 0 €.** Total wall-clock time the first time: ~30 min (mostly waiting for the Space to build).
> Cold-start delay for the first request after 48h of inactivity: ~1 min (the persistent storage keeps models warm).

---

## Architecture

```
            ┌──────────────────────────────────────────────────┐
            │  HuggingFace Space  (Docker SDK, CPU Basic 16GB) │
            │                                                  │
            │   ┌────────────────────────────────────────┐     │
            │   │  FastAPI (uvicorn :7860)               │     │
            │   │  ├─ /                  static frontend │     │
            │   │  ├─ /api/io[1-6]/...   detection ML    │     │
            │   │  ├─ /api/chat/...      chatbot         │     │
            │   │  └─ /health, /docs                     │     │
            │   └────────────────────────────────────────┘     │
            │                                                  │
            │   Secrets (encrypted):                           │
            │     OPENAI_API_KEY                               │
            │     IO1_RESNET50_URL          ← from HF Dataset  │
            │     IO1_RESNET50_DEEPFAKE_URL ← from HF Dataset  │
            └──────────────────────────────────────────────────┘
                          ▲
                          │
            ┌─────────────┴────────────────┐
            │  HuggingFace Dataset (free)  │
            │  Verify-weights (private)    │
            │  ├─ best_ResNet50.pth        │
            │  └─ resnet50_deepfake.pth    │
            └──────────────────────────────┘
```

The Space hosts everything in one container. The two heavy `.pth` weights are stored in a
companion **HuggingFace Dataset** (also free, unlimited) so the Space repo stays under the
git-LFS-free 10 MB-per-file limit.

---

## Step 1 — Create a HuggingFace account

Go to **https://huggingface.co/join**, create your free account, verify your email.
Note your username (e.g. `yassminenouisser`). You'll use it everywhere below.

---

## Step 2 — Upload Islem's `.pth` weights to a HF Dataset

The two ResNet50 checkpoints (94 MB each) cannot live in the Space's git repo. We host them in
a HuggingFace Dataset.

1. Go to **https://huggingface.co/new-dataset**
2. Name: `verify-weights`
3. Visibility: **Private** (the weights are Islem's research artifacts)
4. License: `other`
5. Click **Create dataset**

Then upload the files (web UI is the easiest):

1. Open your new dataset → **Files** tab → **Add file** → **Upload files**
2. Drag-drop `backend/data/io1_resnet50.pth` and `backend/data/io1_resnet50_deepfake.pth`
3. Commit

The files are now at:
- `https://huggingface.co/datasets/<your-username>/verify-weights/resolve/main/io1_resnet50.pth`
- `https://huggingface.co/datasets/<your-username>/verify-weights/resolve/main/io1_resnet50_deepfake.pth`

> ⚠️ **Private dataset**: the Space will need a **read-token** to download these.
> Generate one at https://huggingface.co/settings/tokens (role: `read`). Copy it; you'll paste
> it as a Space Secret in step 4.

---

## Step 3 — Create the HuggingFace Space

1. Go to **https://huggingface.co/new-space**
2. Owner: your username
3. Name: `verify` (the public URL will be `https://<username>-verify.hf.space`)
4. License: `apache-2.0`
5. **SDK: `Docker`** (NOT Gradio/Streamlit — we use our own Dockerfile)
6. Hardware: **CPU basic — free** (16 GB RAM, 2 vCPU)
7. Visibility: **Public**
8. Click **Create Space**

The Space is created empty. Don't push anything yet — first configure the secrets.

---

## Step 4 — Configure Space Secrets (encrypted environment variables)

In your Space, go to **Settings** → **Variables and secrets** → **New secret**. Add these one by one:

| Secret name | Value | Why |
|---|---|---|
| `OPENAI_API_KEY` | `sk-proj-...` (your real key) | Needed by the chatbot module and the narrative layer |
| `IO1_RESNET50_URL` | `https://huggingface.co/datasets/<username>/verify-weights/resolve/main/io1_resnet50.pth` | Where the build script pulls Islem's weights |
| `IO1_RESNET50_DEEPFAKE_URL` | `https://huggingface.co/datasets/<username>/verify-weights/resolve/main/io1_resnet50_deepfake.pth` | Same, for Model X |
| `HUGGINGFACE_HUB_TOKEN` | the read-token you generated in step 2 | Lets the build authenticate to download from the private dataset |

Click **Save** after each one. Secrets are encrypted and never visible in the Space's logs or code.

---

## Step 5 — Push the Verify code to the Space

Each HF Space is a git repo. From your local Verify checkout:

```bash
cd /Users/yassminesmachine/Desktop/template

# 1. Make sure the local repo is up to date (no uncommitted work)
git status
git add -A
git commit -m "Prepare for HuggingFace Space deployment"

# 2. Add HF Space as a remote (use your own username + space name)
git remote add space https://huggingface.co/spaces/<username>/verify

# 3. Push
git push space main

# (HF git will prompt for your HuggingFace credentials — username + an access token from
#  https://huggingface.co/settings/tokens, role 'write')
```

Once the push completes, HuggingFace starts building the Docker image automatically. You can
watch the build at **https://huggingface.co/spaces/`<username>`/verify** → **Logs** tab.

> ⏱ **First build takes ~15 min** because the Dockerfile pre-downloads all HuggingFace models
> (CLIP, TrOCR, Whisper, etc.) inside the image. Subsequent builds are much faster — only the
> changed layers rebuild.

---

## Step 6 — Verify the deployment

When the build is done and the Space status flips to **Running**:

1. Open `https://<username>-verify.hf.space` in your browser → you should see the Verify homepage.
2. Click **Verifier** → choose any module → upload an image → click **Analyze**.
3. The first analysis after a cold start takes ~30-60 s (CPU + first-time module init);
   subsequent calls are 5-15 s.

Sanity checks:

```bash
# From your laptop — confirms the API is reachable
curl https://<username>-verify.hf.space/health | jq .status      # → "ok"

curl https://<username>-verify.hf.space/api                       # → JSON describing the 6 modules + chatbot
```

---

## Step 7 — Fill in the ESPRIT submission form

Now you can fill in section 2 of the submission PDF:

| Champ | Valeur |
|---|---|
| Nom du projet | `Esprit-PI-<TaClasse>-2526-Verify` |
| Lien GitHub | `https://github.com/<YourGitHub>/Esprit-PI-<TaClasse>-2526-Verify` |
| Lien de déploiement | **`https://<username>-verify.hf.space`** ✓ |
| Type de projet | IA |
| Commande de lancement | `docker build -t verify . && docker run -p 7860:7860 verify` (or local: `uvicorn backend.main:app --port 8000`) |
| Temps d'installation estimé | < 10 min (local) or instant (deployed link) |

---

## Updating the Space later

After pushing changes to GitHub, push the same commits to the Space:

```bash
git push origin main         # GitHub
git push space  main         # HF Space (triggers rebuild)
```

If you only changed Python code (no new model), the rebuild takes ~2-3 min thanks to Docker
layer caching.

---

## Troubleshooting

### "Build failed: file too large"
GitHub-via-LFS isn't enabled by default on HF Spaces. Make sure `.gitignore` is excluding all
`*.pth`/`*.pt` files except `yolov8n.pt` (it's only 7 MB).
Check with: `git ls-files | xargs -I{} ls -l {} 2>/dev/null | awk '$5 > 10000000 {print}'`

### "Space running out of memory"
The default CPU-basic Space has 16 GB RAM, which is enough. If you upgraded the hardware and
hit OOM, try `LOAD_MODULES=io1,io4` to load fewer modules at startup (set this as a Space variable).

### Chatbot returns "service unavailable"
The `OPENAI_API_KEY` secret is missing or the key is invalid. Re-set it in **Space Settings** →
**Variables and secrets**, then restart the Space (top-right menu → **Restart this Space**).

### Cold start is very long (> 3 min)
The first request after a 48h sleep needs to (a) re-download HF models if persistent storage was
not enabled, (b) load all PyTorch models into RAM. Enable **Persistent storage** in Space
settings (free 50 GB tier — was previously paid) to keep the cache between sleeps.

### Frontend says "Service unavailable"
Open the browser DevTools console. If `fetch('/api/io1/health')` returns 404, the FastAPI static
mount is broken — check `backend/main.py` and confirm the `app.mount("/", StaticFiles(...))` line
is present and that `index.html` exists at the repo root.

### Some images come up as REAL when they should be FAKE
This is the limit of the open-source AI detectors (see `MODELS.md`). The deepfake ensemble +
2-detector consensus catches ~66% of ThisPersonDoesNotExist images and ~99% of obvious DALL-E /
Midjourney / Flux images. Re-test with another sample if you hit a model blind spot.

---

## Alternative: deploy WITHOUT HuggingFace Spaces (local Docker only)

If for any reason you cannot use HF Spaces, the project also runs with plain Docker. In your
local terminal:

```bash
docker build -t verify .
docker run -p 7860:7860 \
  -e OPENAI_API_KEY=sk-... \
  -e IO1_RESNET50_URL=https://... \
  -e IO1_RESNET50_DEEPFAKE_URL=https://... \
  verify
```

Then open `http://localhost:7860`. The jury will need Docker on their machine — but the
**ESPRIT acceptance criterion for IA projects** (guide page 8) is precisely that: local launch in
<20 min with Docker. So this fully passes the rubric even without HF Spaces.
