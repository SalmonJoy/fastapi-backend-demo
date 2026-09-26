const state = {
  models: [],
  providers: [],
  loading: false,
  error: "",
};

const elements = {
  refreshButton: document.querySelector("#refreshButton"),
  statusBanner: document.querySelector("#statusBanner"),
  totalModels: document.querySelector("#totalModels"),
  localModels: document.querySelector("#localModels"),
  cloudModels: document.querySelector("#cloudModels"),
  onlineProviders: document.querySelector("#onlineProviders"),
  providerGrid: document.querySelector("#providerGrid"),
  sourceFilter: document.querySelector("#sourceFilter"),
  modelsTableBody: document.querySelector("#modelsTableBody"),
  emptyState: document.querySelector("#emptyState"),
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

function formatProviderName(provider) {
  return provider || "unknown";
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

function getModelDetails(model) {
  const details = model.details || {};
  const values = [];

  if (details.id) {
    values.push(["ID", details.id]);
  }

  if (details.owned_by) {
    values.push(["Owner", details.owned_by]);
  }

  if (details.object) {
    values.push(["Object", details.object]);
  }

  if (details.displayName) {
    values.push(["Display", details.displayName]);
  }

  if (details.family) {
    values.push(["Family", details.family]);
  }

  if (details.parameter_size) {
    values.push(["Size", details.parameter_size]);
  }

  if (details.quantization_level) {
    values.push(["Quant", details.quantization_level]);
  }

  if (details.inputTokenLimit) {
    values.push(["Input", `${details.inputTokenLimit} tokens`]);
  }

  if (details.outputTokenLimit) {
    values.push(["Output", `${details.outputTokenLimit} tokens`]);
  }

  if (Array.isArray(details.capabilities) && details.capabilities.length) {
    values.push(["Capabilities", details.capabilities.join(", ")]);
  }

  if (details.supports_generate === false) {
    values.push(["Generate", "No"]);
  }

  if (details.details?.id && details.details.id !== details.id) {
    values.push(["ID", details.details.id]);
  }

  return values;
}

function getFilteredModels() {
  return state.models.filter((model) => getModelSource(model) === elements.sourceFilter.value);
}

function renderStatusBanner() {
  elements.statusBanner.className = "status-banner hidden";
  elements.statusBanner.textContent = "";

  if (state.loading) {
    elements.statusBanner.className = "status-banner";
    elements.statusBanner.textContent = "Loading models...";
    return;
  }

  if (state.error) {
    elements.statusBanner.className = "status-banner error";
    elements.statusBanner.textContent = state.error;
  }
}

function renderStats() {
  const localCount = state.models.filter((model) => model.type === "local").length;
  const cloudCount = state.models.filter((model) => model.type === "cloud").length;
  const onlineCount = state.providers.filter((provider) => provider.ok).length;

  elements.totalModels.textContent = state.models.length;
  elements.localModels.textContent = localCount;
  elements.cloudModels.textContent = cloudCount;
  elements.onlineProviders.textContent = onlineCount;
}

function renderProviders() {
  if (!state.providers.length) {
    elements.providerGrid.innerHTML = `
      <article class="provider-card">
        <div class="provider-topline">
          <span class="provider-name">No providers</span>
          <span class="badge error">Empty</span>
        </div>
        <p class="provider-meta">No provider status was returned.</p>
      </article>
    `;
    return;
  }

  elements.providerGrid.innerHTML = state.providers.map((provider) => {
    const ok = Boolean(provider.ok);
    const configured = provider.configured ? "Configured" : "Not configured";
    const modelCount = provider.data?.models?.length || 0;
    const statusLabel = ok ? "Online" : configured;
    const badgeClass = ok ? "ok" : "error";
    const meta = ok
      ? `${modelCount} model${modelCount === 1 ? "" : "s"} available`
      : provider.error || "Provider is not returning models";

    return `
      <article class="provider-card">
        <div class="provider-topline">
          <span class="provider-name">${escapeHtml(formatProviderName(provider.provider))}</span>
          <span class="badge ${badgeClass}">${escapeHtml(statusLabel)}</span>
        </div>
        <p class="provider-meta">${escapeHtml(provider.type || "unknown")} provider</p>
        <p class="provider-meta">${escapeHtml(meta)}</p>
      </article>
    `;
  }).join("");
}

function renderTable() {
  const filteredModels = getFilteredModels();
  elements.emptyState.classList.toggle("hidden", filteredModels.length > 0 || state.loading);

  elements.modelsTableBody.innerHTML = filteredModels.map((model) => {
    const details = getModelDetails(model);
    const detailsHtml = details.length
      ? details.map(([label, value]) => `<span class="detail-chip">${escapeHtml(label)}: ${escapeHtml(value)}</span>`).join("")
      : `<span class="detail-chip">No extra details</span>`;

    return `
      <tr>
        <td><span class="model-name">${escapeHtml(model.name || "Unnamed model")}</span></td>
        <td>${escapeHtml(formatProviderName(model.provider))}</td>
        <td><span class="badge ${model.type === "cloud" ? "cloud" : "local"}">${escapeHtml(model.type || "unknown")}</span></td>
        <td><div class="detail-list">${detailsHtml}</div></td>
      </tr>
    `;
  }).join("");
}

function render() {
  renderStatusBanner();
  renderStats();
  renderProviders();
  renderTable();
  elements.refreshButton.disabled = state.loading;
}

async function loadModels() {
  state.loading = true;
  state.error = "";
  render();

  try {
    const response = await fetch("/models", { cache: "no-store" });
    const payload = await response.json();

    if (!response.ok) {
      throw new Error(payload.detail || "Unable to load models");
    }

    state.models = Array.isArray(payload.models) ? payload.models : [];
    state.providers = Array.isArray(payload.providers) ? payload.providers : [];
  } catch (error) {
    state.models = [];
    state.providers = [];
    state.error = error.message || "Unable to load models";
  } finally {
    state.loading = false;
    render();
  }
}

elements.refreshButton.addEventListener("click", loadModels);
elements.sourceFilter.addEventListener("change", renderTable);

loadModels();
