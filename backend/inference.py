from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image
from torchvision import transforms
from torchvision.models import densenet121


MODEL_CANDIDATES = (
    Path("models/Pneumonia_DenseNet121_Final.pth"),
    Path("models/best_phase2.pth"),
)
CLASS_NAMES = ("Normal", "Pneumonia")
THRESHOLD = 0.25


@dataclass
class PredictionResult:
    prediction_class: str
    confidence: float
    threshold: float
    inference_time_ms: int
    recommendation: str
    gradcam_overlay_url: str
    gradcam_heatmap_url: str


class ModelUnavailableError(RuntimeError):
    pass


class GradCAM:
    def __init__(self, model: torch.nn.Module, target_layer: torch.nn.Module):
        self.model = model
        self.target_layer = target_layer
        self.activations: torch.Tensor | None = None
        self.gradients: torch.Tensor | None = None
        self.forward_handle = target_layer.register_forward_hook(self._forward_hook)
        self.backward_handle = target_layer.register_full_backward_hook(self._backward_hook)

    def _forward_hook(self, _module: torch.nn.Module, _inputs: Any, output: torch.Tensor) -> None:
        self.activations = output

    def _backward_hook(self, _module: torch.nn.Module, _grad_input: Any, grad_output: Any) -> None:
        self.gradients = grad_output[0]

    def remove(self) -> None:
        self.forward_handle.remove()
        self.backward_handle.remove()

    def generate(self, image_tensor: torch.Tensor, class_idx: int) -> np.ndarray:
        self.model.zero_grad(set_to_none=True)
        logits = self.model(image_tensor)
        score = logits[0, class_idx]
        score.backward(retain_graph=True)

        if self.activations is None or self.gradients is None:
            raise RuntimeError("Grad-CAM hooks did not capture activations and gradients.")

        grads = self.gradients[0]
        acts = self.activations[0]
        weights = grads.mean(dim=(1, 2))
        cam = (weights[:, None, None] * acts).sum(dim=0)
        cam = F.relu(cam)
        cam = cam - cam.min()
        cam = cam / (cam.max() + 1e-8)
        cam = cam.unsqueeze(0).unsqueeze(0)
        cam = F.interpolate(cam, size=(224, 224), mode="bilinear", align_corners=False)
        return cam[0, 0].detach().cpu().numpy()


class PneumoniaInferenceService:
    def __init__(self, output_dir: Path = Path("outputs/gradcam")) -> None:
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.model_path = self._find_model_path()
        self.model: torch.nn.Module | None = None
        self.transform = transforms.Compose(
            [
                transforms.Resize((224, 224)),
                transforms.Grayscale(num_output_channels=3),
                transforms.ToTensor(),
                transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
            ]
        )

    def _find_model_path(self) -> Path | None:
        for path in MODEL_CANDIDATES:
            if path.exists():
                return path
        return None

    def load(self) -> None:
        if self.model is not None:
            return
        if self.model_path is None:
            raise ModelUnavailableError(
                "No trained model found. Place Pneumonia_DenseNet121_Final.pth or best_phase2.pth in the models/ directory."
            )

        model = densenet121(weights=None)
        model.classifier = torch.nn.Linear(model.classifier.in_features, 2)

        checkpoint = torch.load(self.model_path, map_location=self.device)
        state_dict = checkpoint.get("model_state_dict", checkpoint) if isinstance(checkpoint, dict) else checkpoint
        if isinstance(state_dict, dict):
            state_dict = {key.replace("module.", ""): value for key, value in state_dict.items()}
        model.load_state_dict(state_dict)
        model.to(self.device)
        model.eval()
        self.model = model

    def predict(self, image: Image.Image) -> PredictionResult:
        self.load()
        assert self.model is not None

        original = image.convert("RGB")
        tensor = self.transform(original).unsqueeze(0).to(self.device)
        started = time.perf_counter()

        with torch.no_grad():
            logits = self.model(tensor)
            probabilities = torch.softmax(logits, dim=1)[0]
            pneumonia_probability = float(probabilities[1].detach().cpu())

        prediction_idx = 1 if pneumonia_probability >= THRESHOLD else 0
        confidence = pneumonia_probability if prediction_idx == 1 else 1.0 - pneumonia_probability
        inference_time_ms = int((time.perf_counter() - started) * 1000)

        heatmap = GradCAM(self.model, self.model.features.denseblock4)
        try:
            cam = heatmap.generate(tensor, prediction_idx)
        finally:
            heatmap.remove()

        overlay_url, heatmap_url = self._save_gradcam_images(original, cam)

        recommendation = (
            "Pneumonia probability is above the configured recall-focused threshold. Clinical review is recommended."
            if prediction_idx == 1
            else "Pneumonia probability is below the configured threshold. Clinical review is still required before any decision."
        )

        return PredictionResult(
            prediction_class=CLASS_NAMES[prediction_idx],
            confidence=confidence,
            threshold=THRESHOLD,
            inference_time_ms=inference_time_ms,
            recommendation=recommendation,
            gradcam_overlay_url=overlay_url,
            gradcam_heatmap_url=heatmap_url,
        )

    def _save_gradcam_images(self, original: Image.Image, cam: np.ndarray) -> tuple[str, str]:
        case_id = uuid4().hex
        original_224 = original.resize((224, 224)).convert("RGB")
        heatmap = self._colorize_heatmap(cam)
        overlay = Image.blend(original_224, heatmap, alpha=0.45)

        heatmap_path = self.output_dir / f"{case_id}_heatmap.png"
        overlay_path = self.output_dir / f"{case_id}_overlay.png"
        heatmap.save(heatmap_path)
        overlay.save(overlay_path)
        return f"/outputs/gradcam/{overlay_path.name}", f"/outputs/gradcam/{heatmap_path.name}"

    @staticmethod
    def _colorize_heatmap(cam: np.ndarray) -> Image.Image:
        cam_uint8 = np.uint8(np.clip(cam, 0, 1) * 255)
        red = cam_uint8
        green = np.uint8(np.clip(255 - np.abs(cam_uint8.astype(np.int16) - 150) * 2, 0, 255))
        blue = 255 - cam_uint8
        alpha = np.full_like(cam_uint8, 255)
        rgba = np.stack([red, green, blue, alpha], axis=-1)
        return Image.fromarray(rgba, mode="RGBA").convert("RGB")
