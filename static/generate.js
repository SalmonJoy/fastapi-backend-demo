const state = {
  models: [],
  loadingModels: false,
  generating: false,
};

const elements = {
  statusBanner: document.querySelector("#statusBanner"),
  generateForm: document.querySelector("#generateForm"),
  sourceSelect: document.querySelector("#sourceSelect"),
  modelSelect: document.querySelector("#modelSelect"),
  textInput: document.querySelector("#textInput"),
  generateButton: document.querySelector("#generateButton"),
  outputBox: document.querySelector("#outputBox"),
};

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[character]));
}

function getModelSource(model) {
  if (model.provider === "gemini") {
    return "gemini";
  }

  if (model.provider === "ollama" && model.type === "cloud") {
    return "ollama-cloud";
  }

  if (model.provider === "ollama" && model.type === "local") {
    return "ollama-local";
  }

  return "";
}

function setStatus(message = "", isError = false) {
  elements.statusBanner.className = message
    ? `status-banner${isError ? " error" : ""}`
    : "status-banner hidden";
  elements.statusBanner.textContent = message;
}

function getModelsForSelectedSource() {
  return state.models.filter((model) => (
    getModelSource(model) === elements.sourceSelect.value &&
    model.supports_generate !== false
  ));
}

function renderModelOptions() {
  const models = getModelsForSelectedSource();

  elements.modelSelect.innerHTML = models.map((model) => (
    `<option value="${escapeHtml(model.name)}">${escapeHtml(model.name)}</option>`
  )).join("");

  elements.modelSelect.disabled = !models.length || state.loadingModels;
  elements.generateButton.disabled = state.loadingModels || state.generating || !models.length;

  if (!models.length && !state.loadingModels) {
    elements.outputBox.textContent = "No models are available for the selected source.";
  }
}

async function loadModels() {
  state.loadingModels = true;
  setStatus("Loading models...");
  renderModelOptions();

  try {
    const response = await fetch("/models", { cache: "no-store" });
    const payload = await response.json();

    if (!response.ok) {
      throw new Error(payload.detail || "Unable to load models");
    }

    state.models = Array.isArray(payload.models) ? payload.models : [];
    setStatus("");
  } catch (error) {
    state.models = [];
    setStatus(error.message || "Unable to load models", true);
  } finally {
    state.loadingModels = false;
    renderModelOptions();
  }
}

async function generateText(event) {
  event.preventDefault();

  const text = elements.textInput.value.trim();
  const model = elements.modelSelect.value;
  const provider = elements.sourceSelect.value;

  if (!text) {
    setStatus("Enter text before generating.", true);
    elements.textInput.focus();
    return;
  }

  if (!model) {
    setStatus("Select a model before generating.", true);
    elements.modelSelect.focus();
    return;
  }

  state.generating = true;
  elements.generateButton.disabled = true;
  elements.outputBox.textContent = "Generating...";
  setStatus("");

  try {
    const response = await fetch("/generate", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        provider,
        model,
        text,
      }),
    });
    const payload = await response.json();

    if (!response.ok) {
      throw new Error(payload.detail || "Generation failed");
    }

    elements.outputBox.textContent = payload.output || "The model returned an empty response.";
  } catch (error) {
    elements.outputBox.textContent = "";
    setStatus(error.message || "Generation failed", true);
  } finally {
    state.generating = false;
    renderModelOptions();
  }
}

elements.sourceSelect.addEventListener("change", renderModelOptions);
elements.generateForm.addEventListener("submit", generateText);

loadModels();
