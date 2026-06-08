import torch
import torch.nn as nn
from torchvision import models, transforms
from facenet_pytorch import MTCNN
from pytorch_grad_cam import GradCAM
from pytorch_grad_cam.utils.model_targets import ClassifierOutputTarget
from pytorch_grad_cam.utils.image import show_cam_on_image
import cv2
import numpy as np
from PIL import Image
from transformers import AutoProcessor, LlavaForConditionalGeneration

class DeepfakeDetector:
    def __init__(self, model_path, device=None):
        self.device = device if device else torch.device('cuda' if torch.cuda.is_available() else 'cpu')
       
        # --- 1. INITIALISATION RESNET50 ---
        self.model = models.resnet50(weights=None)
        num_ftrs = self.model.fc.in_features
        self.model.fc = nn.Linear(num_ftrs, 2)
        self.model.load_state_dict(torch.load(model_path, map_location=self.device))
        self.model.to(self.device)
        self.model.eval()
       
        self.mtcnn = MTCNN(keep_all=False, device=self.device)
       
        self.transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ])
       
        self.target_layer = self.model.layer4[-1]
        self.cam = GradCAM(model=self.model, target_layers=[self.target_layer])

        # --- 2. INITIALISATION LLAVA (Texte) ---
        print("Chargement du modèle LLaVA (cela peut prendre du temps la première fois)...")
        vlm_model_id = "llava-hf/llava-1.5-7b-hf"
        self.vlm_processor = AutoProcessor.from_pretrained(vlm_model_id)
        # On charge en 4-bit pour économiser la RAM du serveur
        self.vlm_model = LlavaForConditionalGeneration.from_pretrained(
            vlm_model_id,
            device_map="auto",
            load_in_4bit=True
        )

    def predict_and_explain(self, video_path):
        """Prédit Fake/Real, génère Grad-CAM et rédige l'explication textuelle."""
        # Lecture vidéo
        cap = cv2.VideoCapture(video_path)
        ret, frame = cap.read()
        cap.release()
       
        if not ret:
            return {"error": "Erreur lecture vidéo"}, None

        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
       
        # Détection visage
        face = self.mtcnn(frame_rgb)
        if face is None:
            return {"error": "Aucun visage détecté"}, None
           
        # --- PHASE 1 : VISION (ResNet50) ---
        face_pil = transforms.ToPILImage()(face / 255.0)
        input_tensor = self.transform(face_pil).unsqueeze(0).to(self.device)
       
        with torch.no_grad():
            output = self.model(input_tensor)
            prob = torch.softmax(output, dim=1)
            conf, pred = torch.max(prob, 1)
            label = "FAKE" if pred.item() == 0 else "REAL"
           
        # Grad-CAM
        targets = [ClassifierOutputTarget(0)]
        grayscale_cam = self.cam(input_tensor=input_tensor, targets=targets)[0, :]
        img_float = np.array(face_pil.resize((224, 224))) / 255.0
        cam_image = show_cam_on_image(img_float, grayscale_cam, use_rgb=True)
       
        # --- PHASE 2 : TEXTE (LLaVA) ---
        heatmap_pil = Image.fromarray(cam_image).convert("RGB")
        prompt = """USER: <image>
You are an expert AI forensic analyst looking at a Grad-CAM heatmap overlaid on a face.
Task 1: Describe the exact geographical location of the bright red and yellow "hot zones" on the image without guessing.
Task 2: If the hot zones are tightly concentrated in the center of the face, conclude it is a 'FAKE' face-swap mask. If the hot zones are off-center, on the edges, or scattered, conclude it is a 'REAL' unmanipulated image.
Be concise and factual. ASSISTANT:"""
       
        inputs = self.vlm_processor(text=prompt, images=heatmap_pil, return_tensors="pt").to(self.device)
       
        with torch.no_grad():
            generated_ids = self.vlm_model.generate(
                **inputs,
                max_new_tokens=100,
                do_sample=True,
                temperature=0.4,
                top_p=0.9
            )
           
        generated_text = self.vlm_processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
        text_explanation = generated_text.split("ASSISTANT:")[-1].strip()
       
        # Retourne toutes les infos structurées
        return {
            "label": label,
            "confidence": conf.item(),
            "explanation": text_explanation
        }, cam_image