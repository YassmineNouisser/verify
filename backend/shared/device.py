"""Shared device detection used by every module."""
import os


def detect_device() -> str:
    forced = os.environ.get("FORCE_DEVICE")
    if forced:
        return forced
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
    except Exception:
        pass
    return "cpu"


DEVICE = detect_device()
