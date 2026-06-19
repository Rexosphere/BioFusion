from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, UnidentifiedImageError

from backend.inference import ModelUnavailableError, PneumoniaInferenceService


ROOT = Path(__file__).resolve().parents[1]
METRICS_PATH = ROOT / "config/model_metrics.json"

app = FastAPI(title="Rexosphere Pneumonia AI")
service = PneumoniaInferenceService(output_dir=ROOT / "outputs/gradcam")

app.mount("/assets", StaticFiles(directory=ROOT / "assets"), name="assets")
app.mount("/outputs", StaticFiles(directory=ROOT / "outputs"), name="outputs")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(ROOT / "index.html")


@app.get("/api/health")
def health() -> dict[str, object]:
    return {
        "ok": True,
        "modelLoaded": service.model is not None,
        "modelPath": str(service.model_path) if service.model_path else None,
    }


@app.get("/api/performance")
def performance() -> dict[str, object]:
    if not METRICS_PATH.exists():
        raise HTTPException(status_code=404, detail="Performance metrics file is not available.")
    return json.loads(METRICS_PATH.read_text())


@app.post("/api/diagnose")
async def diagnose(image: UploadFile = File(...)) -> dict[str, object]:
    try:
        pil_image = Image.open(image.file)
        result = service.predict(pil_image)
    except UnidentifiedImageError as exc:
        raise HTTPException(status_code=400, detail="Uploaded file is not a valid image.") from exc
    except ModelUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=f"Inference failed: {exc}") from exc

    return {
        "predictionClass": result.prediction_class,
        "confidence": result.confidence,
        "threshold": result.threshold,
        "inferenceTimeMs": result.inference_time_ms,
        "recommendation": result.recommendation,
        "gradcamOverlayUrl": result.gradcam_overlay_url,
        "gradcamHeatmapUrl": result.gradcam_heatmap_url,
    }
