const state = {
  indexes: [],
  loadingIndexes: false,
  ingesting: false,
};

const elements = {
  statusBanner: document.querySelector("#statusBanner"),
  ingestForm: document.querySelector("#ingestForm"),
  indexSelect: document.querySelector("#indexSelect"),
  namespaceMode: document.querySelector("#namespaceMode"),
  existingNamespaceWrap: document.querySelector("#existingNamespaceWrap"),
  newNamespaceWrap: document.querySelector("#newNamespaceWrap"),
  namespaceSelect: document.querySelector("#namespaceSelect"),
  namespaceInput: document.querySelector("#namespaceInput"),
  chunkSizeInput: document.querySelector("#chunkSizeInput"),
  chunkOverlapInput: document.querySelector("#chunkOverlapInput"),
  textInput: document.querySelector("#textInput"),
  refreshIndexesButton: document.querySelector("#refreshIndexesButton"),
  ingestButton: document.querySelector("#ingestButton"),
  resultBox: document.querySelector("#resultBox"),
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

function setStatus(message = "", isError = false) {
  elements.statusBanner.className = message
    ? `status-banner${isError ? " error" : ""}`
    : "status-banner hidden";
  elements.statusBanner.textContent = message;
}

function getSelectedIndex() {
  return state.indexes.find((index) => index.name === elements.indexSelect.value);
}

function getNamespaceName() {
  if (elements.namespaceMode.value === "new") {
    return elements.namespaceInput.value.trim();
  }

  return elements.namespaceSelect.value;
}

function renderNamespaceControls() {
  const useNewNamespace = elements.namespaceMode.value === "new";
  elements.existingNamespaceWrap.classList.toggle("hidden", useNewNamespace);
  elements.newNamespaceWrap.classList.toggle("hidden", !useNewNamespace);
}

function renderNamespaces() {
  const index = getSelectedIndex();
  const namespaces = Array.isArray(index?.namespaces) ? index.namespaces : [];

  elements.namespaceSelect.innerHTML = namespaces.map((namespace) => (
    `<option value="${escapeHtml(namespace.name)}">${escapeHtml(namespace.name)} (${namespace.vector_count || 0})</option>`
  )).join("");

  if (!namespaces.length) {
    elements.namespaceSelect.innerHTML = '<option value="__default__">__default__ (0)</option>';
  }
}

function renderIndexes() {
  elements.indexSelect.innerHTML = state.indexes.map((index) => (
    `<option value="${escapeHtml(index.name)}">${escapeHtml(index.name)}</option>`
  )).join("");

  elements.indexSelect.disabled = state.loadingIndexes || !state.indexes.length;
  elements.refreshIndexesButton.disabled = state.loadingIndexes || state.ingesting;
  elements.ingestButton.disabled = state.loadingIndexes || state.ingesting || !state.indexes.length;
  renderNamespaces();
  renderNamespaceControls();
}

async function loadIndexes() {
  state.loadingIndexes = true;
  setStatus("Loading Pinecone indexes...");
  renderIndexes();

  try {
    const response = await fetch("/pinecone/indexes", { cache: "no-store" });
    const payload = await response.json();

    if (!response.ok) {
      throw new Error(payload.detail || "Unable to load Pinecone indexes");
    }

    state.indexes = Array.isArray(payload.indexes) ? payload.indexes : [];
    setStatus("");

    if (!state.indexes.length) {
      elements.resultBox.textContent = "No Pinecone indexes were returned.";
    }
  } catch (error) {
    state.indexes = [];
    setStatus(error.message || "Unable to load Pinecone indexes", true);
  } finally {
    state.loadingIndexes = false;
    renderIndexes();
  }
}

async function ingestText(event) {
  event.preventDefault();

  const text = elements.textInput.value.trim();
  const indexName = elements.indexSelect.value;
  const namespaceName = getNamespaceName();
  const chunkSize = Number(elements.chunkSizeInput.value);
  const chunkOverlap = Number(elements.chunkOverlapInput.value);

  if (!indexName) {
    setStatus("Select an index before ingesting.", true);
    elements.indexSelect.focus();
    return;
  }

  if (!namespaceName) {
    setStatus("Select or enter a namespace before ingesting.", true);
    elements.namespaceInput.focus();
    return;
  }

  if (!text) {
    setStatus("Paste text before ingesting.", true);
    elements.textInput.focus();
    return;
  }

  state.ingesting = true;
  elements.ingestButton.disabled = true;
  elements.refreshIndexesButton.disabled = true;
  elements.resultBox.textContent = "Chunking, embedding, and upserting...";
  setStatus("");

  try {
    const response = await fetch("/pinecone/upsert-text", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        text,
        index_name: indexName,
        namespace_name: namespaceName,
        chunk_size: chunkSize,
        chunk_overlap: chunkOverlap,
      }),
    });
    const payload = await response.json();

    if (!response.ok) {
      throw new Error(payload.detail || "Text ingestion failed");
    }

    elements.resultBox.textContent = JSON.stringify(payload, null, 2);
    loadIndexes();
  } catch (error) {
    elements.resultBox.textContent = "";
    setStatus(error.message || "Text ingestion failed", true);
  } finally {
    state.ingesting = false;
    renderIndexes();
  }
}

elements.indexSelect.addEventListener("change", renderNamespaces);
elements.namespaceMode.addEventListener("change", renderNamespaceControls);
elements.refreshIndexesButton.addEventListener("click", loadIndexes);
elements.ingestForm.addEventListener("submit", ingestText);

loadIndexes();
