"""
Module io3 — Image-Caption / Video-Caption Coherence (Youssef).
Pipeline V4.1 du notebook : CLIP + YOLO + EasyOCR + SAM + Whisper, avec XAI.
"""
from .router import router, init_models, MODULE_INFO

__all__ = ["router", "init_models", "MODULE_INFO"]
