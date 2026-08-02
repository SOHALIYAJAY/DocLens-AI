/**
 * AI PDF Assistant — Content Script
 *
 * Runs on web pages and acts as the bridge between the webpage and the Chrome Extension.
 * Handles PDF detection, text selection, and responds to messages from the background script.
 */

/* ==========================================================================
   Constants
   ========================================================================== */

const LOG_PREFIX = "[AI PDF Assistant · Content]";

// Actions supported by this content script
const ACTIONS = {
  GET_PAGE_INFO: "GET_PAGE_INFO",
  CHECK_PDF: "CHECK_PDF",
  GET_PDF_URL: "GET_PDF_URL",
  HIGHLIGHT_TEXT: "HIGHLIGHT_TEXT",
  EXTRACT_SELECTED_TEXT: "EXTRACT_SELECTED_TEXT",
};

// Chrome's built-in PDF viewer extension ID
const CHROME_PDF_VIEWER_EXTENSION_ID = "mhjfbmdgcfjbbpaeojofohoefgiehjai";

/* ==========================================================================
   Utility Functions
   ========================================================================== */

/**
 * Logs messages to the console with a standard prefix.
 *
 * @param {string} message - The main log message.
 * @param {any} [data] - Optional data to log alongside the message.
 */
function logMessage(message, data = null) {
  if (data) {
    console.log(`${LOG_PREFIX} ${message}`, data);
  } else {
    console.log(`${LOG_PREFIX} ${message}`);
  }
}

/**
 * Gets the currently selected text on the webpage.
 *
 * @returns {string} The trimmed selected text, or an empty string if nothing is selected.
 */
function getSelectedText() {
  const selection = window.getSelection();
  if (selection) {
    return selection.toString().trim();
  }
  return "";
}

/* ==========================================================================
   Page Detection
   ========================================================================== */

/**
 * Detects whether the current page is a PDF document.
 * Checks the URL and whether it's loaded in Chrome's native PDF viewer.
 *
 * @returns {boolean} True if the page is a PDF, false otherwise.
 */
function isPdfPage() {
  const url = window.location.href.toLowerCase();

  // Check if URL ends with .pdf
  if (url.includes(".pdf")) {
    return true;
  }

  // Check if opened via Chrome's built-in PDF viewer
  if (url.includes(CHROME_PDF_VIEWER_EXTENSION_ID)) {
    return true;
  }

  // Check content type if it's an embed or object (Optional advanced check)
  if (document.contentType === "application/pdf") {
    return true;
  }

  return false;
}

/**
 * Collects basic information about the current page.
 *
 * @returns {Object} An object containing page details (URL, title, PDF status, domain, timestamp, pageNumber).
 */
function getPageInfo() {
  const scrollPosition = window.scrollY;
  const estimatedPageHeight = 1000; 
  const pageNumber = Math.ceil((scrollPosition + window.innerHeight) / estimatedPageHeight);
  
  return {
    url: window.location.href,
    title: document.title,
    isPdf: isPdfPage(),
    domain: window.location.hostname,
    timestamp: new Date().toISOString(),
    pageNumber: pageNumber,
  };
}

/* ==========================================================================
   Message Listener
   ========================================================================== */

/**
 * Listens for messages from the background script or popup.
 */
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  logMessage(`Received action: ${request.action}`, request);

  switch (request.action) {
    case ACTIONS.GET_PAGE_INFO:
      sendResponse({ success: true, data: getPageInfo() });
      break;

    case ACTIONS.CHECK_PDF:
      sendResponse({ success: true, isPdf: isPdfPage() });
      break;

    case ACTIONS.GET_PDF_URL:
      sendResponse({
        success: true,
        url: isPdfPage() ? window.location.href : null,
      });
      break;

    case ACTIONS.HIGHLIGHT_TEXT:
      logMessage("HIGHLIGHT_TEXT action triggered (Placeholder)");
      sendResponse({ success: true, message: "Placeholder: Text highlighted" });
      break;

    case ACTIONS.EXTRACT_SELECTED_TEXT:
      const selectedText = getSelectedText();
      logMessage("EXTRACT_SELECTED_TEXT action triggered", { text: selectedText });
      sendResponse({ success: true, text: selectedText });
      break;

    default:
      logMessage(`Unknown action received: ${request.action}`);
      sendResponse({ success: false, error: "Unknown action" });
      break;
  }

  // Return true to indicate we wish to send a response asynchronously
  return true;
});

/* ==========================================================================
   Event Listeners
   ========================================================================== */

/**
 * Listens for text selection on the page.
 */
document.addEventListener("selectionchange", () => {
  const selectedText = getSelectedText();
  if (selectedText.length > 0) {
    // Log the selected text (kept ready for future AI features)
    logMessage("Text selected", { text: selectedText });
  }
});

/**
 * Listens for page visibility changes (e.g., user switches tabs).
 */
document.addEventListener("visibilitychange", () => {
  logMessage(`Page visibility changed: ${document.visibilityState}`);
});

/**
 * Listens for generic page load completion.
 */
window.addEventListener("load", () => {
  logMessage("Page fully loaded");
});

/* ==========================================================================
   PDF Text Extraction
   ========================================================================== */

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === "START_EXTRACTION") {
    extractPdfText();
  }
});

/**
 * Extracts text from the PDF document using pdf.js.
 */
async function extractPdfText() {
  logMessage("Starting PDF text extraction...");
  
  try {
    // 1. Ensure pdfjsLib is loaded
    if (typeof pdfjsLib === "undefined") {
      throw new Error("PDF.js library is not loaded in the content script.");
    }

    // 2. Set the worker source path (must match web_accessible_resources in manifest)
    pdfjsLib.GlobalWorkerOptions.workerSrc = chrome.runtime.getURL("assets/pdf.worker.min.js");

    // 3. Determine the actual PDF URL
    let pdfUrl = window.location.href;
    
    // If we are inside Chrome's native PDF viewer, the actual URL is in the query params
    if (pdfUrl.includes("mhjfbmdgcfjbbpaeojofohoefgiehjai") && pdfUrl.includes("url=")) {
      const urlParams = new URLSearchParams(window.location.search);
      if (urlParams.has("url")) {
        pdfUrl = urlParams.get("url");
      }
    }
    
    // Check for local file:// URLs which Chrome blocks content scripts from fetching
    // (We now handle this in the background script, but just in case this runs...)
    if (pdfUrl.startsWith("file://")) {
      logMessage("Warning: Attempting to read local file directly. This may fail due to CORS.");
    }

    const loadingTask = pdfjsLib.getDocument(pdfUrl);
    const pdf = await loadingTask.promise;
    
    let fullText = "";
    const numPages = pdf.numPages;
    logMessage(`PDF loaded successfully. Total pages: ${numPages}`);

    // 4. Iterate through all pages and extract text
    for (let i = 1; i <= numPages; i++) {
      const page = await pdf.getPage(i);
      const textContent = await page.getTextContent();
      
      // Combine all text items from the page
      const pageText = textContent.items.map(item => item.str).join(" ");
      fullText += pageText + "\n\n";
    }

    fullText = fullText.trim();

    // 5. Check if any text was found
    if (!fullText) {
      throw new Error("No readable text found in this PDF. It might be a scanned image.");
    }

    logMessage("PDF extraction complete.");
    
    // 6. Send success result back to background.js
    chrome.runtime.sendMessage({ 
      action: "EXTRACTED_TEXT_RESULT", 
      payload: { success: true, text: fullText } 
    });

  } catch (error) {
    logMessage("Error extracting PDF text", { error: error.message });
    
    // Send error result back to background.js
    chrome.runtime.sendMessage({ 
      action: "EXTRACTED_TEXT_RESULT", 
      payload: { success: false, error: error.message } 
    });
  }
}

/* ==========================================================================
   Reading Progress Tracker
   ========================================================================== */

let scrollTimeout = null;

/**
 * Initializes the reading progress tracker.
 */
function initReadingProgress(pageInfo) {
  // Check if we have saved progress
  chrome.runtime.sendMessage(
    { action: "GET_PROGRESS", payload: { pdfId: pageInfo.url } },
    (response) => {
      if (response && response.success && response.data) {
        const progress = response.data;
        if (progress.scrollPosition > 0) {
          injectResumeUI(progress);
        }
      }
    }
  );

  // Listen to scroll events on the window
  window.addEventListener("scroll", () => {
    if (scrollTimeout) {
      clearTimeout(scrollTimeout);
    }
    
    // Debounce the save operation to 2 seconds after the user stops scrolling
    scrollTimeout = setTimeout(() => {
      saveReadingProgress(pageInfo);
    }, 2000);
  });
}

/**
 * Calculates current scroll position and saves it to background script.
 */
function saveReadingProgress(pageInfo) {
  const scrollPosition = window.scrollY;
  const scrollHeight = document.documentElement.scrollHeight - window.innerHeight;
  let progressPercentage = 0;
  
  if (scrollHeight > 0) {
    progressPercentage = (scrollPosition / scrollHeight) * 100;
  }
  
  // Very rough estimation of page number based on scroll
  const estimatedPageHeight = 1000; 
  const pageNumber = Math.ceil((scrollPosition + window.innerHeight) / estimatedPageHeight);

  const payload = {
    pdfId: pageInfo.url,
    title: pageInfo.title,
    pageNumber: pageNumber,
    scrollPosition: scrollPosition,
    progressPercentage: progressPercentage.toFixed(2),
  };

  chrome.runtime.sendMessage({ action: "SAVE_PROGRESS", payload });
  logMessage("Saved reading progress locally.", payload);
}

/**
 * Injects a 'Resume Reading' floating button if previous progress is found.
 */
function injectResumeUI(progress) {
  const container = document.createElement("div");
  container.id = "ai-pdf-resume-banner";
  container.style.position = "fixed";
  container.style.bottom = "20px";
  container.style.right = "20px";
  container.style.backgroundColor = "#2a2b32";
  container.style.color = "#ffffff";
  container.style.padding = "12px 16px";
  container.style.borderRadius = "8px";
  container.style.boxShadow = "0 4px 12px rgba(0, 0, 0, 0.3)";
  container.style.fontFamily = "sans-serif";
  container.style.fontSize = "14px";
  container.style.zIndex = "999999";
  container.style.display = "flex";
  container.style.alignItems = "center";
  container.style.gap = "12px";

  const text = document.createElement("span");
  text.textContent = `Resume reading from ${progress.progressPercentage}%?`;
  
  const resumeBtn = document.createElement("button");
  resumeBtn.textContent = "Resume";
  resumeBtn.style.backgroundColor = "#4caf50";
  resumeBtn.style.color = "white";
  resumeBtn.style.border = "none";
  resumeBtn.style.padding = "6px 12px";
  resumeBtn.style.borderRadius = "4px";
  resumeBtn.style.cursor = "pointer";
  resumeBtn.style.fontWeight = "bold";

  const dismissBtn = document.createElement("button");
  dismissBtn.innerHTML = "&times;";
  dismissBtn.style.background = "transparent";
  dismissBtn.style.color = "#aaa";
  dismissBtn.style.border = "none";
  dismissBtn.style.fontSize = "20px";
  dismissBtn.style.cursor = "pointer";
  dismissBtn.style.padding = "0 4px";

  resumeBtn.addEventListener("click", () => {
    window.scrollTo({
      top: progress.scrollPosition,
      behavior: "smooth"
    });
    // For native PDF viewers that support URL hash navigation
    if (window.scrollY === 0 && progress.scrollPosition > 0) {
       logMessage("Native scrolling blocked, attempting URL hash fallback");
       // we can't easily jump to a page in the native viewer without reloading, 
       // but we leave this branch here for custom viewer setups
    }
    container.remove();
  });

  dismissBtn.addEventListener("click", () => {
    container.remove();
  });

  container.appendChild(text);
  container.appendChild(resumeBtn);
  container.appendChild(dismissBtn);

  document.body.appendChild(container);
  
  // Auto-dismiss after 10 seconds
  setTimeout(() => {
    if (document.body.contains(container)) {
      container.remove();
    }
  }, 10000);
}

/* ==========================================================================
   Initialization
   ========================================================================== */

/**
 * Initializes the content script.
 */
function init() {
  logMessage("Content script initialized.");
  
  const pageInfo = getPageInfo();
  logMessage("Page Info:", pageInfo);

  if (pageInfo.isPdf) {
    logMessage("PDF Document detected!");
    initReadingProgress(pageInfo);
  }

  // Send a dummy test message with the page title
  chrome.runtime.sendMessage({ 
    action: "TEST_CONNECTION", 
    payload: { source: "content", title: document.title } 
  });
}

// Run initialization
init();
