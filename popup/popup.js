/**
 * AI PDF Assistant — Popup Script
 * Handles UI initialization and placeholder click interactions.
 * Backend / AI logic is not implemented yet.
 */

/* ==========================================================================
   Placeholder Data
   ========================================================================== */



/** Extension version shown in the footer */
const EXTENSION_VERSION = "1.0.0";

/* ==========================================================================
   Utility Helpers
   ========================================================================== */

/**
 * Logs an action to the console with a consistent prefix.
 * @param {string} action - Human-readable action name
 * @param {object} [details={}] - Optional extra context
 */
function logAction(action, details = {}) {
  console.log(`[AI PDF Assistant] ${action}`, details);
}

/**
 * Shows a lightweight placeholder alert for user-facing feedback.
 * Replace with toast notifications or in-app UI later.
 * @param {string} message - Message to display
 */
function showPlaceholderAlert(message) {
  window.alert(message);
}

/**
 * Shows the AI loading indicator.
 */
function showLoading(text) {
  const section = document.getElementById("ai-response-section");
  const loading = document.getElementById("ai-loading-indicator");
  const loadingText = document.getElementById("ai-loading-text");
  const container = document.getElementById("ai-response-container");
  
  if (section && loading && loadingText && container) {
    section.style.display = "block";
    loading.style.display = "flex";
    loadingText.textContent = text;
    container.style.display = "none";
  }
}

/**
 * Basic markdown parser to convert text to HTML for AI responses.
 */
function formatMarkdown(text) {
  if (!text) return "";
  
  let html = text;
  
  // 1. Bold: **text**
  html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  
  // 2. List items: * text or - text
  html = html.replace(/^\s*[\*\-]\s+(.*)/gm, '<li>$1</li>');
  
  // 3. Wrap consecutive <li> tags in <ul>
  html = html.replace(/(<li>.*<\/li>\n?)+/g, match => `<ul style="margin: 8px 0; padding-left: 20px; list-style-type: disc;">${match}</ul>`);
  
  // 3.5 Parse tables
  html = html.replace(/(?:(?:\|.*\|)\s*\n?)+/g, match => {
     if (!match.match(/\|[-\s|:]+\|/)) {
        return match;
     }
     let rows = match.trim().split('\n');
     let tableHtml = '<table style="width: 100%; border-collapse: collapse; margin-bottom: 8px; font-size: 13px;">';
     
     let isHeader = true;
     for (let i = 0; i < rows.length; i++) {
         let row = rows[i].trim();
         if (row.match(/^\|[-\s|:]+\|$/)) {
             isHeader = false;
             continue;
         }
         
         let cells = row.split('|');
         if (cells.length > 0 && cells[0].trim() === '') cells.shift();
         if (cells.length > 0 && cells[cells.length - 1].trim() === '') cells.pop();
         
         tableHtml += '<tr>';
         let tag = isHeader ? 'th' : 'td';
         let style = isHeader 
           ? 'border: 1px solid #555; padding: 6px; background-color: rgba(255,255,255,0.1); text-align: left; font-weight: bold;' 
           : 'border: 1px solid #555; padding: 6px;';
           
         cells.forEach(cell => {
             tableHtml += `<${tag} style="${style}">${cell.trim()}</${tag}>`;
         });
         tableHtml += '</tr>';
     }
     tableHtml += '</table>';
     return tableHtml;
  });
  
  // 4. Wrap blocks in <p> and replace remaining single newlines with <br>
  html = html.split(/\n{2,}/).map(block => {
    if (block.trim().startsWith('<ul') || block.trim().startsWith('<table')) {
      return block;
    }
    return `<p style="margin-bottom: 8px;">${block.replace(/\n/g, '<br>')}</p>`;
  }).join('');
  
  return html;
}

/**
 * Displays the AI response or an error.
 */
function showAiResponse(text, isError = false) {
  const loading = document.getElementById("ai-loading-indicator");
  const container = document.getElementById("ai-response-container");
  
  if (loading && container) {
    loading.style.display = "none";
    container.style.display = "block";
    if (isError) {
      container.textContent = text;
    } else {
      container.innerHTML = formatMarkdown(text);
    }
    container.style.borderLeftColor = isError ? "#ef4444" : "#3b82f6";
    container.style.background = isError ? "rgba(239, 68, 68, 0.1)" : "rgba(59, 130, 246, 0.1)";
  }
}

/**
 * Calculates storage usage as a percentage for the progress bar.
 * @param {number} usedMb
 * @param {number} limitMb
 * @returns {number}
 */
function getStoragePercent(usedMb, limitMb) {
  if (limitMb <= 0) {
    return 0;
  }
  return Math.min(100, Math.round((usedMb / limitMb) * 100));
}

/* ==========================================================================
   DOM Rendering
   ========================================================================== */





/* ==========================================================================
   Event Handlers
   ========================================================================== */

/** Opens the extension settings (placeholder). */
function handleSettingsClick() {
  logAction("Settings clicked");
  showPlaceholderAlert("Settings panel will open here.");
}



/** Opens the chat-with-PDF feature in popup (via prompt for now). */
function handleChatPdfClick() {
  logAction("Chat with PDF clicked");
  
  const question = prompt("What would you like to ask about the uploaded PDF?");
  if (!question) return;

  showLoading("Generating answer...");
  logAction("Sending CHAT_WITH_PDF to background");
  
  chrome.runtime.sendMessage(
    { action: "CHAT_WITH_PDF", payload: { question } },
    (response) => {
      logAction("Background received CHAT_WITH_PDF response", response);
      if (chrome.runtime.lastError || !response || !response.success) {
        showAiResponse("Failed to chat: " + (chrome.runtime.lastError?.message || response?.error || "Unknown error"), true);
      } else {
        showAiResponse(response.data.answer || "No answer received.");
      }
    }
  );
}

/** Starts PDF summarization using extracted text and specified length. */
function handleSummarizePdfClick(length = "medium") {
  logAction(`Summarize PDF (${length}) clicked`);
  const extractedTextArea = document.getElementById("extracted-text-area");
  const text = extractedTextArea ? extractedTextArea.innerText : "";
  
  if (!text || text.includes("Extracting text") || text.includes("Extracted text will appear here")) {
    showPlaceholderAlert("Please click 'Extract Text from PDF' first, then try summarizing.");
    return;
  }

  showLoading(`Generating ${length} summary...`);
  logAction("Sending SUMMARIZE_PDF to background");

  chrome.runtime.sendMessage(
    { action: "SUMMARIZE_PDF", payload: { text, summary_type: length } },
    (response) => {
      logAction("Background received SUMMARIZE_PDF response", response);
      if (chrome.runtime.lastError || !response || !response.success) {
        showAiResponse("Failed to summarize: " + (chrome.runtime.lastError?.message || response?.error || "Unknown error"), true);
      } else {
        showAiResponse(response.data.summary || "No summary received.");
      }
    }
  );
}

/** Opens the ask-questions flow (same as Chat for popup). */
function handleAskQuestionsClick() {
  logAction("Ask Questions clicked");
  handleChatPdfClick();
}

/** Bookmarks the current PDF page. */
function handleBookmarkPdfClick() {
  logAction("Bookmark PDF clicked");
  
  chrome.runtime.sendMessage({ action: "SAVE_BOOKMARK", payload: {} }, (response) => {
    if (chrome.runtime.lastError || !response || !response.success) {
      const errorMsg = chrome.runtime.lastError?.message || response?.error || "Unknown error";
      logAction("Failed to bookmark page", { error: errorMsg });
      showPlaceholderAlert("Failed to bookmark page: " + errorMsg);
    } else {
      logAction("Page bookmarked successfully");
      showPlaceholderAlert(`Bookmarked page ${response.data.pageNumber} successfully!\nOpen the Sidepanel Bookmarks tab to view it.`);
    }
  });
}

/** Extracts PDF text via background script. */
function handleExtractPdfClick() {
  logAction("Extract PDF clicked");
  
  const btn = document.getElementById("btn-extract-pdf");
  if (btn) btn.disabled = true;
  
  const section = document.getElementById("extracted-text-section");
  const textArea = document.getElementById("extracted-text-area");
  
  if (section && textArea) {
    section.style.display = "block";
    textArea.innerHTML = "<em>Extracting text... please wait.</em>";
  }

  // Ask background script to begin extraction
  chrome.runtime.sendMessage({ action: "EXTRACT_PDF_TEXT" });
}

/** Copies extracted text to clipboard. */
async function handleCopyExtractedText(event) {
  const btn = event.currentTarget;
  const textArea = document.getElementById("extracted-text-area");
  
  if (textArea && textArea.innerText) {
    try {
      await navigator.clipboard.writeText(textArea.innerText);
      const originalHtml = btn.innerHTML;
      btn.innerHTML = '<i class="fa-solid fa-check"></i>';
      btn.style.color = "var(--color-success)";
      setTimeout(() => {
        btn.innerHTML = originalHtml;
        btn.style.color = "var(--color-text-muted)";
      }, 2000);
      logAction("Copied extracted text");
    } catch (err) {
      logAction("Failed to copy text", { error: err.message });
      showPlaceholderAlert("Failed to copy text to clipboard.");
    }
  }
}



/* ==========================================================================
   Event Binding
   ========================================================================== */

/**
 * Attaches click and change listeners to all interactive elements.
 */
function bindEventListeners() {
  // Header
  document.getElementById("btn-settings")?.addEventListener("click", handleSettingsClick);

  // Quick Actions
  document.getElementById("btn-chat-pdf")?.addEventListener("click", handleChatPdfClick);
  document.getElementById("btn-sum-s")?.addEventListener("click", () => handleSummarizePdfClick("small"));
  document.getElementById("btn-sum-m")?.addEventListener("click", () => handleSummarizePdfClick("medium"));
  document.getElementById("btn-sum-l")?.addEventListener("click", () => handleSummarizePdfClick("large"));
  document
    .getElementById("btn-ask-questions")
    ?.addEventListener("click", handleAskQuestionsClick);
  document.getElementById("btn-bookmark-pdf")?.addEventListener("click", handleBookmarkPdfClick);
  document.getElementById("btn-extract-pdf")?.addEventListener("click", handleExtractPdfClick);
  document.getElementById("btn-copy-extracted")?.addEventListener("click", handleCopyExtractedText);

  // Footer
  document.getElementById("btn-help")?.addEventListener("click", () => {
    showPlaceholderAlert("Help documentation will be available soon.");
  });
}

/* ==========================================================================
   Initialization
   ========================================================================== */

/**
 * Bootstraps the popup UI when the DOM is ready.
 */
function initPopup() {

  bindEventListeners();

  logAction("Popup initialized");

  // Send a dummy test message to the background script
  chrome.runtime.sendMessage({ 
    action: "TEST_CONNECTION", 
    payload: { source: "popup", data: "Hello from the Popup!" } 
  });

  // Listen for the extracted text result from background
  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.action === "EXTRACTED_TEXT_RESULT") {
      const btn = document.getElementById("btn-extract-pdf");
      if (btn) btn.disabled = false;
      
      const section = document.getElementById("extracted-text-section");
      const textArea = document.getElementById("extracted-text-area");
      
      if (section && textArea) {
        section.style.display = "block";
        if (message.success) {
          // Format as key points (bullet list) by splitting newlines
          const points = message.text.split('\n').filter(p => p.trim().length > 0);
          if (points.length === 1 && points[0].includes("via backend upload")) {
             textArea.innerHTML = `<p>${points[0]}</p>`;
          } else {
             const ul = document.createElement("ul");
             ul.style.listStyleType = "disc";
             ul.style.paddingLeft = "20px";
             points.forEach(point => {
               const li = document.createElement("li");
               li.style.marginBottom = "8px";
               li.textContent = point.trim();
               ul.appendChild(li);
             });
             textArea.innerHTML = "";
             textArea.appendChild(ul);
          }
        } else {
          textArea.innerHTML = `<span style="color: #ef4444;">Error: ${message.error}</span>`;
        }
      }
    }
  });
}

document.addEventListener("DOMContentLoaded", initPopup);
