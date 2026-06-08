#!/usr/bin/env python3
"""Download the model weights that are NOT versioned in the repo.

Per the ESPRIT student guide (page 6): trained model weights bigger than ~100 MB or that pile up
quickly are hosted externally (Hugging Face Hub, Google Drive, Kaggle) and pulled at install time
by a script like this one.

Usage:
    python scripts/download_models.py

Models downloaded here are Islem's ResNet50 weights for io1 (face deepfake detection). All other
HuggingFace / OpenAI-CLIP / Ultralytics models auto-download on first use of the backend.

Hosting URLs are read from environment variables (set them in `.env` or export them in your shell):
    IO1_RESNET50_URL          public download URL for io1_resnet50.pth         (~94 MB)
    IO1_RESNET50_DEEPFAKE_URL public download URL for io1_resnet50_deepfake.pth (~94 MB)

The recommended hosting is Hugging Face Hub (free, unlimited for public models — see ESPRIT
guide page 6 for the rationale). Once Islem uploads the files to a HF repo, set:

    export IO1_RESNET50_URL=https://huggingface.co/<user>/<repo>/resolve/main/best_ResNet50.pth
    export IO1_RESNET50_DEEPFAKE_URL=https://huggingface.co/<user>/<repo>/resolve/main/resnet50_deepfake.pth
"""
from __future__ import annotations

import hashlib
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "backend" / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# (env var, target filename, expected approx size in MB) for each weight
WEIGHTS = [
    ("IO1_RESNET50_URL",          "io1_resnet50.pth",          94),
    ("IO1_RESNET50_DEEPFAKE_URL", "io1_resnet50_deepfake.pth", 94),
]


def _human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def _progress(blocknum: int, blocksize: int, totalsize: int):
    done = blocknum * blocksize
    if totalsize > 0:
        pct = min(100, done * 100 // totalsize)
        sys.stdout.write(f"\r    {pct:3d}%  {_human(done):>10s} / {_human(totalsize):>10s}")
    else:
        sys.stdout.write(f"\r    {_human(done):>10s}")
    sys.stdout.flush()


def download(url: str, dest: Path):
    print(f"  → {url}")
    print(f"     into {dest}")
    tmp = dest.with_suffix(dest.suffix + ".part")
    urllib.request.urlretrieve(url, tmp, reporthook=_progress)
    print()
    tmp.replace(dest)


def main():
    print(f"[download_models] target directory: {DATA_DIR}")
    print()
    missing_env = []
    for env_var, filename, _ in WEIGHTS:
        dest = DATA_DIR / filename
        if dest.exists() and dest.stat().st_size > 1_000_000:
            print(f"  ✓ {filename} already present ({_human(dest.stat().st_size)})")
            continue
        url = (os.environ.get(env_var) or "").strip()
        if not url:
            missing_env.append((env_var, filename))
            print(f"  ✗ {filename} missing — set {env_var}=<download URL>")
            continue
        try:
            download(url, dest)
            print(f"  ✓ {filename} ready ({_human(dest.stat().st_size)})")
        except Exception as e:
            print(f"  ✗ download failed for {filename}: {type(e).__name__}: {e}")
            sys.exit(2)

    if missing_env:
        print()
        print("Some weights were not downloaded because their environment variables are unset.")
        print("Edit .env (or export the variables) with the hosting URLs and re-run this script.")
        print()
        print("Example:")
        print("    export IO1_RESNET50_URL=https://huggingface.co/<user>/verify-weights/resolve/main/best_ResNet50.pth")
        sys.exit(1)

    print()
    print("All weights are in place. You can now run the backend:")
    print("    uvicorn backend.main:app --host 0.0.0.0 --port 8000")


if __name__ == "__main__":
    main()
