"""
Fake media image detection — unified inference module.

Two specialized ResNet50 models with automatic routing :
  1. Image AI vs Real      → resnet50_ai_vs_real.pth
  2. Image Deepfake vs Real → resnet50_deepfake.pth

The detector uses MTCNN to detect a face in the input image.
If a face is found → routes to the deepfake model.
If no face       → routes to the AI vs Real model.

Usage:
    from inference import FakeMediaImageDetector
    from PIL import Image

    detector = FakeMediaImageDetector()
    img = Image.open("photo.jpg")
    result = detector.detect(img)

    # result example :
    # {'task':       'image_deepfake',
    #  'verdict':    'DEEPFAKE',
    #  'risk_score': 87,
    #  'confidence': 92.3,
    #  'probs':      {'real': 0.13, 'fake': 0.87},
    #  'heatmap':    numpy.ndarray (224, 224) values 0–1}
"""
import os
import cv2
import numpy as np
import torch
import torch.nn as nn
from PIL import Image, ImageFile
from torchvision import models, transforms
from facenet_pytorch import MTCNN

# Allow large + truncated images
Image.MAX_IMAGE_PIXELS = None
ImageFile.LOAD_TRUNCATED_IMAGES = True


# ============================================================
# Constants
# ============================================================
NORM_MEAN = (0.485, 0.456, 0.406)
NORM_STD  = (0.229, 0.224, 0.225)
IMG_SIZE  = 224


# ============================================================
# ResNet50 builder (matches the training architecture)
# ============================================================
def build_resnet50(num_classes=2, dropout=0.3):
    """Same architecture as the training notebook: ResNet50 + Dropout + Linear."""
    m = models.resnet50(weights=None)
    m.fc = nn.Sequential(
        nn.Dropout(dropout),
        nn.Linear(m.fc.in_features, num_classes)
    )
    return m


# ============================================================
# Grad-CAM (for XAI heatmaps)
# ============================================================
class GradCAM:
    """Generic Grad-CAM for any CNN architecture."""

    def __init__(self, model, target_layer):
        self.model = model
        self.gradients = None
        self.activations = None
        self._fwd = target_layer.register_forward_hook(
            lambda m, i, o: setattr(self, 'activations', o.detach()))
        self._bwd = target_layer.register_full_backward_hook(
            lambda m, gi, go: setattr(self, 'gradients', go[0].detach()))

    def generate(self, x, class_idx=None):
        self.model.eval()
        self.model.zero_grad()
        out = self.model(x)
        if class_idx is None:
            class_idx = out.argmax(1).item()
        out[0, class_idx].backward(retain_graph=True)
        w = self.gradients[0].mean(dim=(1, 2), keepdim=True)
        h = (w * self.activations[0]).sum(0).cpu().numpy()
        h = np.maximum(h, 0)
        h /= h.max() + 1e-8
        return cv2.resize(h.squeeze(), (IMG_SIZE, IMG_SIZE))

    def remove(self):
        self._fwd.remove()
        self._bwd.remove()


# ============================================================
# Main detector class
# ============================================================
class FakeMediaImageDetector:
    """
    Unified detector for image-based fake media detection.

    Args:
        ai_weights:  path to the AI vs Real model weights (.pth)
        dfk_weights: path to the Deepfake model weights (.pth)
        device:      torch.device, or None for auto-detect
    """

    VERDICT_MAP = {
        "image_ai_vs_real": ("REAL", "FAKE/AI"),
        "image_deepfake":   ("REAL", "DEEPFAKE"),
    }

    def __init__(self,
                 ai_weights="models/resnet50_ai_vs_real.pth",
                 dfk_weights="models/resnet50_deepfake.pth",
                 device=None):
        self.device = device or torch.device(
            "cuda" if torch.cuda.is_available() else "cpu"
        )

        # Build + load both ResNet50 models
        self.model_ai  = self._load(ai_weights)
        self.model_dfk = self._load(dfk_weights)

        # Shared MTCNN face detector
        self.mtcnn = MTCNN(image_size=IMG_SIZE, margin=20, keep_all=False,
                           post_process=False, device=self.device)

        # Standard preprocessing
        self.transform = transforms.Compose([
            transforms.Resize((IMG_SIZE, IMG_SIZE)),
            transforms.ToTensor(),
            transforms.Normalize(NORM_MEAN, NORM_STD),
        ])

    def _load(self, weights_path):
        m = build_resnet50().to(self.device)
        m.load_state_dict(torch.load(weights_path, map_location=self.device))
        m.eval()
        return m

    def _crop_face(self, pil_image, margin_ratio=0.15):
        """Detect the largest face. Returns PIL crop or None."""
        boxes, probs = self.mtcnn.detect(pil_image)
        if boxes is None or len(boxes) == 0:
            return None
        box = boxes[np.argmax(probs)]
        x1, y1, x2, y2 = box
        w, h = x2 - x1, y2 - y1
        x1 = max(0, x1 - w * margin_ratio)
        y1 = max(0, y1 - h * margin_ratio)
        x2 = min(pil_image.width,  x2 + w * margin_ratio)
        y2 = min(pil_image.height, y2 + h * margin_ratio)
        return pil_image.crop((x1, y1, x2, y2)).resize((IMG_SIZE, IMG_SIZE))

    def _predict(self, model, pil_image):
        """Returns (pred_class, prob_real, prob_fake)."""
        x = self.transform(pil_image.convert('RGB')).unsqueeze(0).to(self.device)
        with torch.no_grad():
            probs = torch.softmax(model(x), dim=1)[0]
        return probs.argmax().item(), probs[0].item(), probs[1].item()

    def _make_result(self, task, pred, p_real, p_fake, model, pil_input):
        """Build the standardized output dict including Grad-CAM heatmap."""
        x = self.transform(pil_input.convert('RGB')).unsqueeze(0).to(self.device)
        # Both models share the same ResNet50 architecture → same target layer
        cam = GradCAM(model, model.layer4[-1])
        heatmap = cam.generate(x, class_idx=pred)
        cam.remove()

        return {
            "task":       task,
            "verdict":    self.VERDICT_MAP[task][pred],
            "risk_score": int(p_fake * 100),
            "confidence": round(max(p_real, p_fake) * 100, 1),
            "probs":      {"real": p_real, "fake": p_fake},
            "heatmap":    heatmap,
        }

    def detect(self, image):
        """
        Main entry point. Auto-routes to the right model.

        Args:
            image: file path (str) or PIL.Image

        Returns:
            dict with keys: task, verdict, risk_score, confidence, probs, heatmap
        """
        # Accept either a path or a PIL Image
        if isinstance(image, str):
            pil = Image.open(image).convert('RGB')
        elif isinstance(image, Image.Image):
            pil = image.convert('RGB')
        else:
            raise TypeError("`image` must be a file path or a PIL.Image")

        # Try face detection
        face = self._crop_face(pil)

        if face is not None:
            # Face found → deepfake model
            pred, p_r, p_f = self._predict(self.model_dfk, face)
            return self._make_result("image_deepfake", pred, p_r, p_f,
                                     self.model_dfk, face)
        else:
            # No face → AI vs Real model
            pred, p_r, p_f = self._predict(self.model_ai, pil)
            return self._make_result("image_ai_vs_real", pred, p_r, p_f,
                                     self.model_ai, pil)


# ============================================================
# Quick test (CLI)
# ============================================================
if __name__ == "__main__":
    detector = FakeMediaImageDetector()
    result = detector.detect("test_image.jpg")
    # Print without the heatmap (too large for stdout)
    print({k: v for k, v in result.items() if k != "heatmap"})
    print(f"Heatmap shape: {result['heatmap'].shape}")
