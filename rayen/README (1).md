# Image Tampering Detection — CNN From Scratch

A dual-output convolutional neural network trained on the **DF2023 Digital Forensics Dataset** that simultaneously classifies the *type* of image manipulation and localises the tampered region at pixel level. The model is integrated into a web platform where users upload an image and receive a manipulation probability breakdown alongside a Grad-CAM heatmap that visually explains *where* the model focused its attention.

---

## Table of Contents

1. [What the model does](#what-the-model-does)
2. [Input specification](#input-specification)
3. [Model architecture](#model-architecture)
4. [Output specification](#output-specification)
5. [Interpreting the confidence scores — real vs. fake](#interpreting-the-confidence-scores--real-vs-fake)
6. [Explainability: Grad-CAM](#explainability-grad-cam)
7. [Web platform integration](#web-platform-integration)
8. [Performance benchmarks](#performance-benchmarks)
9. [Dataset & classes](#dataset--classes)

---

## What the model does

The model solves two tasks in a single forward pass:

| Task | Output | Purpose |
|---|---|---|
| **Classification** | 4-class probability distribution | Identifies *how* the image was manipulated |
| **Segmentation** | Binary pixel mask 256×256 | Localises *where* the manipulation occurred |

On top of these two raw outputs, the web platform generates a **Grad-CAM heatmap** — a coarse saliency map derived from the network's own gradients — to visually explain which regions drove the classification decision.

---

## Input specification

### What goes in

The model accepts a **single RGB image** per inference call. Before the image reaches the network it goes through a fixed preprocessing pipeline:

```
Raw image (any resolution, any format)
        ↓
Resize to 256 × 256 pixels  (bilinear interpolation)
        ↓
Convert to float32 tensor with values in [0, 1]
        ↓
Channel-wise normalisation using ImageNet statistics:
    mean = [0.485, 0.456, 0.406]   (R, G, B)
    std  = [0.229, 0.224, 0.225]   (R, G, B)
        ↓
Final tensor shape: [1, 3, 256, 256]  (batch=1, channels=3, height=256, width=256)
```

### Why these preprocessing steps matter

**Resize to 256×256** — The convolutional layers have fixed kernel sizes and the bottleneck feature map is 16×16. A consistent input resolution ensures that spatial relationships are preserved identically across every image and that skip connections in the U-Net decoder align correctly.

**ImageNet normalisation** — Even though this model was trained from scratch (no pretrained weights), applying the same normalisation shifts pixel distributions to roughly zero-mean / unit-variance per channel. This stabilises gradient flow during training and, more importantly for inference, means the model learned to decode these specific value ranges. Sending an un-normalised image would produce unreliable outputs.

**What the platform should accept** — The frontend can accept JPEG, PNG, WebP, or any standard web image format. The preprocessing pipeline converts whatever format arrives into the expected tensor automatically before inference.

---

## Model architecture

The network is a **hand-built dual-output CNN** — no pretrained backbone, no external segmentation library. It is structured as a U-Net with an additional classification head grafted onto the bottleneck.

```
Input [B, 3, 256, 256]
        │
        ▼
┌─── Encoder (4 stages) ────────────────────────────────────────┐
│  Stage 1 — DoubleConv(3→32)    → [B,  32, 256, 256]  ─ skip1 │
│  Stage 2 — DoubleConv(32→64)   → [B,  64, 128, 128]  ─ skip2 │
│  Stage 3 — DoubleConv(64→128)  → [B, 128,  64,  64]  ─ skip3 │
│  Stage 4 — DoubleConv(128→256) → [B, 256,  32,  32]  ─ skip4 │
└────────────────────────────────────────────────────────────────┘
        │  MaxPool2d
        ▼
  Bottleneck  [B, 256, 16, 16]   ← Grad-CAM targets this layer
        │
   ┌────┴───────────────────────────────────────────────────┐
   ▼                                                        ▼
Classification head                               U-Net Decoder
AdaptiveAvgPool2d(1)                          (4 upsample + skip concat stages)
Flatten                                               │
Dropout(0.3)                                          ▼
Linear(256 → 4)                             Binary mask logits [B, 1, 256, 256]
   │
   ▼
4-class logits [B, 4]
```

**DoubleConv block** — Each stage applies two successive Conv2d(3×3) → BatchNorm2d → ReLU sequences. The double-convolution pattern increases effective receptive field and representational capacity without increasing parameter count as quickly as a single larger kernel would.

**Skip connections** — Feature maps from each encoder stage are concatenated with the corresponding decoder output. This gives the decoder access to fine-grained spatial detail (edges, textures, colour transitions) that would otherwise be lost during downsampling — critical for accurately outlining the tampered region in the segmentation mask.

**Bottleneck as the bridge** — At 16×16 spatial resolution, each of the 256 feature channels encodes a high-level semantic concept over a large receptive field covering most of the image. This is where the classification head operates, and it is the layer that Grad-CAM interrogates.

**Total size: 2.15M trainable parameters.**

---

## Output specification

### 1. Classification probabilities (the "fake meter")

The raw network output for classification is a vector of 4 unnormalised logits. The platform converts them to a probability distribution using the **softmax** function:

```
softmax(logits)_i = exp(logits_i) / Σ exp(logits_j)
```

This yields four values that sum to exactly 1.0. Each value represents the model's estimated probability that the uploaded image belongs to that manipulation class:

| Index | Code | Manipulation type | What it means |
|---|---|---|---|
| 0 | **I** | Inpainting | A region was algorithmically filled in to remove or replace content |
| 1 | **C** | Copy-move | A patch from inside the image was duplicated and pasted elsewhere |
| 2 | **S** | Splicing | Content from a different image was inserted |
| 3 | **E** | Enhancement | Global or local adjustments (brightness, contrast, blur, sharpening) that disguise prior editing |

The platform displays these four values as percentages, for example:

```
Inpainting  ████░░░░░░  12%
Copy-move   ██████████  71%   ← predicted class
Splicing    ███░░░░░░░   9%
Enhancement ████░░░░░░   8%
```

### 2. Pixel-level tamper mask

In parallel, the model produces a 256×256 binary mask where each pixel is either **tampered** (value 1) or **untampered** (value 0). A sigmoid activation converts the raw mask logit to a probability per pixel; pixels above 0.5 are flagged. The platform can display this mask as a red overlay on the original image to show *where* the model found evidence of manipulation, independently of the Grad-CAM heatmap.

---

## Interpreting the confidence scores — real vs. fake

The model was trained on four manipulation classes. It has never seen a ground-truth "real / unmodified" class, because the training dataset only contains tampered images. For a web platform exposed to real-world uploads (which includes genuine photographs), a confidence-threshold rule is applied:

### Decision logic

```
max_confidence = max(P_inpainting, P_copy_move, P_splicing, P_enhancement)

if max_confidence < THRESHOLD:
    verdict = "AUTHENTIC — no significant manipulation detected"
else:
    verdict = f"FAKE — predicted manipulation: {argmax class}"
```

**Recommended threshold: 0.50** (i.e. no single class exceeds 50% confidence).

When all four probabilities are spread roughly evenly (e.g. 27% / 24% / 26% / 23%), the model is uncertain — it cannot find a coherent tampering pattern that matches any known manipulation type. This is the expected behaviour on authentic images: the model finds nothing to latch on to, so probability mass disperses across all classes, and none clears the threshold.

### How to display this in the platform

```
┌──────────────────────────────────────────────────────────┐
│  VERDICT:  ✅  AUTHENTIC IMAGE                           │
│  The model found no confident evidence of manipulation.  │
│                                                          │
│  Manipulation scores:                                    │
│  Inpainting  ██░░░░░░░░  22%                            │
│  Copy-move   ███░░░░░░░  28%                            │
│  Splicing    ██░░░░░░░░  24%                            │
│  Enhancement ██░░░░░░░░  26%                            │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│  VERDICT:  ❌  FAKE IMAGE                                │
│  Predicted manipulation type: COPY-MOVE (71%)           │
│                                                          │
│  Manipulation scores:                                    │
│  Inpainting  ████░░░░░░  12%                            │
│  Copy-move   ██████████  71%   ← detected               │
│  Splicing    ███░░░░░░░   9%                            │
│  Enhancement ████░░░░░░   8%                            │
└──────────────────────────────────────────────────────────┘
```

You can expose the threshold as a user-facing slider (e.g. "Sensitivity") to let users trade off false positives vs. false negatives depending on the context.

---

## Explainability: Grad-CAM

### Why Grad-CAM

Showing a verdict alone ("this image is fake") is not enough — users need to understand *why* the model reached that conclusion. Without an explanation, the output is untrustworthy and unactionable. **Gradient-weighted Class Activation Mapping (Grad-CAM)** addresses this by producing a heatmap that highlights which spatial regions of the image were most influential for the predicted class.

This is especially important for a tampering-detection platform because the highlighted region should ideally coincide with the physically manipulated area, giving the user a concrete visual marker to inspect.

### How it works (step by step)

Grad-CAM operates on a chosen convolutional layer — here, the last encoder stage (`enc4`) — which produces feature maps of shape `[256, 32, 32]` (256 channels, each a 32×32 spatial grid). This is the richest semantic layer before pooling collapses spatial information for the classification head.

**Step 1 — Forward pass**

The image is passed through the network normally. The 256-channel feature map at `enc4` is captured via a forward hook and saved as `A` (activations).

**Step 2 — Backward pass for the predicted class**

The score of the predicted class (the highest logit) is backpropagated through the network. The gradient of this score with respect to every spatial location in `enc4`'s feature map is captured via a backward hook and saved as `∂score/∂A`.

**Step 3 — Channel importance weights**

For each of the 256 channels `k`, compute its importance weight `α_k` by global-average-pooling the gradient map over the 32×32 spatial grid:

```
α_k = (1 / (32×32))  Σ_{i,j}  (∂score / ∂A_k^{ij})
```

Channels whose gradients are large and positive contributed strongly to the class score; channels with near-zero or negative gradients are uninformative or suppressive.

**Step 4 — Weighted combination + ReLU**

The Grad-CAM heatmap is a weighted sum of the activation maps, retaining only positive contributions (ReLU ensures we focus on features that increase the class score, not features that suppress it):

```
CAM = ReLU( Σ_k  α_k · A_k )
```

The result is a single-channel spatial map of shape `[32, 32]`.

**Step 5 — Upsampling and normalisation**

The 32×32 CAM is bilinearly upsampled back to the original input resolution (256×256), then min-max normalised to [0, 1] so it can be rendered as a colour heatmap. Values near 1 (hot colours in the jet colormap) indicate regions the classifier relied on most; values near 0 (cool colours) are regions it largely ignored.

**Step 6 — Overlay**

The normalised CAM is composited over the original image with 50% transparency (alpha blending), producing the final overlay shown to the user.

### What the Grad-CAM tells you

- **Heatmap concentrated on a specific object or region** — the model identified a localised manipulation; the hot area is where to look for signs of editing.
- **Heatmap diffuse across the entire image** — either the manipulation affects the whole image (e.g. global enhancement), or the model is not confident in its localisation.
- **Heatmap coincides with the segmentation mask** — strong agreement between the pixel-level mask (task 2) and the Grad-CAM (task 1 explanation) increases confidence that the detection is genuine.
- **Heatmap on irrelevant regions** — a sign of a shortcut/artefact the model learned; users should treat the verdict with more scepticism.

### Implementation reference

```python
class GradCAM:
    def __init__(self, model, target_module):
        # register forward hook to capture enc4 activations
        self.h_fwd = target_module.register_forward_hook(self._fwd_hook)
        # register backward hook to capture gradients at enc4
        self.h_bwd = target_module.register_full_backward_hook(self._bwd_hook)

    def __call__(self, x, class_idx=None):
        _, logits = self.model(x)              # forward pass
        score = logits[:, class_idx].sum()
        score.backward()                        # backward pass
        weights = self.gradients.mean(dim=(2,3), keepdim=True)       # α_k
        cam = F.relu((weights * self.activations).sum(dim=1))        # weighted sum + ReLU
        cam = F.interpolate(cam, size=(256, 256), mode='bilinear')   # upsample
        cam = (cam - cam.min()) / (cam.max() - cam.min() + 1e-8)     # normalise
        return cam
```

The model weights target `enc4` (the last encoder stage, output shape `[B, 256, 32, 32]`). This layer sees a 32×32 grid where each cell covers a 16×16 pixel receptive field in the original image, giving a good balance between spatial resolution and semantic richness.

---

## Web platform integration

### Inference pipeline per upload

```
User uploads image
        ↓
Preprocess: resize → tensor → normalise  →  [1, 3, 256, 256]
        ↓
model(image)  →  (mask_logits [1,1,256,256],  cls_logits [1,4])
        ↓
softmax(cls_logits)  →  [P_I, P_C, P_S, P_E]   (four class probabilities)
sigmoid(mask_logits) →  pixel-level tamper probability map
GradCAM(image, predicted_class)  →  heatmap [256, 256]
        ↓
Response to frontend:
  - verdict: "AUTHENTIC" | "FAKE — <class>"
  - class_probabilities: { inpainting: %, copy_move: %, splicing: %, enhancement: % }
  - tamper_mask: base64-encoded PNG overlay
  - gradcam_heatmap: base64-encoded PNG overlay
  - gradcam_on_image: base64-encoded blended composite
```

### What to display per result

| UI element | Content |
|---|---|
| **Verdict badge** | Green "Authentic" or red "Fake — Copy-move" (example) |
| **Confidence bars** | Four horizontal bars, one per manipulation class, labelled with percentages |
| **Tamper mask overlay** | Original image with red-tinted pixels where the binary mask fires (pixel-level "where") |
| **Grad-CAM overlay** | Original image composited with the jet-coloured heatmap at 50% alpha (attention-level "where and why") |
| **Explanation text** | Short natural-language description of what the Grad-CAM shows, e.g.: *"The model focused on the lower-left region (red/yellow area), where it detected pixel statistics inconsistent with the surrounding texture — a common sign of copy-move forgery."* |

### Confidence threshold setting

Expose a configurable threshold in the platform settings (default 0.50). A user who wants fewer false positives (e.g. a journalist) should raise it to 0.65–0.70. A user who wants to catch any hint of manipulation (e.g. a forensics auditor) should lower it to 0.35–0.40.

---

## Performance benchmarks

Evaluated on a held-out test set of 24,000 images (6,000 per class), trained on 2× NVIDIA Tesla T4 GPUs.

| Metric | Value |
|---|---|
| Test Accuracy | **95.20%** |
| Test F1 (macro) | **95.22%** |
| Test F1 (weighted) | **95.22%** |
| Test ROC-AUC (macro / OvR) | **99.59%** |
| Mean IoU (segmentation) | **70.65%** |
| Mean Dice (segmentation) | **77.90%** |
| Expected Calibration Error | **0.0139** (well-calibrated) |
| Total parameters | **2.15M** |
| Forward FLOPs (1 image) | **12.80 GFLOPs** |
| Inference latency | **4.81 ms / image** |
| Throughput | **208 FPS @ batch 64** |

The low ECE (0.014) means the confidence percentages shown to users are trustworthy: when the model says 71%, the image really is that class about 71% of the time. This is what makes the probability display meaningful rather than decorative.

---

## Dataset & classes

The model was trained on the **DF2023 Digital Forensics 2023 Dataset (v15, COCO split)** — 160,000 images (40,000 per class), split 70% train / 15% validation / 15% test with stratified sampling to preserve class balance.

### Manipulation classes

**I — Inpainting**
A region of the image was removed and algorithmically filled in using content-aware or neural inpainting techniques. The forged area typically shows smooth textures that blend with the surroundings but lack natural noise patterns. Common use case: removing people or objects from photographs.

**C — Copy-move**
A patch from one area of the image was copied and pasted into another area of the *same* image. The duplicate patch may be rotated, scaled, or slightly colour-corrected to disguise the copy. Copy-move is one of the most common forgery types in political and journalistic image manipulation.

**S — Splicing**
Content from a *different* source image was cut and pasted into the target image. Unlike copy-move, splicing introduces foreign lighting, noise characteristics, and compression artefacts that do not match the host image's statistics — the strongest signal the model exploits.

**E — Enhancement**
Selective or global adjustments including brightness/contrast changes, blurring, sharpening, saturation shifts, or JPEG re-compression. Enhancement is often used to disguise prior editing or to make other manipulations less detectable.

### Why no "real" class in training

The DF2023 dataset does not include unmodified authentic images — every sample has been manipulated in one of the four ways above. This is why the platform uses a confidence-threshold rule rather than a dedicated "real" output neuron. The absence of any strongly recognised manipulation pattern (flat probability distribution across all four classes) is used as the proxy for authenticity.
