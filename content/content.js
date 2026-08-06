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

    case "NAVIGATE_TO_PAGE":
      if (request.pageNumber) {
        navigateToPage(request.pageNumber);
      }
      sendResponse({ success: true });
      break;

    case "OPEN_BOOKMARK_MODAL":
      openInPageBookmarkModal();
      sendResponse({ success: true });
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
   In-Page PDF Bookmark Toolbar & Modal
   ========================================================================== */

/**
 * Injects a sleek floating Toolbar onto PDF pages with "Bookmark Page" and "View Bookmarks" buttons.
 */
function injectPdfToolbarButton() {
  if (document.getElementById("pdf-assistant-floating-toolbar")) return;

  const toolbar = document.createElement("div");
  toolbar.id = "pdf-assistant-floating-toolbar";
  Object.assign(toolbar.style, {
    position: "fixed",
    top: "20px",
    right: "20px",
    zIndex: "999999",
    display: "flex",
    alignItems: "center",
    gap: "8px",
    fontFamily: "Inter, sans-serif"
  });

  // 1. Bookmark Page Button
  const btnBookmark = document.createElement("button");
  btnBookmark.id = "pdf-assistant-bookmark-btn";
  btnBookmark.innerHTML = `
    <span style="font-size: 15px;">🔖</span>
    <span style="font-weight: 600; font-size: 13px;">Bookmark</span>
  `;
  Object.assign(btnBookmark.style, {
    background: "rgba(15, 23, 42, 0.92)",
    color: "#ffffff",
    border: "1px solid rgba(255, 255, 255, 0.15)",
    backdropFilter: "blur(8px)",
    borderRadius: "24px",
    padding: "8px 16px",
    display: "flex",
    alignItems: "center",
    gap: "8px",
    cursor: "pointer",
    boxShadow: "0 8px 24px rgba(0, 0, 0, 0.35)",
    transition: "all 0.2s ease"
  });

  btnBookmark.addEventListener("mouseenter", () => {
    btnBookmark.style.transform = "translateY(-2px) scale(1.03)";
    btnBookmark.style.borderColor = "#06b6d4";
    btnBookmark.style.boxShadow = "0 12px 28px rgba(6, 182, 212, 0.3)";
  });
  btnBookmark.addEventListener("mouseleave", () => {
    btnBookmark.style.transform = "none";
    btnBookmark.style.borderColor = "rgba(255, 255, 255, 0.15)";
    btnBookmark.style.boxShadow = "0 8px 24px rgba(0, 0, 0, 0.35)";
  });
  btnBookmark.addEventListener("click", () => {
    openInPageBookmarkModal();
  });

  // 2. View Bookmarks List Button
  const btnViewList = document.createElement("button");
  btnViewList.id = "pdf-assistant-view-bookmarks-btn";
  btnViewList.innerHTML = `
    <span style="font-size: 15px;">📚</span>
    <span style="font-weight: 600; font-size: 13px;">Stored Bookmarks</span>
  `;
  Object.assign(btnViewList.style, {
    background: "rgba(15, 23, 42, 0.92)",
    color: "#ec4899",
    border: "1px solid rgba(236, 72, 153, 0.3)",
    backdropFilter: "blur(8px)",
    borderRadius: "24px",
    padding: "8px 16px",
    display: "flex",
    alignItems: "center",
    gap: "8px",
    cursor: "pointer",
    boxShadow: "0 8px 24px rgba(0, 0, 0, 0.35)",
    transition: "all 0.2s ease"
  });

  btnViewList.addEventListener("mouseenter", () => {
    btnViewList.style.transform = "translateY(-2px) scale(1.03)";
    btnViewList.style.borderColor = "#ec4899";
    btnViewList.style.boxShadow = "0 12px 28px rgba(236, 72, 153, 0.3)";
  });
  btnViewList.addEventListener("mouseleave", () => {
    btnViewList.style.transform = "none";
    btnViewList.style.borderColor = "rgba(236, 72, 153, 0.3)";
    btnViewList.style.boxShadow = "0 8px 24px rgba(0, 0, 0, 0.35)";
  });
  btnViewList.addEventListener("click", () => {
    chrome.runtime.sendMessage({ action: "OPEN_SIDE_PANEL" });
  });

  toolbar.appendChild(btnBookmark);
  toolbar.appendChild(btnViewList);
  document.body.appendChild(toolbar);
}

/**
 * Shows an in-page toast notification.
 */
function showInPageToast(message, isError = false) {
  let toast = document.getElementById("pdf-assistant-toast");
  if (!toast) {
    toast = document.createElement("div");
    toast.id = "pdf-assistant-toast";
    Object.assign(toast.style, {
      position: "fixed",
      bottom: "24px",
      right: "24px",
      zIndex: "1000001",
      color: "#ffffff",
      padding: "12px 20px",
      borderRadius: "10px",
      fontSize: "13px",
      fontWeight: "600",
      fontFamily: "Inter, sans-serif",
      boxShadow: "0 10px 25px rgba(0, 0, 0, 0.4)",
      transition: "all 0.3s ease",
      display: "flex",
      alignItems: "center",
      gap: "10px"
    });
    document.body.appendChild(toast);
  }

  toast.style.background = isError ? "rgba(239, 68, 68, 0.95)" : "rgba(16, 185, 129, 0.95)";
  toast.innerHTML = `${isError ? '⚠️' : '✅'} <span>${message}</span>`;
  toast.style.display = "flex";
  toast.style.opacity = "1";

  if (toast._timer) clearTimeout(toast._timer);
  toast._timer = setTimeout(() => {
    toast.style.opacity = "0";
    setTimeout(() => { toast.style.display = "none"; }, 300);
  }, 3000);
}

/**
 * Opens the in-page Bookmark creation modal.
 */
function openInPageBookmarkModal() {
  const pageInfo = getPageInfo();
  let overlay = document.getElementById("pdf-assistant-modal-overlay");

  if (!overlay) {
    overlay = document.createElement("div");
    overlay.id = "pdf-assistant-modal-overlay";
    Object.assign(overlay.style, {
      position: "fixed",
      top: "0",
      left: "0",
      width: "100vw",
      height: "100vh",
      background: "rgba(0, 0, 0, 0.75)",
      backdropFilter: "blur(4px)",
      zIndex: "1000000",
      display: "flex",
      alignItems: "center",
      justify-content: "center",
      fontFamily: "Inter, sans-serif"
    });

    overlay.innerHTML = `
      <div style="width: 100%; max-width: 380px; background: #18181b; border: 1px solid rgba(255,255,255,0.1); border-radius: 16px; padding: 20px; box-shadow: 0 20px 40px rgba(0,0,0,0.5); color: #fff;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
          <h3 style="font-size: 16px; font-weight: 700; margin: 0; display: flex; align-items: center; gap: 8px;">
            <span>🔖</span> Add PDF Bookmark
          </h3>
          <button id="pdf-assistant-close-modal" style="background: none; border: none; color: #94a3b8; font-size: 20px; cursor: pointer;">&times;</button>
        </div>
        <div style="margin-bottom: 14px;">
          <label style="display: block; font-size: 12px; font-weight: 600; color: #94a3b8; margin-bottom: 6px;">Bookmark Title <span style="color: #ef4444;">*</span></label>
          <input type="text" id="pdf-assistant-modal-title" placeholder="e.g. Chapter 1 Summary" style="width: 100%; padding: 10px 12px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.15); background: #27272a; color: #fff; font-size: 13px; box-sizing: border-box;" required />
        </div>
        <div style="margin-bottom: 20px;">
          <label style="display: block; font-size: 12px; font-weight: 600; color: #94a3b8; margin-bottom: 6px;">Page Number <span style="color: #ef4444;">*</span></label>
          <input type="number" id="pdf-assistant-modal-page" min="1" placeholder="Enter page number" style="width: 100%; padding: 10px 12px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.15); background: #27272a; color: #fff; font-size: 13px; box-sizing: border-box;" required />
        </div>
        <div style="display: flex; gap: 10px; justify-content: flex-end;">
          <button id="pdf-assistant-cancel-modal" style="padding: 8px 16px; border-radius: 8px; background: rgba(255,255,255,0.1); border: none; color: #fff; font-weight: 600; cursor: pointer;">Cancel</button>
          <button id="pdf-assistant-save-modal" style="padding: 8px 16px; border-radius: 8px; background: #06b6d4; border: none; color: #fff; font-weight: 600; cursor: pointer;">Save Bookmark</button>
        </div>
      </div>
    `;

    document.body.appendChild(overlay);

    document.getElementById("pdf-assistant-close-modal").addEventListener("click", () => {
      overlay.style.display = "none";
    });
    document.getElementById("pdf-assistant-cancel-modal").addEventListener("click", () => {
      overlay.style.display = "none";
    });
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) overlay.style.display = "none";
    });

    document.getElementById("pdf-assistant-save-modal").addEventListener("click", async () => {
      const titleInput = document.getElementById("pdf-assistant-modal-title");
      const pageInput = document.getElementById("pdf-assistant-modal-page");
      
      const title = titleInput ? titleInput.value.trim() : "";
      const pageNumber = pageInput ? parseInt(pageInput.value, 10) : pageInfo.pageNumber;

      if (!title) {
        showInPageToast("Bookmark title is required", true);
        return;
      }
      if (isNaN(pageNumber) || pageNumber < 1) {
        showInPageToast("Please enter a valid page number", true);
        return;
      }

      chrome.runtime.sendMessage({
        action: "SAVE_BOOKMARK",
        payload: {
          pdfId: pageInfo.url,
          title,
          pageNumber
        }
      }, (response) => {
        if (chrome.runtime.lastError || (response && response.success === false)) {
          const err = chrome.runtime.lastError?.message || response?.error || "Error saving bookmark";
          showInPageToast(err, true);
        } else {
          showInPageToast(`Bookmark "${title}" (Page ${pageNumber}) saved!`);
          overlay.style.display = "none";
        }
      });
    });
  }

  const titleInput = document.getElementById("pdf-assistant-modal-title");
  const pageInput = document.getElementById("pdf-assistant-modal-page");

  if (titleInput) titleInput.value = `Page ${pageInfo.pageNumber} Notes`;
  if (pageInput) pageInput.value = pageInfo.pageNumber;

  overlay.style.display = "flex";
  setTimeout(() => {
    if (titleInput) {
      titleInput.focus();
      titleInput.select();
    }
  }, 50);
}

/**
 * Smoothly scrolls to the bookmarked page and highlights it briefly.
 */
function navigateToPage(pageNumber) {
  const targetPage = parseInt(pageNumber, 10);
  if (isNaN(targetPage) || targetPage < 1) return;

  logMessage(`Navigating to Page ${targetPage}`);

  const estimatedPageHeight = 1000;
  const targetScrollY = (targetPage - 1) * estimatedPageHeight;

  window.scrollTo({
    top: targetScrollY,
    behavior: "smooth"
  });

  highlightTargetPage();
}

/**
 * Creates a translucent glowing outline highlight across the viewport that fades out smoothly.
 */
function highlightTargetPage() {
  let highlight = document.getElementById("pdf-assistant-page-highlight");
  if (!highlight) {
    highlight = document.createElement("div");
    highlight.id = "pdf-assistant-page-highlight";
    Object.assign(highlight.style, {
      position: "fixed",
      top: "0",
      left: "0",
      width: "100vw",
      height: "100vh",
      pointerEvents: "none",
      zIndex: "999998",
      boxShadow: "inset 0 0 50px rgba(6, 182, 212, 0.7), 0 0 30px rgba(6, 182, 212, 0.5)",
      border: "4px solid #06b6d4",
      background: "rgba(6, 182, 212, 0.08)",
      transition: "opacity 1.2s ease-out"
    });
    document.body.appendChild(highlight);
  }

  highlight.style.opacity = "1";
  highlight.style.display = "block";

  if (highlight._timer) clearTimeout(highlight._timer);
  highlight._timer = setTimeout(() => {
    highlight.style.opacity = "0";
    setTimeout(() => { highlight.style.display = "none"; }, 1200);
  }, 800);
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
    injectPdfToolbarButton();
  }

  // Send a dummy test message with the page title
  chrome.runtime.sendMessage({ 
    action: "TEST_CONNECTION", 
    payload: { source: "content", title: document.title } 
  });
}

// Run initialization
init();
