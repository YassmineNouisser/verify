"""
Module io4 — Image Tampering Detection / Photoshop Forensics (Rayen).
CNN from scratch (U-Net + classification head) on DF2023.
4 classes: Inpainting · Copy-move · Splicing · Enhancement.
Grad-CAM XAI on enc4 (target layer).
"""
from .router import router, init_models, MODULE_INFO

__all__ = ["router", "init_models", "MODULE_INFO"]
