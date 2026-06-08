"""
Module io2 — Visual Manipulation Detection (Malek Tirellil).
Pipeline of 5 sub-models: TrOCR + RoBERTa + ViT + DETR + ManipNet (fusion).
XAI: Gradient Saliency + Occlusion Sensitivity + Attention Rollout.
"""
from .router import router, init_models, MODULE_INFO

__all__ = ["router", "init_models", "MODULE_INFO"]
