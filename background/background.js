/**
 * AI PDF Assistant — Background Service Worker (Manifest V3)
 *
 * Central controller for the extension. Handles lifecycle events,
 * inter-script messaging, tab/PDF detection, and side panel coordination.
 *
 * Note: AI, PDF parsing, and backend integrations are not implemented yet.
 */

/* ==========================================================================
   Dependencies
   ========================================================================== */

importScripts('../services/storage-service.js');

/* ==========================================================================
   Constants
   ========================================================================== */

/** Prefix used for all service worker log output */
const LOG_PREFIX = "[AI PDF Assistant · Background]";

/**
 * Supported message actions sent from popup, side panel, content, or options scripts.
 * Payload shape: { action: string, payload?: object }
 */
const MESSAGE_ACTIONS = {
  OPEN_SIDE_PANEL: "OPEN_SIDE_PANEL",
  OPEN_OPTIONS: "OPEN_OPTIONS",
  OPEN_CURRENT_PDF: "OPEN_CURRENT_PDF",
  CHAT_WITH_PDF: "CHAT_WITH_PDF",
  SUMMARIZE_PDF: "SUMMARIZE_PDF",
  ASK_QUESTION: "ASK_QUESTION",
  SEARCH_PDF: "SEARCH_PDF",
  GET_EXTENSION_STATUS: "GET_EXTENSION_STATUS",
  TEST_CONNECTION: "TEST_CONNECTION",
  EXTRACT_PDF_TEXT: "EXTRACT_PDF_TEXT",
  EXTRACTED_TEXT_RESULT: "EXTRACTED_TEXT_RESULT",
  SAVE_PROGRESS: "SAVE_PROGRESS",
  GET_PROGRESS: "GET_PROGRESS",
  DELETE_PROGRESS: "DELETE_PROGRESS",
  UPLOAD_PDF: "UPLOAD_PDF",
  SAVE_BOOKMARK: "SAVE_BOOKMARK",
  GET_BOOKMARKS: "GET_BOOKMARKS",
  DELETE_BOOKMARK: "DELETE_BOOKMARK",
};

/** Keys used with chrome.storage.local */
const STORAGE_KEYS = {
  SETTINGS: "settings",
  INSTALLED_VERSION: "installedVersion",
};

/**
 * Default extension settings written on first install.
 * Kept in sync with options/options.js defaults.
 */
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

/** Chrome's built-in PDF viewer extension ID */
const CHROME_PDF_VIEWER_EXTENSION_ID = "mhjfbmdgcfjbbpaeojofohoefgiehjai";

/**
 * In-memory cache of the most recently detected PDF tab state.
 * Updated when tabs are activated or finish loading.
 */
let lastKnownPdfState = {
  tabId: null,
  url: null,
  isPdf: false,
};

/* ==========================================================================
   Utility Functions
   ========================================================================== */

/**
 * Writes a structured log message to the service worker console.
 *
 * @param {string} message - Short description of the event
 * @param {Record<string, unknown>} [details={}] - Optional structured metadata
 */
function logMessage(message, details = {}) {
  if (Object.keys(details).length === 0) {
    console.log(`${LOG_PREFIX} ${message}`);
    return;
  }

  console.log(`${LOG_PREFIX} ${message}`, details);
}

/**
 * Sends a standardized success response to a message sender.
 *
 * @param {Function} sendResponse - chrome.runtime message callback
 * @param {Record<string, unknown>} [data={}] - Optional response payload
 */
function sendSuccessResponse(sendResponse, data = {}) {
  sendResponse({
    success: true,
    timestamp: Date.now(),
    ...data,
  });
}

/**
 * Sends a standardized error response to a message sender.
 *
 * @param {Function} sendResponse - chrome.runtime message callback
 * @param {string} errorMessage - Human-readable error description
 * @param {Record<string, unknown>} [data={}] - Optional extra error context
 */
function sendErrorResponse(sendResponse, errorMessage, data = {}) {
  sendResponse({
    success: false,
    error: errorMessage,
    timestamp: Date.now(),
    ...data,
  });
}

/**
 * Determines whether a URL likely points to a PDF document.
 *
 * Checks common patterns:
 * - Path ending in `.pdf`
 * - Chrome's built-in PDF viewer extension URL
 * - Embedded PDF URLs inside the viewer extension URL
 *
 * @param {string | undefined | null} url - Tab or resource URL
 * @returns {boolean} True when the URL appears to represent a PDF
 */
function isPdfUrl(url) {
  if (!url || typeof url !== "string") {
    return false;
  }

  const normalizedUrl = url.trim().toLowerCase();

  if (normalizedUrl.startsWith("file://") && normalizedUrl.includes(".pdf")) {
    return true;
  }

  if (normalizedUrl.includes(`${CHROME_PDF_VIEWER_EXTENSION_ID}/`)) {
    return true;
  }

  try {
    const parsedUrl = new URL(url);
    const pathname = parsedUrl.pathname.toLowerCase();

    if (pathname.endsWith(".pdf")) {
      return true;
    }

    if (parsedUrl.searchParams.get("format") === "pdf") {
      return true;
    }
  } catch {
    return normalizedUrl.includes(".pdf");
  }

  return false;
}

/**
 * Safely retrieves the currently active tab in the current window.
 *
 * @returns {Promise<chrome.tabs.Tab | null>} Active tab or null if unavailable
 */
async function getActiveTab() {
  const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
  return tabs[0] ?? null;
}

/**
 * Updates the in-memory PDF detection cache and logs the result.
 *
 * @param {number | undefined} tabId - Chrome tab ID
 * @param {string | undefined} url - Tab URL
 */
function updatePdfDetectionState(tabId, url) {
  const isPdf = isPdfUrl(url);

  lastKnownPdfState = {
    tabId: tabId ?? null,
    url: url ?? null,
    isPdf,
  };

  logMessage(isPdf ? "PDF detected in tab" : "No PDF detected in tab", {
    tabId,
    url,
  });
}

/**
 * Persists default extension settings when the extension is installed for the first time.
 *
 * Existing settings are not overwritten on subsequent startups.
 *
 * @returns {Promise<void>}
 */
async function initializeDefaultSettings() {
  const storedValues = await chrome.storage.local.get([
    STORAGE_KEYS.SETTINGS,
    STORAGE_KEYS.INSTALLED_VERSION,
  ]);

  const manifestVersion = chrome.runtime.getManifest().version;
  const isFirstInstall = !storedValues[STORAGE_KEYS.SETTINGS];

  if (isFirstInstall) {
    await chrome.storage.local.set({
      [STORAGE_KEYS.SETTINGS]: DEFAULT_SETTINGS,
      [STORAGE_KEYS.INSTALLED_VERSION]: manifestVersion,
    });

    logMessage("Default settings initialized in chrome.storage.local", {
      version: manifestVersion,
    });
    return;
  }

  logMessage("Existing settings found — skipping default initialization", {
    installedVersion: storedValues[STORAGE_KEYS.INSTALLED_VERSION] ?? "unknown",
  });
}

/**
 * Configures Side Panel behavior for Manifest V3.
 *
 * Because a default popup is defined in manifest.json, the extension icon
 * opens the popup instead of firing chrome.action.onClicked.
 *
 * @returns {Promise<void>}
 */
async function configureSidePanel() {
  if (!chrome.sidePanel?.setPanelBehavior) {
    logMessage("Side Panel API unavailable in this browser context");
    return;
  }

  await chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: false });

  logMessage("Side Panel behavior configured", {
    openPanelOnActionClick: false,
    reason: "default_popup is set on the browser action",
  });
}

/* ==========================================================================
   Message Action Handlers
   ========================================================================== */

/**
 * Opens the Side Panel for a specific tab.
 *
 * @param {Record<string, unknown>} payload - Optional message payload
 * @param {chrome.runtime.MessageSender} sender - Message sender metadata
 * @returns {Promise<Record<string, unknown>>}
 */
async function handleOpenSidePanel(payload, sender) {
  const tabId = payload?.tabId ?? sender.tab?.id ?? (await getActiveTab())?.id;

  if (!tabId) {
    throw new Error("Unable to determine a target tab for the Side Panel.");
  }

  if (chrome.sidePanel?.open) {
    await chrome.sidePanel.open({ tabId });
  }

  logMessage("OPEN_SIDE_PANEL handled", { tabId, payload });

  return {
    action: MESSAGE_ACTIONS.OPEN_SIDE_PANEL,
    tabId,
    message: "Side Panel open request completed.",
  };
}

/**
 * Opens the extension options page in a new tab.
 *
 * @returns {Promise<Record<string, unknown>>}
 */
async function handleOpenOptions() {
  if (chrome.runtime.openOptionsPage) {
    await chrome.runtime.openOptionsPage();
  }

  logMessage("OPEN_OPTIONS handled");

  return {
    action: MESSAGE_ACTIONS.OPEN_OPTIONS,
    message: "Options page opened.",
  };
}

/**
 * Placeholder handler for opening the PDF in the active tab.
 *
 * @param {Record<string, unknown>} payload - Optional message payload
 * @returns {Promise<Record<string, unknown>>}
 */
async function handleOpenCurrentPdf(payload) {
  const activeTab = await getActiveTab();

  logMessage("OPEN_CURRENT_PDF handled", {
    tabId: activeTab?.id,
    url: activeTab?.url,
    payload,
  });

  return {
    action: MESSAGE_ACTIONS.OPEN_CURRENT_PDF,
    tabId: activeTab?.id ?? null,
    isPdf: isPdfUrl(activeTab?.url),
    message: "Open current PDF request acknowledged.",
  };
}

/**
 * Helper to convert base64 to Blob
 */
function base64ToBlob(base64, contentType = 'application/pdf') {
  const byteCharacters = atob(base64);
  const byteArrays = [];
  for (let offset = 0; offset < byteCharacters.length; offset += 512) {
    const slice = byteCharacters.slice(offset, offset + 512);
    const byteNumbers = new Array(slice.length);
    for (let i = 0; i < slice.length; i++) {
      byteNumbers[i] = slice.charCodeAt(i);
    }
    const byteArray = new Uint8Array(byteNumbers);
    byteArrays.push(byteArray);
  }
  return new Blob(byteArrays, { type: contentType });
}

/**
 * Handles UPLOAD_PDF requests.
 */
async function handleUploadPdf(payload) {
  logMessage("UPLOAD_PDF handled", { filename: payload.filename });
  
  try {
    const blob = base64ToBlob(payload.base64);
    const formData = new FormData();
    formData.append("file", blob, payload.filename);

    const response = await fetch("http://127.0.0.1:8000/upload-pdf", {
      method: "POST",
      body: formData,
    });
    
    if (!response.ok) {
      throw new Error(`Upload failed: ${response.statusText}`);
    }
    
    const result = await response.json();
    return { ...result, action: MESSAGE_ACTIONS.UPLOAD_PDF };
  } catch (error) {
    logMessage("UPLOAD_PDF Error", { error: error.message });
    throw error;
  }
}

/**
 * Handles chat-with-PDF requests.
 */
async function handleChatWithPdf(payload) {
  logMessage("CHAT_WITH_PDF handled", { payload });
  try {
    const response = await fetch("http://127.0.0.1:8000/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: payload.question }),
    });
    
    if (!response.ok) {
      throw new Error(`Chat failed: ${response.statusText}`);
    }
    
    const result = await response.json();
    return { ...result, action: MESSAGE_ACTIONS.CHAT_WITH_PDF };
  } catch (error) {
    logMessage("CHAT_WITH_PDF Error", { error: error.message });
    throw error;
  }
}

/**
 * Handles summarize-PDF requests.
 */
async function handleSummarizePdf(payload) {
  logMessage("SUMMARIZE_PDF handled", { payload });
  try {
    const response = await fetch("http://127.0.0.1:8000/summarize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pdf_text: payload.text || "", summary_type: payload.summary_type || "medium" }),
    });
    
    if (!response.ok) {
      throw new Error(`Summarize failed: ${response.statusText}`);
    }
    
    const result = await response.json();
    return { ...result, action: MESSAGE_ACTIONS.SUMMARIZE_PDF };
  } catch (error) {
    logMessage("SUMMARIZE_PDF Error", { error: error.message });
    throw error;
  }
}

/**
 * Placeholder handler for ask-question requests.
 *
 * @param {Record<string, unknown>} payload - Optional message payload
 * @returns {Promise<Record<string, unknown>>}
 */
async function handleAskQuestion(payload) {
  logMessage("ASK_QUESTION handled", { payload });

  return {
    action: MESSAGE_ACTIONS.ASK_QUESTION,
    message: "Ask question request acknowledged.",
  };
}

/**
 * Placeholder handler for search-PDF requests.
 *
 * @param {Record<string, unknown>} payload - Optional message payload
 * @returns {Promise<Record<string, unknown>>}
 */
async function handleSearchPdf(payload) {
  logMessage("SEARCH_PDF handled", { payload });

  return {
    action: MESSAGE_ACTIONS.SEARCH_PDF,
    message: "Search PDF request acknowledged.",
  };
}

/**
 * Returns current extension status for UI dashboards.
 *
 * @returns {Promise<Record<string, unknown>>}
 */
async function handleGetExtensionStatus() {
  const manifest = chrome.runtime.getManifest();
  const storedValues = await chrome.storage.local.get(STORAGE_KEYS.SETTINGS);
  const activeTab = await getActiveTab();

  const status = {
    action: MESSAGE_ACTIONS.GET_EXTENSION_STATUS,
    extensionName: manifest.name,
    version: manifest.version,
    aiStatus: "Ready",
    settings: storedValues[STORAGE_KEYS.SETTINGS] ?? DEFAULT_SETTINGS,
    activeTab: {
      id: activeTab?.id ?? null,
      url: activeTab?.url ?? null,
      isPdf: isPdfUrl(activeTab?.url),
    },
    lastKnownPdfState,
    message: "Extension status retrieved successfully.",
  };

  logMessage("GET_EXTENSION_STATUS handled", {
    version: status.version,
    activeTabId: status.activeTab.id,
    isPdf: status.activeTab.isPdf,
  });

  return status;
}

/**
 * Starts the PDF text extraction process.
 */
async function handleExtractPdfText(payload, sender) {
  const activeTab = await getActiveTab();
  
  if (!activeTab || !isPdfUrl(activeTab.url)) {
    chrome.runtime.sendMessage({ 
      action: "EXTRACTED_TEXT_RESULT", 
      success: false, 
      error: "The current tab is not a PDF document." 
    });
    return "Error: Not a PDF";
  }

  logMessage("Injecting PDF.js and content script", { tabId: activeTab.id });

  try {
    let pdfUrl = activeTab.url;
    if (pdfUrl.includes("mhjfbmdgcfjbbpaeojofohoefgiehjai") && pdfUrl.includes("url=")) {
      try {
        const urlObj = new URL(pdfUrl);
        const actualUrl = urlObj.searchParams.get("url");
        if (actualUrl) {
          pdfUrl = actualUrl;
        }
      } catch (e) {
        logMessage("Failed to parse native PDF viewer URL", { error: e.message });
      }
    }

    if (pdfUrl.startsWith("file://")) {
      logMessage("Local file detected. Fetching directly from background and uploading to backend...", { pdfUrl });
      
      const response = await fetch(pdfUrl);
      if (!response.ok) {
        throw new Error(`Failed to fetch local file: ${response.statusText}`);
      }
      const blob = await response.blob();
      
      let filename = "local_document.pdf";
      try {
        const decoded = decodeURIComponent(pdfUrl);
        const parts = decoded.split('/');
        filename = parts[parts.length - 1] || filename;
      } catch (e) {}

      const formData = new FormData();
      formData.append("file", blob, filename);
      
      const uploadRes = await fetch("http://127.0.0.1:8000/upload-pdf", {
        method: "POST",
        body: formData
      });
      
      if (!uploadRes.ok) {
        throw new Error(`Backend upload failed: ${uploadRes.statusText}`);
      }
      
      const result = await uploadRes.json();
      
      chrome.runtime.sendMessage({ 
        action: "EXTRACTED_TEXT_RESULT", 
        success: true, 
        text: `Extracted ${result.num_chunks} chunks via backend upload. You can now chat or summarize!`,
        error: null
      });
      
      return "Extraction initiated via background upload";
    }

    // Inject scripts into the PDF tab (for non-local or fallback scenarios)
    await chrome.scripting.executeScript({
      target: { tabId: activeTab.id },
      files: ["assets/pdf.min.js", "content/content.js"]
    });

    // Command the injected content script to start extraction
    chrome.tabs.sendMessage(activeTab.id, { action: "START_EXTRACTION" });
  } catch (error) {
    logMessage("Script injection failed", { error: error.message });
    chrome.runtime.sendMessage({ 
      action: "EXTRACTED_TEXT_RESULT", 
      success: false, 
      error: "Cannot read this PDF page (it might be a protected browser page)." 
    });
  }

  return "Extraction initiated";
}

/**
 * Handles the result from content.js and forwards to popup.js.
 */
async function handleExtractedTextResult(payload, sender) {
  logMessage("PDF Extraction Result", { 
    success: payload.success, 
    textLength: payload.text ? payload.text.length : 0,
    error: payload.error
  });

  // Forward to popup.js (broadcast)
  chrome.runtime.sendMessage({
    action: "EXTRACTED_TEXT_RESULT",
    success: payload.success,
    text: payload.text,
    error: payload.error
  });

  return "Forwarded to popup successfully";
}

/**
 * Handles the dummy test connection message.
 */
async function handleTestConnection(payload, sender) {
  logMessage("Handling test connection from", { source: payload.source });
  chrome.runtime.sendMessage({
    action: "FORWARD_TEST_CONNECTION",
    source: payload.source,
    data: payload.data || payload.title
  });
  return "Forwarded to sidepanel successfully";
}

/**
 * Handles saving reading progress.
 */
async function handleSaveProgress(payload, sender) {
  if (!payload.pdfId) {
    throw new Error("Missing pdfId in payload");
  }
  const result = await saveReadingProgress(payload.pdfId, payload);
  logMessage("Saved reading progress", { pdfId: payload.pdfId });
  return result;
}

/**
 * Handles getting reading progress.
 */
async function handleGetProgress(payload, sender) {
  if (!payload.pdfId) {
    throw new Error("Missing pdfId in payload");
  }
  const result = await getReadingProgress(payload.pdfId);
  logMessage("Retrieved reading progress", { pdfId: payload.pdfId, found: !!result });
  return result;
}

/**
 * Handles deleting reading progress.
 */
async function handleDeleteProgress(payload, sender) {
  if (!payload.pdfId) {
    throw new Error("Missing pdfId in payload");
  }
  await deleteReadingProgress(payload.pdfId);
  logMessage("Deleted reading progress", { pdfId: payload.pdfId });
  return { deleted: true };
}

/* ==========================================================================
   Bookmark Handlers
   ========================================================================== */

async function handleGetBookmarks(payload, sender) {
  const bookmarks = await getBookmarks();
  logMessage("Retrieved bookmarks", { count: bookmarks.length });
  return bookmarks;
}

async function handleDeleteBookmark(payload, sender) {
  if (!payload.bookmarkId) {
    throw new Error("Missing bookmarkId in payload");
  }
  await deleteBookmark(payload.bookmarkId);
  logMessage("Deleted bookmark", { bookmarkId: payload.bookmarkId });
  return { deleted: true };
}

async function handleSaveBookmark(payload, sender) {
  let pdfId = payload.pdfId;
  let title = payload.title;
  let pageNumber = payload.pageNumber;

  if (!pdfId || !title) {
    const activeTab = await getActiveTab();
    if (activeTab && isPdfUrl(activeTab.url)) {
      try {
        const response = await chrome.tabs.sendMessage(activeTab.id, { action: "GET_PAGE_INFO" });
        if (response && response.success && response.data) {
          pdfId = response.data.url;
          title = response.data.title;
          pageNumber = response.data.pageNumber || 1;
        }
      } catch (err) {
        logMessage("Failed to get page info from content script", { error: err.message });
        pdfId = activeTab.url;
        title = activeTab.title;
        pageNumber = 1;
      }
    } else {
      throw new Error("No PDF active in the current tab to bookmark.");
    }
  }

  const result = await saveBookmark(pdfId, title, pageNumber);
  logMessage("Saved bookmark", { pdfId });
  return result;
}

/* ==========================================================================
   Message Router
   ========================================================================== */

/**
 * Maps supported message actions to their handler functions.
 * Each handler returns a serializable response object.
 *
 * @type {Record<string, Function>}
 */
const MESSAGE_HANDLERS = {
  [MESSAGE_ACTIONS.OPEN_SIDE_PANEL]: handleOpenSidePanel,
  [MESSAGE_ACTIONS.OPEN_OPTIONS]: handleOpenOptions,
  [MESSAGE_ACTIONS.OPEN_CURRENT_PDF]: handleOpenCurrentPdf,
  [MESSAGE_ACTIONS.UPLOAD_PDF]: handleUploadPdf,

  [MESSAGE_ACTIONS.CHAT_WITH_PDF]: handleChatWithPdf,
  [MESSAGE_ACTIONS.SUMMARIZE_PDF]: handleSummarizePdf,
  [MESSAGE_ACTIONS.ASK_QUESTION]: handleAskQuestion,
  [MESSAGE_ACTIONS.SEARCH_PDF]: handleSearchPdf,
  [MESSAGE_ACTIONS.GET_EXTENSION_STATUS]: handleGetExtensionStatus,
  [MESSAGE_ACTIONS.TEST_CONNECTION]: handleTestConnection,
  [MESSAGE_ACTIONS.EXTRACT_PDF_TEXT]: handleExtractPdfText,
  [MESSAGE_ACTIONS.EXTRACTED_TEXT_RESULT]: handleExtractedTextResult,
  [MESSAGE_ACTIONS.SAVE_PROGRESS]: handleSaveProgress,
  [MESSAGE_ACTIONS.GET_PROGRESS]: handleGetProgress,
  [MESSAGE_ACTIONS.DELETE_PROGRESS]: handleDeleteProgress,
  [MESSAGE_ACTIONS.SAVE_BOOKMARK]: handleSaveBookmark,
  [MESSAGE_ACTIONS.GET_BOOKMARKS]: handleGetBookmarks,
  [MESSAGE_ACTIONS.DELETE_BOOKMARK]: handleDeleteBookmark,
};

/**
 * Routes incoming runtime messages to the appropriate handler.
 *
 * Expected message format:
 * { action: "OPEN_SIDE_PANEL", payload?: { ... } }
 *
 * @param {Record<string, unknown>} message - Incoming message object
 * @param {chrome.runtime.MessageSender} sender - Sender metadata
 * @param {Function} sendResponse - Async response callback
 * @returns {Promise<void>}
 */
async function routeMessage(message, sender, sendResponse) {
  const action = message?.action;
  const payload = message?.payload ?? {};

  if (!action || typeof action !== "string") {
    logMessage("Rejected message without a valid action", { message, sender });
    sendErrorResponse(sendResponse, "Invalid message: missing action.");
    return;
  }

  const handler = MESSAGE_HANDLERS[action];

  if (!handler) {
    logMessage("Unhandled message action received", { action, payload, sender });
    sendErrorResponse(sendResponse, `Unknown action: ${action}`, { action });
    return;
  }

  try {
    const result = await handler(payload, sender);
    sendSuccessResponse(sendResponse, { data: result });
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : "Unknown background error";

    logMessage("Message handler failed", { action, error: errorMessage });
    sendErrorResponse(sendResponse, errorMessage, { action });
  }
}

/* ==========================================================================
   Event Listeners
   ========================================================================== */

/**
 * Runs when the extension is installed or updated.
 */
chrome.runtime.onInstalled.addListener(async (details) => {
  logMessage("Extension installed/updated", {
    reason: details.reason,
    previousVersion: details.previousVersion ?? null,
    currentVersion: chrome.runtime.getManifest().version,
  });

  try {
    await initializeDefaultSettings();
    await configureSidePanel();
    logMessage("Installation setup completed successfully");
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : "Installation setup failed";
    logMessage("Installation setup failed", { error: errorMessage });
  }
});

/**
 * Runs when the browser profile starts and the extension is already installed.
 */
chrome.runtime.onStartup.addListener(() => {
  logMessage("Extension startup detected");
});

/**
 * Central message listener for popup, side panel, content script, and options page.
 *
 * Returns true to keep the message channel open for async sendResponse calls.
 */
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  logMessage("Message received", {
    action: message?.action,
    from: sender.id,
    tabId: sender.tab?.id ?? null,
  });

  routeMessage(message, sender, sendResponse);

  return true;
});

/**
 * Detects PDF URLs when a tab finishes loading or its URL changes.
 */
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  const url = changeInfo.url ?? tab.url;
  const shouldEvaluate =
    changeInfo.status === "complete" || typeof changeInfo.url === "string";

  if (!shouldEvaluate || !url) {
    return;
  }

  updatePdfDetectionState(tabId, url);
});

/**
 * Detects PDF URLs when the user switches to a different active tab.
 */
chrome.tabs.onActivated.addListener(async (activeInfo) => {
  try {
    const tab = await chrome.tabs.get(activeInfo.tabId);
    updatePdfDetectionState(tab.id, tab.url);
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : "Tab lookup failed";
    logMessage("Failed to inspect activated tab", {
      tabId: activeInfo.tabId,
      error: errorMessage,
    });
  }
});

/**
 * Listens for direct extension icon clicks.
 *
 * Important MV3 note:
 * This event does NOT fire when manifest.json defines action.default_popup.
 * The popup opens instead. This listener remains for future configurations
 * where the popup may be removed in favor of Side Panel-first interaction.
 */
chrome.action.onClicked.addListener(async (tab) => {
  logMessage("Browser action clicked", {
    tabId: tab.id,
    url: tab.url,
    note: "This event only fires when no default_popup is configured.",
  });

  try {
    await handleOpenSidePanel({}, { tab });
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : "Action click handling failed";
    logMessage("Browser action handler failed", { error: errorMessage });
  }
});

/* ==========================================================================
   Initialization
   ========================================================================== */

/**
 * Performs one-time service worker boot tasks.
 * Service workers can restart frequently, so this must remain idempotent.
 */
async function initializeServiceWorker() {
  logMessage("Service worker initialized", {
    version: chrome.runtime.getManifest().version,
  });

  try {
    const activeTab = await getActiveTab();

    if (activeTab?.url) {
      updatePdfDetectionState(activeTab.id, activeTab.url);
    }
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : "Startup tab scan failed";
    logMessage("Initial active tab scan failed", { error: errorMessage });
  }
}

initializeServiceWorker();
