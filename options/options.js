/**
 * AI PDF Assistant — Options Page Script
 * Manages settings UI with in-memory storage (no backend yet).
 */

/* ==========================================================================
   Model Options per AI Provider
   ========================================================================== */

const MODEL_OPTIONS = {
  openai: [
    { value: "gpt-4o", label: "GPT-4o" },
    { value: "gpt-4o-mini", label: "GPT-4o Mini" },
    { value: "gpt-4-turbo", label: "GPT-4 Turbo" },
  ],
  gemini: [
    { value: "gemini-2.0-flash", label: "Gemini 2.0 Flash" },
    { value: "gemini-1.5-pro", label: "Gemini 1.5 Pro" },
    { value: "gemini-1.5-flash", label: "Gemini 1.5 Flash" },
  ],
  claude: [
    { value: "claude-3-5-sonnet", label: "Claude 3.5 Sonnet" },
    { value: "claude-3-opus", label: "Claude 3 Opus" },
    { value: "claude-3-haiku", label: "Claude 3 Haiku" },
  ],
};

/** Default settings applied on first load and after reset */
const DEFAULT_SETTINGS = {
  aiProvider: "openai",
  aiModel: "gpt-4o-mini",
  apiKey: "",
  summaryLength: "medium",
  autoOpenSidePanel: true,
  rememberRecentPdfs: true,
  theme: "dark",
  fontSize: "medium",
  language: "en",
};

/** Placeholder storage statistics */
const STORAGE_STATS = {
  usedMb: 12.4,
  limitMb: 50,
  chatHistoryCount: 24,
  savedPdfsCount: 8,
};

/** About section metadata */
const ABOUT_INFO = {
  name: "AI PDF Assistant",
  version: "1.0.0",
  developer: "AI PDF Assistant Team",
  githubUrl: "https://github.com/example/ai-pdf-assistant",
};

/**
 * In-memory settings store (temporary — replace with chrome.storage later).
 * @type {typeof DEFAULT_SETTINGS}
 */
let appSettings = { ...DEFAULT_SETTINGS };

/** Minimum valid API key length for validation */
const MIN_API_KEY_LENGTH = 20;

/** Toast auto-hide timer reference */
let toastTimer = null;

/* ==========================================================================
   Utility Helpers
   ========================================================================== */

/**
 * Logs an action with a consistent prefix.
 * @param {string} action
 * @param {object} [details={}]
 */
function logAction(action, details = {}) {
  console.log(`[AI PDF Assistant · Options] ${action}`, details);
}

/**
 * Shows a temporary toast notification.
 * @param {string} message
 * @param {"success"|"error"} [type="success"]
 */
function showToast(message, type = "success") {
  const toast = document.getElementById("toast");
  const toastMessage = document.getElementById("toast-message");
  const toastIcon = toast?.querySelector(".toast-icon");

  if (!toast || !toastMessage) {
    return;
  }

  toastMessage.textContent = message;
  toast.classList.toggle("error", type === "error");
  toast.hidden = false;

  if (toastIcon) {
    toastIcon.className =
      type === "error"
        ? "fa-solid fa-circle-xmark toast-icon"
        : "fa-solid fa-circle-check toast-icon";
  }

  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toast.hidden = true;
  }, 3200);
}

/**
 * Validates the API key field value.
 * Empty is allowed (optional until user saves with intent to use AI).
 * If provided, must meet minimum length.
 * @param {string} apiKey
 * @returns {{ valid: boolean, message: string }}
 */
function validateApiKey(apiKey) {
  const trimmed = apiKey.trim();

  if (trimmed.length === 0) {
    return { valid: true, message: "" };
  }

  if (trimmed.length < MIN_API_KEY_LENGTH) {
    return {
      valid: false,
      message: `Please enter a valid API key (minimum ${MIN_API_KEY_LENGTH} characters).`,
    };
  }

  return { valid: true, message: "" };
}

/* ==========================================================================
   DOM References
   ========================================================================== */

const elements = {
  aiProvider: () => document.getElementById("ai-provider"),
  aiModel: () => document.getElementById("ai-model"),
  apiKey: () => document.getElementById("api-key"),
  apiKeyError: () => document.getElementById("api-key-error"),
  summaryLength: () => document.getElementById("summary-length"),
  autoSidePanel: () => document.getElementById("toggle-auto-sidepanel"),
  rememberPdfs: () => document.getElementById("toggle-remember-pdfs"),
  themeSelect: () => document.getElementById("theme-select"),
  languageSelect: () => document.getElementById("language-select"),
};

/* ==========================================================================
   UI Rendering
   ========================================================================== */

/**
 * Populates the model dropdown based on the selected AI provider.
 * @param {string} provider
 * @param {string} [selectedModel]
 */
function renderModelOptions(provider, selectedModel) {
  const modelSelect = elements.aiModel();

  if (!modelSelect) {
    return;
  }

  const models = MODEL_OPTIONS[provider] || MODEL_OPTIONS.openai;

  modelSelect.innerHTML = "";

  models.forEach((model) => {
    const option = document.createElement("option");
    option.value = model.value;
    option.textContent = model.label;
    modelSelect.appendChild(option);
  });

  const validModel = models.some((model) => model.value === selectedModel);
  modelSelect.value = validModel ? selectedModel : models[0].value;
}

/**
 * Applies in-memory settings to all form controls.
 */
function applySettingsToForm() {
  const providerEl = elements.aiProvider();
  const apiKeyEl = elements.apiKey();

  if (providerEl) {
    providerEl.value = appSettings.aiProvider;
  }

  renderModelOptions(appSettings.aiProvider, appSettings.aiModel);

  if (apiKeyEl) {
    apiKeyEl.value = appSettings.apiKey;
  }

  if (elements.summaryLength()) {
    elements.summaryLength().value = appSettings.summaryLength;
  }

  if (elements.autoSidePanel()) {
    elements.autoSidePanel().checked = appSettings.autoOpenSidePanel;
  }

  if (elements.rememberPdfs()) {
    elements.rememberPdfs().checked = appSettings.rememberRecentPdfs;
  }

  if (elements.themeSelect()) {
    elements.themeSelect().value = appSettings.theme;
  }

  if (elements.languageSelect()) {
    elements.languageSelect().value = appSettings.language;
  }

  const fontSizeRadio = document.querySelector(
    `input[name="fontSize"][value="${appSettings.fontSize}"]`
  );

  if (fontSizeRadio) {
    fontSizeRadio.checked = true;
  }
}

/**
 * Reads current form values into the in-memory settings object.
 */
function readSettingsFromForm() {
  const fontSize = document.querySelector('input[name="fontSize"]:checked');

  appSettings = {
    aiProvider: elements.aiProvider()?.value || DEFAULT_SETTINGS.aiProvider,
    aiModel: elements.aiModel()?.value || DEFAULT_SETTINGS.aiModel,
    apiKey: elements.apiKey()?.value.trim() || "",
    summaryLength: elements.summaryLength()?.value || DEFAULT_SETTINGS.summaryLength,
    autoOpenSidePanel: elements.autoSidePanel()?.checked ?? DEFAULT_SETTINGS.autoOpenSidePanel,
    rememberRecentPdfs: elements.rememberPdfs()?.checked ?? DEFAULT_SETTINGS.rememberRecentPdfs,
    theme: elements.themeSelect()?.value || DEFAULT_SETTINGS.theme,
    fontSize: fontSize?.value || DEFAULT_SETTINGS.fontSize,
    language: elements.languageSelect()?.value || DEFAULT_SETTINGS.language,
  };

  logAction("Settings updated in memory", { ...appSettings, apiKey: "[hidden]" });
}

/**
 * Renders placeholder storage statistics.
 */
function renderStorageStats() {
  const usedEl = document.getElementById("storage-used");
  const chatEl = document.getElementById("chat-history-count");
  const pdfsEl = document.getElementById("saved-pdfs-count");
  const barFill = document.getElementById("storage-bar-fill");

  const percent = Math.min(100, Math.round((STORAGE_STATS.usedMb / STORAGE_STATS.limitMb) * 100));

  if (usedEl) {
    usedEl.textContent = `${STORAGE_STATS.usedMb} MB`;
  }

  if (chatEl) {
    chatEl.textContent = `${STORAGE_STATS.chatHistoryCount} conversations`;
  }

  if (pdfsEl) {
    pdfsEl.textContent = `${STORAGE_STATS.savedPdfsCount} documents`;
  }

  if (barFill) {
    barFill.style.width = `${percent}%`;
  }
}

/**
 * Renders about section metadata.
 */
function renderAboutInfo() {
  document.getElementById("about-name").textContent = ABOUT_INFO.name;
  document.getElementById("about-version").textContent = ABOUT_INFO.version;
  document.getElementById("about-developer").textContent = ABOUT_INFO.developer;
}

/* ==========================================================================
   Form Validation UI
   ========================================================================== */

/**
 * Displays or hides API key validation error state.
 * @param {boolean} isValid
 * @param {string} [message=""]
 */
function setApiKeyValidationState(isValid, message = "") {
  const apiKeyInput = elements.apiKey();
  const errorEl = elements.apiKeyError();

  if (apiKeyInput) {
    apiKeyInput.classList.toggle("invalid", !isValid);
  }

  if (errorEl) {
    errorEl.textContent = message;
    errorEl.hidden = isValid;
  }
}

/* ==========================================================================
   Event Handlers
   ========================================================================== */

/**
 * Handles AI provider change — updates available models.
 */
function handleProviderChange() {
  const provider = elements.aiProvider()?.value || "openai";
  renderModelOptions(provider);
  logAction("AI provider changed", { provider });
}

/**
 * Toggles API key visibility between password and text.
 */
function handleToggleApiKey() {
  const apiKeyInput = elements.apiKey();
  const toggleBtn = document.getElementById("btn-toggle-api-key");
  const icon = toggleBtn?.querySelector("i");

  if (!apiKeyInput || !icon) {
    return;
  }

  const isPassword = apiKeyInput.type === "password";
  apiKeyInput.type = isPassword ? "text" : "password";
  icon.className = isPassword ? "fa-solid fa-eye-slash" : "fa-solid fa-eye";

  toggleBtn.setAttribute("aria-label", isPassword ? "Hide API key" : "Show API key");
  logAction("API key visibility toggled", { visible: isPassword });
}

/**
 * Validates and saves AI settings from the form.
 * @param {Event} event
 */
function handleSaveSettings(event) {
  event.preventDefault();

  const apiKey = elements.apiKey()?.value || "";
  const validation = validateApiKey(apiKey);

  if (!validation.valid) {
    setApiKeyValidationState(false, validation.message);
    showToast(validation.message, "error");
    logAction("Save failed — invalid API key");
    return;
  }

  setApiKeyValidationState(true);
  readSettingsFromForm();
  showToast("Settings saved successfully!");
  logAction("Settings saved");
}

/**
 * Clears chat history (placeholder).
 */
function handleClearChatHistory() {
  logAction("Clear chat history clicked");
  window.alert("Chat history will be cleared.\n(Not implemented yet.)");
}

/**
 * Clears saved PDFs (placeholder).
 */
function handleClearSavedPdfs() {
  logAction("Clear saved PDFs clicked");
  window.alert("Saved PDFs will be cleared.\n(Not implemented yet.)");
}

/**
 * Resets all settings after user confirmation.
 */
function handleResetAllSettings() {
  const confirmed = window.confirm(
    "Are you sure you want to reset all settings to their defaults?\n\nThis action cannot be undone."
  );

  if (!confirmed) {
    logAction("Reset cancelled by user");
    return;
  }

  appSettings = { ...DEFAULT_SETTINGS };
  applySettingsToForm();
  setApiKeyValidationState(true);
  showToast("All settings have been reset to defaults.");
  logAction("All settings reset");
}

/**
 * Opens GitHub repository (placeholder).
 */
function handleGitHubClick() {
  logAction("GitHub clicked", { url: ABOUT_INFO.githubUrl });
  window.alert(`GitHub: ${ABOUT_INFO.githubUrl}\n(Opening links not implemented yet.)`);
}

/**
 * Opens help documentation (placeholder).
 */
function handleHelpClick() {
  logAction("Help clicked");
  window.alert("Help documentation will be available soon.");
}

/**
 * Live validation as the user types in the API key field.
 */
function handleApiKeyInput() {
  const validation = validateApiKey(elements.apiKey()?.value || "");
  setApiKeyValidationState(validation.valid, validation.message);
}

/* ==========================================================================
   Event Binding
   ========================================================================== */

/**
 * Attaches all event listeners for the options page.
 */
function bindEventListeners() {
  document.getElementById("ai-settings-form")?.addEventListener("submit", handleSaveSettings);

  elements.aiProvider()?.addEventListener("change", handleProviderChange);
  elements.apiKey()?.addEventListener("input", handleApiKeyInput);

  document.getElementById("btn-toggle-api-key")?.addEventListener("click", handleToggleApiKey);
  document.getElementById("btn-clear-chat")?.addEventListener("click", handleClearChatHistory);
  document.getElementById("btn-clear-pdfs")?.addEventListener("click", handleClearSavedPdfs);
  document.getElementById("btn-reset-settings")?.addEventListener("click", handleResetAllSettings);
  document.getElementById("btn-github")?.addEventListener("click", handleGitHubClick);
  document.getElementById("btn-help")?.addEventListener("click", handleHelpClick);
}

/* ==========================================================================
   Initialization
   ========================================================================== */

/**
 * Bootstraps the options page when the DOM is ready.
 */
function initOptionsPage() {
  applySettingsToForm();
  renderStorageStats();
  renderAboutInfo();
  bindEventListeners();

  logAction("Options page initialized", { settings: { ...appSettings, apiKey: "[hidden]" } });
}

document.addEventListener("DOMContentLoaded", initOptionsPage);
