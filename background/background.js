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

importScripts('../services/bookmark-service.js');
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
  UPLOAD_PDF: "UPLOAD_PDF",
  EXTRACT_PDF_NAVIGATOR: "EXTRACT_PDF_NAVIGATOR",
  DOWNLOAD_NAVIGATOR_PDF: "DOWNLOAD_NAVIGATOR_PDF",
  GENERATE_NAVIGATOR: "GENERATE_NAVIGATOR",
  CHAT_WITH_PDF: "CHAT_WITH_PDF",
  ASK_QUESTION: "ASK_QUESTION",
  SEARCH_PDF: "SEARCH_PDF",
  GET_EXTENSION_STATUS: "GET_EXTENSION_STATUS",
  TEST_CONNECTION: "TEST_CONNECTION",
  EXTRACT_PDF_TEXT: "EXTRACT_PDF_TEXT",
  EXTRACTED_TEXT_RESULT: "EXTRACTED_TEXT_RESULT",
  EXTRACT_IMAGES: "EXTRACT_IMAGES",
  EXPLAIN_IMAGE: "EXPLAIN_IMAGE",
  SAVE_PROGRESS: "SAVE_PROGRESS",
  GET_PROGRESS: "GET_PROGRESS",
  DELETE_PROGRESS: "DELETE_PROGRESS",
  SAVE_BOOKMARK: "SAVE_BOOKMARK",
  GET_BOOKMARKS: "GET_BOOKMARKS",
  UPDATE_BOOKMARK: "UPDATE_BOOKMARK",
  DELETE_BOOKMARK: "DELETE_BOOKMARK",
  SEARCH_BOOKMARKS: "SEARCH_BOOKMARKS",
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
  autoOpenSidePanel: false,
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
  const tabs = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
  return tabs[0] ?? null;
}

/**
 * Updates the in-memory PDF detection cache and logs the result.
 *
 * @param {number | undefined} tabId - Chrome tab ID
 * @param {string | undefined} url - Tab URL
 */
async function updatePdfDetectionState(tabId, url) {
  const isPdf = isPdfUrl(url);

  lastKnownPdfState = {
    tabId: tabId ?? null,
    url: url ?? null,
    isPdf,
  };

  if (isPdf) {
    logMessage("PDF detected in tab", { tabId, url });
  }


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

  await chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });

  logMessage("Side Panel behavior configured", {
    openPanelOnActionClick: true,
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
 * Handles GENERATE_NAVIGATOR requests.
 */
async function handleGenerateNavigator(payload) {
  logMessage("GENERATE_NAVIGATOR handled", { filename: payload.filename });
  
  try {
    let response;
    
    // Since the frontend needs to send the file, we can either re-fetch or use base64 
    // if payload.base64 is provided.
    const blob = base64ToBlob(payload.base64);
    const formData = new FormData();
    formData.append("file", blob, payload.filename);

    response = await fetch("http://127.0.0.1:8000/generate-navigator", {
      method: "POST",
      body: formData,
    });
    
    if (!response.ok) {
      throw new Error(`Generate Navigator failed: ${response.statusText}`);
    }
    
    const result = await response.json();
    return { ...result, action: MESSAGE_ACTIONS.GENERATE_NAVIGATOR };
  } catch (error) {
    logMessage("GENERATE_NAVIGATOR Error", { error: error.message });
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
      body: JSON.stringify({
        question: payload.question,
        history: payload.history || []
      }),
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
 * Handles image vision analysis requests.
 */
async function handleExplainImage(payload) {
  logMessage("EXPLAIN_IMAGE handled", { payload });
  try {
    const response = await fetch("http://127.0.0.1:8000/explain-image", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        image_id: payload.image_id,
        prompt: payload.prompt || null
      }),
    });

    if (!response.ok) {
      const errText = await response.text();
      throw new Error(`Vision analysis failed: ${errText || response.statusText}`);
    }

    const result = await response.json();
    return result;
  } catch (error) {
    logMessage("EXPLAIN_IMAGE Error", { error: error.message });
    throw error;
  }
}

/**
 * Extracts PDF structure and calls generate-navigator.
 */
async function handleExtractPdfNavigator() {
  logMessage("EXTRACT_PDF_NAVIGATOR triggered");
  const activeTab = await getActiveTab();
  
  if (!activeTab || !isPdfUrl(activeTab.url)) {
    throw new Error("No active PDF found to generate navigator.");
  }
  
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
        logMessage("Could not parse actual URL from Chrome viewer", e);
      }
    }

    if (pdfUrl.startsWith("file://")) {
      logMessage("Local file detected for navigator. Using local path...", { pdfUrl });
      let localPath = decodeURIComponent(pdfUrl);
      if (localPath.startsWith("file:///")) {
        localPath = localPath.substring(8);
        if (!localPath.match(/^[a-zA-Z]:\//)) {
          localPath = "/" + localPath;
        }
      }
      
      // Need a backend endpoint that accepts local path for navigator, 
      // or we just read it locally in backend. Let's add that to backend next.
      const res = await fetch("http://127.0.0.1:8000/generate-local-navigator", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_path: localPath })
      });
      
      if (!res.ok) throw new Error(`Backend failed: ${res.statusText}`);
      const data = await res.json();
      return { success: true, data };
      
    } else if (pdfUrl.startsWith("http")) {
      logMessage("Web URL detected for navigator. Fetching PDF...", { pdfUrl });
      
      const response = await fetch(pdfUrl);
      if (!response.ok) throw new Error(`Failed to fetch PDF: ${response.statusText}`);
      
      const blob = await response.blob();
      const formData = new FormData();
      formData.append("file", blob, "document.pdf");
      
      const res = await fetch("http://127.0.0.1:8000/generate-navigator", {
        method: "POST",
        body: formData
      });
      
      if (!res.ok) throw new Error(`Backend failed: ${res.statusText}`);
      const data = await res.json();
      return { success: true, data };
    }
  } catch (error) {
    logMessage("Error extracting navigator", { error: error.message });
    throw error;
  }
}

/**
 * Extracts PDF structure and calls download-navigator-pdf.
 */
async function handleDownloadNavigatorPdf(payload) {
  logMessage("DOWNLOAD_NAVIGATOR_PDF triggered", { payload });
  
  let pdfUrl = payload?.pdfUrl;
  if (!pdfUrl) {
    const activeTab = await getActiveTab();
    pdfUrl = activeTab?.url;
  }
  
  if (!pdfUrl || !isPdfUrl(pdfUrl)) {
    throw new Error("No active PDF found to download navigator.");
  }
  
  try {
    if (pdfUrl.includes("mhjfbmdgcfjbbpaeojofohoefgiehjai") && pdfUrl.includes("url=")) {
      try {
        const urlObj = new URL(pdfUrl);
        const actualUrl = urlObj.searchParams.get("url");
        if (actualUrl) {
          pdfUrl = actualUrl;
        }
      } catch (e) {
        logMessage("Could not parse actual URL from Chrome viewer", e);
      }
    }

    if (pdfUrl.startsWith("file://")) {
      logMessage("Local file detected for navigator PDF. Using local path...", { pdfUrl });
      let localPath = decodeURIComponent(pdfUrl);
      if (localPath.startsWith("file:///")) {
        localPath = localPath.substring(8);
        if (!localPath.match(/^[a-zA-Z]:\//)) {
          localPath = "/" + localPath;
        }
      }
      
      const res = await fetch("http://127.0.0.1:8000/download-local-navigator-pdf", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_path: localPath })
      });
      
      if (!res.ok) {
        let errStr = res.statusText;
        try {
          const errBody = await res.json();
          if (errBody && errBody.detail) errStr = errBody.detail;
        } catch(e) {}
        throw new Error(`Backend failed: ${errStr}`);
      }
      const data = await res.json();
      return { success: true, data };
      
    } else if (pdfUrl.startsWith("http")) {
      logMessage("Web URL detected for navigator PDF. Fetching PDF...", { pdfUrl });
      
      const response = await fetch(pdfUrl);
      if (!response.ok) throw new Error(`Failed to fetch PDF: ${response.statusText}`);
      
      const blob = await response.blob();
      const formData = new FormData();
      formData.append("file", blob, "document.pdf");
      
      const res = await fetch("http://127.0.0.1:8000/download-navigator-pdf", {
        method: "POST",
        body: formData
      });
      
      if (!res.ok) {
        let errStr = res.statusText;
        try {
          const errBody = await res.json();
          if (errBody && errBody.detail) errStr = errBody.detail;
        } catch(e) {}
        throw new Error(`Backend failed: ${errStr}`);
      }
      const data = await res.json();
      return { success: true, data };
    }
  } catch (error) {
    logMessage("Error downloading navigator PDF", { error: error.message });
    throw error;
  }
}

/**
 * Handles extract-images requests.
 */
async function handleExtractImages(payload) {
  logMessage("EXTRACT_IMAGES handled", { payload });
  
  const activeTab = await getActiveTab();
  if (!activeTab || !isPdfUrl(activeTab.url)) {
    throw new Error("No active PDF found to extract images from.");
  }
  
  try {
    let pdfUrl = activeTab.url;
    if (pdfUrl.includes("mhjfbmdgcfjbbpaeojofohoefgiehjai") && pdfUrl.includes("url=")) {
      try {
        const urlObj = new URL(pdfUrl);
        const actualUrl = urlObj.searchParams.get("url");
        if (actualUrl) {
          pdfUrl = actualUrl;
        }
      } catch (e) {}
    }

    let response;
    if (pdfUrl.startsWith("file://")) {
      let localPath = decodeURIComponent(pdfUrl);
      if (localPath.startsWith("file:///")) {
        localPath = localPath.substring(8);
        if (!localPath.match(/^[a-zA-Z]:\//)) {
          localPath = "/" + localPath;
        }
      }
      
      response = await fetch("http://127.0.0.1:8000/extract-images", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_path: localPath })
      });
    } else if (pdfUrl.startsWith("http")) {
      const pdfRes = await fetch(pdfUrl);
      if (!pdfRes.ok) throw new Error(`Failed to fetch PDF: ${pdfRes.statusText}`);
      
      const blob = await pdfRes.blob();
      const formData = new FormData();
      formData.append("file", blob, "document.pdf");
      
      response = await fetch("http://127.0.0.1:8000/extract-images", {
        method: "POST",
        body: formData
      });
    } else {
      throw new Error("Cannot extract images from this type of URL.");
    }
    
    if (!response.ok) {
      throw new Error(`Extract images failed: ${response.statusText}`);
    }
    
    const result = await response.json();
    return { ...result, action: MESSAGE_ACTIONS.EXTRACT_IMAGES };
  } catch (error) {
    logMessage("EXTRACT_IMAGES Error", { error: error.message });
    throw error;
  }
}

/**
 * Handles explain-image requests.
 */
async function handleExplainImage(payload) {
  logMessage("EXPLAIN_IMAGE handled");
  try {
    const response = await fetch("http://127.0.0.1:8000/image/explain", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ image_id: payload.image_id, prompt: payload.prompt }),
    });
    
    if (!response.ok) {
      throw new Error(`Explain image failed: ${response.statusText}`);
    }
    
    const result = await response.json();
    return { ...result, action: MESSAGE_ACTIONS.EXPLAIN_IMAGE };
  } catch (error) {
    logMessage("EXPLAIN_IMAGE Error", { error: error.message });
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

    // Clean URL by stripping any hash fragment (e.g. #page=...) or query string
    const cleanUrl = pdfUrl.split("#")[0].split("?")[0];

    if (cleanUrl.startsWith("file://")) {
      logMessage("Local file detected. Sending local path to backend...", { cleanUrl });
      
      let localPath = decodeURIComponent(cleanUrl);
      if (localPath.startsWith("file:///")) {
        localPath = localPath.substring(8); // removes file:///
        // If it doesn't look like a Windows drive letter (e.g. C:/), prepend a slash for Mac/Linux
        if (!localPath.match(/^[a-zA-Z]:\//)) {
          localPath = "/" + localPath;
        }
      } else if (localPath.startsWith("file://")) {
        localPath = localPath.substring(7);
      }
      
      const uploadRes = await fetch("http://127.0.0.1:8000/upload-local-pdf", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ file_path: localPath })
      });
      
      if (!uploadRes.ok) {
        let errDetail = uploadRes.statusText;
        try {
          const errJson = await uploadRes.json();
          if (errJson && errJson.detail) errDetail = errJson.detail;
        } catch (_) {}
        throw new Error(`Backend upload failed: ${errDetail}`);
      }
      
      const result = await uploadRes.json();
      await chrome.storage.local.remove(["lastExtractedText"]);
      await chrome.storage.local.set({
        lastExtractedImages: result.images || []
      });

      chrome.runtime.sendMessage({ 
        action: "EXTRACTED_TEXT_RESULT", 
        success: true, 
        text: "",
        images: result.images || [],
        error: null
      });
      
      return "Extraction initiated via background upload";
    } else if (pdfUrl.startsWith("http")) {
      logMessage("Web URL detected. Fetching PDF and uploading to backend...", { pdfUrl });
      
      const response = await fetch(pdfUrl);
      if (!response.ok) {
        throw new Error(`Failed to fetch PDF from URL: ${response.statusText}`);
      }
      
      const blob = await response.blob();
      const formData = new FormData();
      // Fastapi expects the file field name to be 'file' based on the endpoint definition
      formData.append("file", blob, "document.pdf");
      
      const uploadRes = await fetch("http://127.0.0.1:8000/upload-pdf", {
        method: "POST",
        body: formData
      });
      
      if (!uploadRes.ok) {
        let errDetail = uploadRes.statusText;
        try {
          const errJson = await uploadRes.json();
          if (errJson && errJson.detail) errDetail = errJson.detail;
        } catch (_) {}
        throw new Error(`Backend upload failed: ${errDetail}`);
      }
      
      const result = await uploadRes.json();
      await chrome.storage.local.remove(["lastExtractedText"]);
      await chrome.storage.local.set({
        lastExtractedImages: result.images || []
      });

      chrome.runtime.sendMessage({ 
        action: "EXTRACTED_TEXT_RESULT", 
        success: true, 
        text: "",
        images: result.images || [],
        error: null
      });
      
      return "Extraction initiated via background upload (HTTP)";
    } else {
      // Inject scripts into the PDF tab (for fallback scenarios, if not file:// or http://)
      await chrome.scripting.executeScript({
        target: { tabId: activeTab.id },
        files: ["assets/pdf.min.js", "content/content.js"]
      });

      // Command the injected content script to start extraction
      chrome.tabs.sendMessage(activeTab.id, { action: "START_EXTRACTION" });
    }
  } catch (error) {
    logMessage("PDF processing failed", { error: error.message });
    chrome.runtime.sendMessage({ 
      action: "EXTRACTED_TEXT_RESULT", 
      success: false, 
      error: "Cannot read this PDF page (it might be a protected browser page or unreachable). " + error.message
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
    images: payload.images || [],
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
  const pdfId = payload?.pdfId || null;
  const bookmarks = await BookmarkService.getBookmarks(pdfId);
  logMessage("Retrieved bookmarks", { count: bookmarks.length, pdfId });
  return bookmarks;
}

async function handleSearchBookmarks(payload, sender) {
  const pdfId = payload?.pdfId || null;
  const query = payload?.query || "";
  const sortBy = payload?.sortBy || "page-asc";
  const bookmarks = await BookmarkService.searchBookmarks(pdfId, query, sortBy);
  return bookmarks;
}

async function handleUpdateBookmark(payload, sender) {
  if (!payload || !payload.bookmarkId || !payload.title) {
    throw new Error("Missing bookmarkId or title in payload");
  }
  const updated = await BookmarkService.updateBookmark(payload.bookmarkId, payload.title, payload.pageNumber);
  logMessage("Updated bookmark", { bookmarkId: payload.bookmarkId });
  return updated;
}

async function handleDeleteBookmark(payload, sender) {
  if (!payload || !payload.bookmarkId) {
    throw new Error("Missing bookmarkId in payload");
  }
  await BookmarkService.deleteBookmark(payload.bookmarkId);
  logMessage("Deleted bookmark", { bookmarkId: payload.bookmarkId });
  return { deleted: true };
}

async function handleSaveBookmark(payload, sender) {
  let pdfId = payload?.pdfId;
  let title = payload?.title;
  let pageNumber = payload?.pageNumber;

  if (!pdfId || !title || !pageNumber) {
    const activeTab = await getActiveTab();
    if (activeTab && isPdfUrl(activeTab.url)) {
      try {
        const response = await chrome.tabs.sendMessage(activeTab.id, { action: "GET_PAGE_INFO" });
        if (response && response.success && response.data) {
          pdfId = pdfId || response.data.url;
          pageNumber = pageNumber || response.data.pageNumber || 1;
          title = title || `Bookmark - Page ${pageNumber}`;
        }
      } catch (err) {
        logMessage("Failed to get page info from content script", { error: err.message });
        pdfId = pdfId || activeTab.url;
        title = title || activeTab.title || "PDF Bookmark";
        pageNumber = pageNumber || 1;
      }
    } else {
      throw new Error("No PDF active in the current tab to bookmark.");
    }
  }

  const result = await BookmarkService.addBookmark({ pdfId, title, pageNumber });
  logMessage("Saved bookmark", { pdfId, pageNumber });
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
  [MESSAGE_ACTIONS.EXTRACT_PDF_NAVIGATOR]: handleExtractPdfNavigator,
  [MESSAGE_ACTIONS.DOWNLOAD_NAVIGATOR_PDF]: handleDownloadNavigatorPdf,
  [MESSAGE_ACTIONS.GENERATE_NAVIGATOR]: handleGenerateNavigator,
  [MESSAGE_ACTIONS.CHAT_WITH_PDF]: handleChatWithPdf,
  [MESSAGE_ACTIONS.ASK_QUESTION]: handleAskQuestion,
  [MESSAGE_ACTIONS.SEARCH_PDF]: handleSearchPdf,
  [MESSAGE_ACTIONS.GET_EXTENSION_STATUS]: handleGetExtensionStatus,
  [MESSAGE_ACTIONS.TEST_CONNECTION]: handleTestConnection,
  [MESSAGE_ACTIONS.EXTRACT_PDF_TEXT]: handleExtractPdfText,
  [MESSAGE_ACTIONS.EXTRACTED_TEXT_RESULT]: handleExtractedTextResult,
  [MESSAGE_ACTIONS.EXTRACT_IMAGES]: handleExtractImages,
  [MESSAGE_ACTIONS.EXPLAIN_IMAGE]: handleExplainImage,
  [MESSAGE_ACTIONS.SAVE_PROGRESS]: handleSaveProgress,
  [MESSAGE_ACTIONS.GET_PROGRESS]: handleGetProgress,
  [MESSAGE_ACTIONS.DELETE_PROGRESS]: handleDeleteProgress,
  [MESSAGE_ACTIONS.SAVE_BOOKMARK]: handleSaveBookmark,
  [MESSAGE_ACTIONS.GET_BOOKMARKS]: handleGetBookmarks,
  [MESSAGE_ACTIONS.UPDATE_BOOKMARK]: handleUpdateBookmark,
  [MESSAGE_ACTIONS.DELETE_BOOKMARK]: handleDeleteBookmark,
  [MESSAGE_ACTIONS.SEARCH_BOOKMARKS]: handleSearchBookmarks,
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
    await configureSidePanel();
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
