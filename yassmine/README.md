# IO6 — Multimodal Fact-Checking Pipeline for Cosmetic Advertising

> AI Media Credibility Platform · Automated fact-checking of cosmetic advertising claims using multimodal deep learning, compliant with EU Regulation 655/2013 and the EU AI Act 2024.

---

## Overview

This project, **IO6 — Multimodal Fact-Checking Pipeline**, was developed as part of the coursework at **[Esprit School of Engineering](https://esprit.tn)** (3rd year AI), in the context of the **AI Media Credibility Platform** Challenge-Based Learning (CBL) project. It addresses the growing problem of misleading claims in cosmetic advertising by combining **audio, visual, and textual analysis** into a single explainable AI system, fully aligned with **European Union regulations** on cosmetic claims (EU 655/2013) and AI explainability (EU AI Act 2024 Article 13).

The repository contains **two complementary deliverables** :

1. **CNN from Scratch** — A custom convolutional neural network (PharmaLogoNet) built from scratch for pharmaceutical/cosmetic brand logo detection in images, with multi-task learning (classification + bounding box regression) and GradCAM explainability.
2. **Multimodal Pipeline** — An end-to-end fact-checking pipeline that processes video advertisements through six specialized open-source models (Whisper, YOLOv8, EasyOCR, Phi-3, MiniLM, MLP) and outputs structured verdicts (TRUE / FALSE / TO_VERIFY) with full XAI traceability.

---

## Features

### Multimodal Pipeline

- **Multimodal extraction** combining audio (Whisper ASR), vision (YOLOv8 object detection + EasyOCR text recognition), and reasoning (Phi-3 LLM + MiniLM semantic embeddings).
- **Knowledge Base** with 309+ entries across 8 sheets (brands, fake claims, EU 655/2013 patterns, ingredients, certifications) — fully editable by domain experts.
- **LoRA fine-tuning** of Phi-3 (rank=8, alpha=16) for domain adaptation on a single GPU.
- **Decisive Post-Processor** — proprietary innovation that forces TRUE/FALSE verdicts on ambiguous claims using EU 655/2013 patterns and ASA UK puffery jurisprudence.
- **Explainability suite (XAI)** with four complementary methods : LIME word-level highlighting, SHAP-like severity scoring, counterfactual analysis (Wachter 2018), and traceability with EU article citations.
- **Five evaluation protocols** : validated curated cases, extended stratified sample (N=30, Cohen's κ=1.0), 3-fold cross-validation (100% ± 0%), multi-video operational batch (F1 macro 92.5%), and ablation study.
- **Six loss functions** suite : Cross-Entropy, Brier Score, MSE, MAE, KL Divergence, ECE — for full calibration analysis.
- **Automated PDF report generation** for compliance officers, including verdict, confidence, justifications, and EU article citations.
- **Final analytical dashboard** with six visualizations (Trust Score Gauge, Distribution Donut, Confidence per claim, SHAP Scatter, EU Patterns frequency, Verdict Source Pie).

### CNN from Scratch

- **Custom architecture (PharmaLogoNet)** with depthwise separable convolutions inspired by MobileNet (~1.5M parameters, 15× lighter than ResNet-50).
- **Multi-task learning** with two parallel heads : classification (50 logo classes) and bounding box regression.
- **Custom GIoU Loss** implemented from scratch (Rezatofighi CVPR 2019) for better gradient flow when bboxes don't overlap.
- **mAP@0.5 and mAP@0.5:0.95** implemented from scratch in COCO style — no torchvision dependency.
- **Adaptive AMP** (Automatic Mixed Precision) — auto-detects GPU (P100, T4, V100, A100) and adjusts FP16/FP32 accordingly.
- **GradCAM explainability** (Selvaraju 2017) on the last convolutional layer.

### Cross-cutting features

- **Reproducibility** : fixed random seeds (42), open-source models, JSON exports of all results.
- **Compliance** : aligned with EU 655/2013 cosmetic claims regulation and EU AI Act 2024 Article 13 (Right to Explanation).
- **Documentation** : 104-cell main notebook + 47-cell CNN notebook + Dataset Card + Ethics & Bias Statement + 23 academic references.

---

## Tech Stack

### Core ML / Deep Learning

- **PyTorch** 2.5.1+cu121 — primary deep learning framework
- **Transformers** 4.44.2 (HuggingFace) — Phi-3, MiniLM
- **PEFT** — LoRA fine-tuning
- **Sentence-Transformers** — multilingual semantic embeddings
- **Ultralytics YOLOv8** — object detection
- **OpenAI Whisper** — speech-to-text
- **EasyOCR** (JaidedAI) — multilingual OCR
- **scikit-learn** — classical metrics and cross-validation

### Models Used

| Model | Type | Role | Source |
|-------|------|------|--------|
| **Whisper medium** | Transformer encoder-decoder | Speech-to-text (ASR) | OpenAI |
| **YOLOv8n** | CNN one-stage detector | Object detection | Ultralytics |
| **EasyOCR** | CRAFT + CRNN | Multilingual OCR | JaidedAI |
| **Phi-3-mini-4k** | Decoder-only Transformer | LLM reasoning | Microsoft |
| **MiniLM-L12-v2** | Distilled BERT | Semantic embeddings | Sentence-Transformers |
| **PharmaLogoNet** | Custom CNN (MobileNet-inspired) | Logo detection | Built from scratch |
| **MLP Calibration Head** | Multi-Layer Perceptron | Confidence calibration | Built from scratch |

### Data Processing

- **FFmpeg** — video preprocessing (audio extraction, frame sampling)
- **OpenCV** + **Pillow** — image processing
- **pandas** — tabular data manipulation
- **openpyxl** — Knowledge Base management (Excel)

### Visualization & Reporting

- **matplotlib** + **seaborn** — analytical charts
- **ReportLab** — automated PDF report generation
- **IPython / Jupyter** — interactive notebooks
- **Kaggle** — GPU compute environment (Tesla T4, P100, V100)

### Regulations & Standards

- **EU 655/2013** — Cosmetic claims regulation
- **EU AI Act 2024** — Article 13 (Right to Explanation)
- **ASA UK** — Cosmetic puffery jurisprudence
- **PASCAL VOC XML** — annotation format
- **COCO** — mAP metric standard

---

## Directory Structure

```
.
├── README.md                                       # This file
├── notebook_io6_final.ipynb                        # Main multimodal pipeline notebook (104 cells)
├── cnn-from-scratch-model.ipynb                    # CNN from scratch notebook (47 cells)
│
├── architecture/                                   # Pipeline architecture diagrams
│   ├── Pipeline_IO6_Architecture_v2.png            # Multimodal pipeline schema
│   ├── Pipeline_CNN_FromScratch.png                # CNN from scratch schema
│   └── Pipeline_MLP_Calibration_FromScratch.png    # MLP calibration head schema
│
├── data/                                           # Knowledge Base + reference data
│   └── IO6_Base_Reference_V3_FULL_ENRICHED.xlsx    # 309+ entries, 8 sheets
│
├── docs/                                           # Documentation & guides
│   ├── IO6_Project_Summary_EN.pdf                  # Project summary (English)
│   ├── IO6_Guide_Notebook_FR.pdf                   # Notebook walkthrough (French)
│   ├── CNN_Guide_Notebook_FR.pdf                   # CNN walkthrough (French)
│   ├── Guide_Dashboard_IO6_Defense.pdf             # Defense dashboard guide
│   ├── Challenges_Investigate_Rejected.png         # Rejected approaches schema
│   └── Limitations_Future_Work.png                 # Limitations + V2 roadmap
│
├── reports/                                        # Generated reports
│   ├── Dashboard_Visuals_Batch_Loaded.pdf          # 7-page analytical dashboard
│   ├── Rapport_Explicabilite_IO6.pdf               # Per-claim explainability report
│   └── Rapport_Video_*.pdf                         # Per-video compliance reports
│
└── results/                                        # Evaluation results
    ├── batch_eval_results.json                     # Multi-video batch results
    ├── final_model_evaluation.json                 # Final metrics
    ├── all_metrics.json                            # All loss functions
    ├── confusion_matrix_normalized.png             # Confusion matrix
    └── ablation_study.png                          # Ablation study chart
```

---

## Getting Started

### Prerequisites

- **Python** 3.10+
- **CUDA-capable GPU** (recommended : Tesla T4, P100, V100, or A100 with at least 16 GB VRAM)
- **FFmpeg** installed system-wide
- **Kaggle account** (for free GPU access) or local CUDA setup

### Installation

```bash
# Clone the repository
git clone https://github.com/<your-username>/io6-multimodal-fact-checking.git
cd io6-multimodal-fact-checking

# Install dependencies
pip install -q openai-whisper ultralytics easyocr transformers accelerate \
                bitsandbytes sentence-transformers openpyxl jiwer reportlab \
                peft scikit-learn pandas matplotlib seaborn

# Pin compatible versions (see notebook for details)
pip install Pillow==10.4.0 numpy==1.26.4
```

### Running the Multimodal Pipeline

```bash
# Open the main notebook in Jupyter or Kaggle
jupyter notebook notebook_io6_final.ipynb

# Run all cells in order — the pipeline will :
# 1. Load 6 open-source models
# 2. Extract audio + frames from input video
# 3. Run multimodal extraction (Whisper + YOLO + OCR + Phi-3)
# 4. Verify each claim against Knowledge Base + EU patterns
# 5. Generate verdicts with XAI explanations
# 6. Output a compliance PDF report
```

### Running the CNN from Scratch

```bash
# Open the CNN notebook
jupyter notebook cnn-from-scratch-model.ipynb

# The notebook auto-detects your GPU and adapts batch size + AMP accordingly
# Training takes ~12 epochs on Tesla T4 (~1 hour)
```

### Test on a Sample Video

```python
from process_video import process_video

result = process_video("path/to/cosmetic_ad.mp4")
print(f"Verdict : {result['global_verdict']}")
print(f"Trust Score : {result['trust_score']}%")
print(f"Claims TRUE : {result['n_true']} | FALSE : {result['n_false']}")
```

---

## Results

### Multimodal Pipeline (vs strict EU 655/2013 Gold Standard)

| Metric | Score | Threshold (Excellent) |
|--------|-------|-----------------------|
| **Accuracy** | **92.9%** | ≥ 85% |
| **Precision (macro)** | **94.4%** | ≥ 85% |
| **Recall (macro)** | **91.7%** | ≥ 85% |
| **F1 Score (macro)** | **92.5%** | ≥ 85% |
| **F1 Score (weighted)** | **92.7%** | ≥ 85% |
| **F1 TRUE** | 90.9% | ≥ 85% |
| **F1 FALSE** | 94.1% | ≥ 85% |
| **Cohen's Kappa** | **1.0** | ≥ 0.8 |
| **Cross-Validation (3-fold)** | **100% ± 0%** | Stable |

**Key strengths :**
- Precision TRUE = 100% (zero false positive on legitimate claims)
- Recall FALSE = 100% (zero missed misleading claim — critical for safety)
- Conservative bias by design (safety-first approach for regulatory compliance)

### Computational Cost

- **~71 seconds per video** on Tesla T4 (16 GB VRAM)
- ~50 videos per hour on a single GPU
- VRAM peak : ~10 GB (load → use → unload pattern)

---

## Acknowledgments

This project was completed under the supervision of the academic team at **[Esprit School of Engineering](https://esprit.tn)**, as part of the IO6 — System Integration objective in the AI specialization (3rd year).

Special thanks to the open-source community for the foundational models that made this pipeline possible : OpenAI (Whisper), Microsoft (Phi-3), Ultralytics (YOLOv8), JaidedAI (EasyOCR), and the Sentence-Transformers / HuggingFace ecosystem.

### Academic References

- **Hu et al., 2022** — *LoRA: Low-Rank Adaptation of Large Language Models* (ICLR)
- **Ribeiro et al., 2016** — *"Why Should I Trust You?": Explaining the Predictions of Any Classifier* (LIME)
- **Lundberg & Lee, 2017** — *A Unified Approach to Interpreting Model Predictions* (SHAP)
- **Wachter et al., 2018** — *Counterfactual Explanations Without Opening the Black Box*
- **Selvaraju et al., 2017** — *Grad-CAM: Visual Explanations from Deep Networks*
- **Howard et al., 2017** — *MobileNets: Efficient Convolutional Neural Networks for Mobile Vision*
- **Rezatofighi et al., 2019** — *Generalized Intersection over Union* (CVPR)
- **EU 655/2013** — Commission Regulation laying down common criteria for the justification of claims used in relation to cosmetic products
- **EU AI Act 2024** — Article 13 on transparency and explainability of AI systems

---

## License

This project is released for academic and research purposes under the MIT License. The pretrained models retain their original licenses (MIT for Whisper and Phi-3, AGPL for YOLOv8, Apache 2.0 for EasyOCR and Sentence-Transformers).

---

## Topics

`python` `machine-learning` `deep-learning` `multimodal-ai` `fact-checking` `computer-vision` `natural-language-processing` `cnn-from-scratch` `pytorch` `transformers` `whisper` `yolov8` `phi-3` `lora-fine-tuning` `xai` `lime` `shap` `gradcam` `eu-ai-act` `cosmetic-claims` `regulatory-compliance` `kaggle` `jupyter-notebook` `esprit-school-of-engineering` `cbl` `system-integration`
