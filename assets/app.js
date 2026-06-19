const state = {
  selectedFile: null,
  previewUrl: "",
  lastDiagnosis: null,
  endpoint: "/api/diagnose",
  camMode: "overlay",
  camOpacity: 0.55,
};

const fallbackPerformanceMetrics = [
  { label: "Accuracy", value: "Not available" },
  { label: "Precision", value: "Not available" },
  { label: "Recall / Sensitivity", value: "Not available" },
  { label: "F1-score", value: "Not available" },
  { label: "ROC-AUC", value: "Not available" },
  { label: "PR-AUC", value: "Not available" },
  { label: "Threshold", value: "Not available" },
  { label: "Confusion Matrix", value: "Not available" },
];

const navItems = document.querySelectorAll(".nav-item");
const screens = document.querySelectorAll(".screen");
const fileInput = document.getElementById("xray-input");
const previewFrame = document.getElementById("preview-frame");
const previewImage = document.getElementById("preview-image");
const previewEmpty = document.getElementById("preview-empty");
const diagnoseButton = document.getElementById("diagnose-button");
const diagnoseIcon = document.getElementById("diagnose-icon");
const diagnoseLabel = document.getElementById("diagnose-label");
const clearButton = document.getElementById("clear-button");
const diagnosisError = document.getElementById("diagnosis-error");
const backendStatus = document.getElementById("backend-status");
const endpointInput = document.getElementById("endpoint-input");
const camCanvas = document.getElementById("cam-canvas");
const camOriginal = document.getElementById("cam-original");
const camOverlay = document.getElementById("cam-overlay");
const camHeatmap = document.getElementById("cam-heatmap");
const camEmpty = document.getElementById("cam-empty");

function showScreen(targetId) {
  screens.forEach((screen) => screen.classList.toggle("active", screen.id === targetId));
  navItems.forEach((item) => item.classList.toggle("active", item.dataset.target === targetId));
  document.getElementById("sidebar").classList.remove("open");
}

function setLoading(isLoading) {
  diagnoseButton.disabled = isLoading || !state.selectedFile;
  diagnoseIcon.textContent = isLoading ? "hourglass_empty" : "psychology";
  diagnoseLabel.textContent = isLoading ? "Analyzing..." : "Run Diagnosis";
}

function setBackendStatus(text, mode = "neutral") {
  backendStatus.textContent = text;
  backendStatus.className = `status-pill ${mode}`;
}

function resetDiagnosis() {
  state.lastDiagnosis = null;
  document.getElementById("result-class").textContent = "Not available";
  document.getElementById("result-confidence").textContent = "Not available";
  document.getElementById("result-threshold").textContent = "Not available";
  document.getElementById("result-time").textContent = "Not available";
  document.getElementById("result-recommendation").textContent = "Run a backend-connected diagnosis to populate this screen.";
  document.getElementById("result-icon").textContent = "pending";
  renderGradCam();
}

function formatPercent(value) {
  if (value === undefined || value === null || value === "") return "Not available";
  const numeric = Number(value);
  if (Number.isNaN(numeric)) return String(value);
  return numeric <= 1 ? `${(numeric * 100).toFixed(1)}%` : `${numeric.toFixed(1)}%`;
}

function renderDiagnosis(data) {
  state.lastDiagnosis = data || {};
  document.getElementById("result-class").textContent = data.predictionClass || data.class || data.label || "Not available";
  document.getElementById("result-confidence").textContent = formatPercent(data.confidence ?? data.probability);
  document.getElementById("result-threshold").textContent = data.threshold ?? "Not available";
  document.getElementById("result-time").textContent = data.inferenceTimeMs ? `${data.inferenceTimeMs} ms` : "Not available";
  document.getElementById("result-recommendation").textContent = data.recommendation || "Review with a qualified clinician. This output is decision support only.";
  document.getElementById("result-icon").textContent = "clinical_notes";
  renderGradCam();
}

function renderGradCam() {
  const data = state.lastDiagnosis || {};
  const overlayUrl = data.gradcamOverlayUrl || data.gradCamOverlayUrl || "";
  const heatmapUrl = data.gradcamHeatmapUrl || data.gradCamHeatmapUrl || "";

  camCanvas.className = `cam-canvas mode-${state.camMode}`;
  camOriginal.src = state.previewUrl || "";
  camOverlay.src = overlayUrl;
  camHeatmap.src = heatmapUrl;
  camOverlay.style.opacity = state.camOpacity;

  if (state.previewUrl) camCanvas.classList.add("has-original");
  if (overlayUrl) camCanvas.classList.add("has-overlay");
  if (heatmapUrl) camCanvas.classList.add("has-heatmap");

  camOriginal.style.display = state.camMode === "heatmap" || !state.previewUrl ? "none" : "block";
  camOverlay.style.display = state.camMode === "overlay" && overlayUrl ? "block" : "none";
  camHeatmap.style.display = state.camMode === "heatmap" && heatmapUrl ? "block" : "none";

  const hasRequestedImage = Boolean(
    (state.camMode === "original" && state.previewUrl) ||
      (state.camMode === "overlay" && (state.previewUrl || overlayUrl)) ||
      (state.camMode === "heatmap" && heatmapUrl),
  );

  camEmpty.style.display = hasRequestedImage ? "none" : "block";
}

async function runDiagnosis() {
  if (!state.selectedFile) return;

  setLoading(true);
  diagnosisError.textContent = "";
  setBackendStatus("Calling backend...", "neutral");

  try {
    const formData = new FormData();
    formData.append("image", state.selectedFile);

    const response = await fetch(state.endpoint, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      let detail = `Backend returned HTTP ${response.status}`;
      try {
        const errorBody = await response.json();
        detail = errorBody.detail || detail;
      } catch (_error) {
        detail = response.statusText || detail;
      }
      throw new Error(detail);
    }

    const data = await response.json();
    renderDiagnosis(data);
    setBackendStatus("Backend connected", "ready");
    showScreen("results-screen");
  } catch (error) {
    resetDiagnosis();
    diagnosisError.textContent = `Diagnosis backend unavailable: ${error.message}. Configure ${state.endpoint} or update the API setting.`;
    setBackendStatus("Backend unavailable", "error");
  } finally {
    setLoading(false);
  }
}

function handleFile(file) {
  if (!file) return;
  state.selectedFile = file;
  if (state.previewUrl) URL.revokeObjectURL(state.previewUrl);
  state.previewUrl = URL.createObjectURL(file);
  previewImage.src = state.previewUrl;
  previewFrame.classList.remove("empty");
  previewEmpty.style.display = "none";
  diagnoseButton.disabled = false;
  clearButton.disabled = false;
  diagnosisError.textContent = "";
  resetDiagnosis();
  renderGradCam();
}

function clearUpload() {
  state.selectedFile = null;
  if (state.previewUrl) URL.revokeObjectURL(state.previewUrl);
  state.previewUrl = "";
  fileInput.value = "";
  previewImage.src = "";
  previewFrame.classList.add("empty");
  previewEmpty.style.display = "block";
  diagnoseButton.disabled = true;
  clearButton.disabled = true;
  diagnosisError.textContent = "";
  resetDiagnosis();
}

function renderPerformanceCards(metrics) {
  const container = document.getElementById("performance-cards");
  container.innerHTML = metrics
    .map(
      (metric) => `
        <article class="panel metric-card ${metric.isWide ? 'wide' : ''}" ${metric.isWide ? 'style="grid-column: 1 / -1;"' : ''}>
          <span>${metric.label}</span>
          ${metric.isHtml ? metric.value : `<strong>${metric.value}</strong>`}
        </article>
      `,
    )
    .join("");
}

function formatMetric(value, isPercent = false, fallback = "Not available") {
  if (value === undefined || value === null || value === "") return fallback;
  if (typeof value === "number") {
    if (isPercent) return (value * 100).toFixed(2) + "%";
    return Number.isInteger(value) ? String(value) : value.toFixed(4);
  }
  return String(value);
}

async function loadPerformanceMetrics() {
  try {
    const response = await fetch("/api/performance");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    
    const matrix = data.confusion_matrix;
    let matrixHtml = "Not available";
    if (matrix && Array.isArray(matrix) && matrix.length === 2) {
      matrixHtml = `
        <table class="confusion-matrix-table" style="width: 100%; border-collapse: collapse; margin-top: 1rem; text-align: right;">
          <thead>
            <tr style="border-bottom: 1px solid var(--border-color, #e5e7eb);">
              <th style="text-align: left; padding: 0.5rem;">Actual \\ Predicted</th>
              <th style="padding: 0.5rem;">Normal</th>
              <th style="padding: 0.5rem;">Pneumonia</th>
            </tr>
          </thead>
          <tbody>
            <tr style="border-bottom: 1px solid var(--border-color, #e5e7eb);">
              <td style="text-align: left; padding: 0.5rem;">Normal</td>
              <td style="padding: 0.5rem;">${matrix[0][0]}</td>
              <td style="padding: 0.5rem;">${matrix[0][1]}</td>
            </tr>
            <tr>
              <td style="text-align: left; padding: 0.5rem;">Pneumonia</td>
              <td style="padding: 0.5rem;">${matrix[1][0]}</td>
              <td style="padding: 0.5rem;">${matrix[1][1]}</td>
            </tr>
          </tbody>
        </table>
      `;
    }

    renderPerformanceCards([
      { label: "Accuracy", value: formatMetric(data.accuracy, true) },
      { label: "Precision", value: formatMetric(data.precision, true) },
      { label: "Recall / Sensitivity", value: formatMetric(data.recall, true) },
      { label: "F1-score", value: formatMetric(data.f1_score, true) },
      { label: "ROC-AUC", value: formatMetric(data.roc_auc, false, "Not computed") },
      { label: "PR-AUC", value: formatMetric(data.pr_auc, false, "Not computed") },
      { label: "Threshold", value: data.threshold !== undefined ? data.threshold : 0.25 },
      { label: "Confusion Matrix", value: matrixHtml, isHtml: true, isWide: true },
    ]);
  } catch (_error) {
    renderPerformanceCards(fallbackPerformanceMetrics);
  }
}

navItems.forEach((item) => item.addEventListener("click", () => showScreen(item.dataset.target)));

document.getElementById("theme-toggle").addEventListener("click", () => {
  document.documentElement.classList.toggle("dark");
  localStorage.setItem("rexosphere-theme", document.documentElement.classList.contains("dark") ? "dark" : "light");
});

document.getElementById("menu-toggle").addEventListener("click", () => {
  document.getElementById("sidebar").classList.toggle("open");
});

fileInput.addEventListener("change", (event) => handleFile(event.target.files[0]));
diagnoseButton.addEventListener("click", runDiagnosis);
clearButton.addEventListener("click", clearUpload);

endpointInput.addEventListener("input", (event) => {
  state.endpoint = event.target.value.trim() || "/api/diagnose";
});

document.getElementById("opacity-slider").addEventListener("input", (event) => {
  state.camOpacity = Number(event.target.value) / 100;
  renderGradCam();
});

document.querySelectorAll("[data-cam-mode]").forEach((button) => {
  button.addEventListener("click", () => {
    state.camMode = button.dataset.camMode;
    document.querySelectorAll("[data-cam-mode]").forEach((item) => item.classList.toggle("active", item === button));
    renderGradCam();
  });
});

if (localStorage.getItem("rexosphere-theme") === "dark") {
  document.documentElement.classList.add("dark");
}

loadPerformanceMetrics();
renderGradCam();
