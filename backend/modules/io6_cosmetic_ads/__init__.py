"""
Module io6 — Cosmetic Ads Fact-Checking (Yassmine).
Notebook V3 pipeline: Whisper + YOLO + EasyOCR + (optional Phi-3 + MiniLM)
+ Excel Knowledge Base (309+ entries) + Decisive Post-Processor EU 655/2013.
"""
from .router import router, init_models, MODULE_INFO

__all__ = ["router", "init_models", "MODULE_INFO"]
