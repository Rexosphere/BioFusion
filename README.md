# Rexosphere Pneumonia AI

Explainable Pneumonia Detection Using Two-Phase Fine-Tuned DenseNet121 for BioFusion Hackathon 2026.

## Web App

The Stitch-generated visual direction has been integrated as a plain HTML/CSS/JS frontend:

- `index.html` defines the app shell, sidebar navigation, topbar, and all product screens.
- `assets/styles.css` contains the unified responsive light/dark theme.
- `assets/app.js` handles navigation, upload preview, diagnosis API calls, result rendering, Grad-CAM controls, and frontend configuration.
- `backend/app.py` serves the frontend and exposes the API.
- `backend/inference.py` loads the trained DenseNet121 model, runs inference, and generates Grad-CAM images.
- `config/model_metrics.json` stores exported notebook performance metrics used by `/api/performance`.

### Screens

- Upload & Diagnose
- Diagnosis Result
- Grad-CAM Explainability
- Model Performance
- Training Method
- Dataset
- Robustness & Quality
- Research
- Settings/About

### Backend integration

The frontend is connected to:

```text
POST /api/diagnose
GET /api/performance
GET /api/health
```

Diagnosis requests are sent as `multipart/form-data` with one field:

```text
image
```

Supported response fields are:

```json
{
  "predictionClass": "Normal or Pneumonia",
  "confidence": 0.94,
  "threshold": 0.25,
  "inferenceTimeMs": 123,
  "recommendation": "Clinical review recommended.",
  "gradcamOverlayUrl": "/path/to/overlay.png",
  "gradcamHeatmapUrl": "/path/to/heatmap.png"
}
```

No backend predictions are faked in the UI. If the trained model file is missing, `/api/diagnose` returns `503` and the upload screen shows a clear backend error.

### Model file

Export the trained notebook model and place one of these files in `models/`:

```text
models/Pneumonia_DenseNet121_Final.pth
models/best_phase2.pth
```

The backend expects a PyTorch DenseNet121 state dict matching:

```text
torchvision.models.densenet121(weights=IMAGENET1K_V1)
classifier replaced with Linear(1024, 2)
classes: Normal, Pneumonia
```

### Run locally

```bash
cd /home/ifaz/Coding/BioFusion
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

Then open:

```text
http://127.0.0.1:8000
```

If port `8000` is already in use:

```bash
.venv/bin/uvicorn backend.app:app --host 127.0.0.1 --port 8010
```

Then open:

```text
http://127.0.0.1:8010
```

### How to use the app

1. Start the FastAPI app with Uvicorn.
2. Open the app URL in a browser.
3. Go to Upload & Diagnose.
4. Select a chest X-ray image.
5. Click Run Diagnosis.
6. Review Diagnosis Result for class, confidence, threshold, inference time, recommendation, and disclaimer.
7. Open Grad-CAM to inspect the original image, overlay, or heatmap. Use the opacity slider for overlay review.
8. Open Model Performance, Dataset, Training Method, Robustness & Quality, and Research for project documentation.

Diagnosis and Grad-CAM require a real trained `.pth` file in `models/`. Without it, the rest of the app still runs and diagnosis requests fail safely with an explicit model-missing message.
