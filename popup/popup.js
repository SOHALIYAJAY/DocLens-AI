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
  
  const formSection = document.getElementById("popup-bookmark-section");
  const pageInput = document.getElementById("popup-bookmark-page-input");
  const titleInput = document.getElementById("popup-bookmark-title-input");

  if (!formSection || !pageInput || !titleInput) return;

  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    const activeTab = tabs[0];
    let defaultPage = 1;

    if (activeTab) {
      chrome.tabs.sendMessage(activeTab.id, { action: "GET_PAGE_INFO" }, (pageInfoRes) => {
        // ALWAYS check chrome.runtime.lastError FIRST to avoid "Unchecked runtime.lastError" log!
        if (chrome.runtime.lastError) {
          logAction("Content script unready on tab, using default page 1", chrome.runtime.lastError.message);
        } else if (pageInfoRes && pageInfoRes.success && pageInfoRes.data) {
          defaultPage = pageInfoRes.data.pageNumber || 1;
        }
        
        pageInput.value = defaultPage;
        titleInput.value = `Page ${defaultPage} Notes`;
        formSection.style.display = "block";
        setTimeout(() => {
          titleInput.focus();
          titleInput.select();
        }, 50);
      });
    } else {
      pageInput.value = 1;
      titleInput.value = "Page 1 Notes";
      formSection.style.display = "block";
    }
  });
}

function handleClosePopupBookmark() {
  const formSection = document.getElementById("popup-bookmark-section");
  if (formSection) formSection.style.display = "none";
}

function handleSavePopupBookmark() {
  const pageInput = document.getElementById("popup-bookmark-page-input");
  const titleInput = document.getElementById("popup-bookmark-title-input");

  const pageNumber = pageInput ? parseInt(pageInput.value, 10) : 1;
  const title = titleInput ? titleInput.value.trim() : "";

  if (isNaN(pageNumber) || pageNumber < 1) {
    showPlaceholderAlert("Please enter a valid Page Number (1 or greater).");
    return;
  }
  if (!title) {
    showPlaceholderAlert("Please enter a Bookmark Title.");
    return;
  }

  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    const activeTab = tabs[0];
    const pdfId = activeTab ? activeTab.url : "unknown-pdf";

    chrome.runtime.sendMessage({
      action: "SAVE_BOOKMARK",
      payload: {
        pdfId,
        title,
        pageNumber
      }
    }, (response) => {
      if (chrome.runtime.lastError || (response && response.success === false)) {
        const errorMsg = chrome.runtime.lastError?.message || response?.error || "Unknown error";
        logAction("Failed to save bookmark from popup", { error: errorMsg });
        showPlaceholderAlert("Failed to save bookmark: " + errorMsg);
      } else {
        logAction("Page bookmarked successfully from popup", response);
        showPlaceholderAlert(`🔖 Bookmarked "${title}" (Page ${pageNumber}) successfully!\nClick the bookmark icon in the header to view & manage bookmarks.`);
        handleClosePopupBookmark();
        const section = document.getElementById("popup-bookmarks-list-section");
        if (section && section.style.display !== "none") {
          renderPopupBookmarks();
        }
      }
    });
  });
}

async function handleRefreshPopup() {
  logAction("Popup refresh clicked");
  const btn = document.getElementById("btn-refresh-popup");
  const icon = btn ? btn.querySelector("i") : null;
  if (icon) icon.classList.add("spinning");

  try {
    await new Promise((resolve) => {
      chrome.storage.local.remove(["lastExtractedText", "lastExtractedImages"], () => {
        resolve();
      });
    });
    logAction("Popup refreshed successfully");
    setTimeout(() => {
      window.location.reload();
    }, 600);
  } catch (err) {
    logAction("Error refreshing popup", err);
  } finally {
    setTimeout(() => {
      if (icon) icon.classList.remove("spinning");
    }, 600);
  }
}

async function handleViewAllBookmarksClick() {
  logAction("View All Bookmarks clicked");
  const section = document.getElementById("popup-bookmarks-list-section");
  if (section) {
    if (section.style.display === "none") {
      // Close add bookmark section if open
      const addSection = document.getElementById("popup-bookmark-section");
      if (addSection) addSection.style.display = "none";
      
      section.style.display = "block";
      await renderPopupBookmarks();
    } else {
      section.style.display = "none";
    }
  }
}

async function renderPopupBookmarks() {
  const list = document.getElementById("popup-bookmarks-list");
  if (!list) return;
  list.innerHTML = "";

  try {
    let bookmarks = [];
    if (typeof BookmarkService !== "undefined") {
      bookmarks = await BookmarkService.getAllBookmarks();
    }

    if (bookmarks.length === 0) {
      list.innerHTML = `<li style="font-size: 11px; color: var(--color-text-muted); text-align: center; padding: 10px;">No bookmarks saved.</li>`;
      return;
    }

    bookmarks.forEach(bm => {
      const li = document.createElement("li");
      li.style.display = "flex";
      li.style.justify = "space-between";
      li.style.alignItems = "center";
      li.style.padding = "8px 10px";
      li.style.background = "rgba(255, 255, 255, 0.03)";
      li.style.border = "1px solid var(--color-border)";
      li.style.borderRadius = "6px";
      li.style.cursor = "pointer";
      li.style.marginBottom = "4px";

      li.innerHTML = `
        <div style="display: flex; flex-direction: column; gap: 2px; flex: 1;">
          <span style="font-size: 12px; font-weight: 500; color: var(--color-text);">${bm.title}</span>
          <span style="font-size: 10px; color: var(--color-text-muted);">Page ${bm.pageNumber}</span>
        </div>
        <div style="display: flex; gap: 6px; align-items: center;">
          <button type="button" class="btn-jump-bm" style="background: none; border: none; color: #10a37f; cursor: pointer; padding: 4px;" title="Jump to page">
            <i class="fa-solid fa-arrow-up-right-from-square" style="font-size: 11px;"></i>
          </button>
          <button type="button" class="btn-delete-bm" style="background: none; border: none; color: #ef4444; cursor: pointer; padding: 4px;" title="Delete bookmark">
            <i class="fa-solid fa-trash" style="font-size: 11px;"></i>
          </button>
        </div>
      `;

      const jumpAction = async (e) => {
        if (e) e.stopPropagation();
        try {
          const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
          const activeTab = tabs[0];
          if (activeTab) {
            chrome.tabs.sendMessage(activeTab.id, {
              action: "JUMP_TO_PAGE",
              pageNumber: bm.pageNumber
            }, (res) => {
              if (chrome.runtime.lastError) {}
            });
            if (bm.pdfId) {
              let cleanUrl = bm.pdfId.split("#")[0];
              const newUrl = `${cleanUrl}#page=${bm.pageNumber}`;
              if (activeTab.url !== newUrl) {
                chrome.tabs.update(activeTab.id, { url: newUrl });
              }
            }
          }
        } catch (err) {
          logAction("Failed to jump from popup", err);
        }
      };

      li.addEventListener("click", jumpAction);
      li.querySelector(".btn-jump-bm").addEventListener("click", jumpAction);

      li.querySelector(".btn-delete-bm").addEventListener("click", async (e) => {
        e.stopPropagation();
        try {
          if (typeof BookmarkService !== "undefined") {
            await BookmarkService.deleteBookmark(bm.id);
            await renderPopupBookmarks();
          }
        } catch (err) {
          logAction("Failed to delete bookmark from popup", err);
        }
      });

      list.appendChild(li);
    });
  } catch (err) {
    logAction("Error rendering popup bookmarks", err);
  }
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
  document.getElementById("btn-refresh-popup")?.addEventListener("click", handleRefreshPopup);
  document.getElementById("btn-popup-all-bookmarks")?.addEventListener("click", handleViewAllBookmarksClick);

  // Quick Actions
  document.getElementById("btn-chat-pdf")?.addEventListener("click", handleChatPdfClick);
  document.getElementById("btn-sum-s")?.addEventListener("click", () => handleSummarizePdfClick("small"));
  document.getElementById("btn-sum-m")?.addEventListener("click", () => handleSummarizePdfClick("medium"));
  document.getElementById("btn-sum-l")?.addEventListener("click", () => handleSummarizePdfClick("large"));
  document
    .getElementById("btn-ask-questions")
    ?.addEventListener("click", handleAskQuestionsClick);
  document.getElementById("btn-bookmark-pdf")?.addEventListener("click", handleBookmarkPdfClick);
  document.getElementById("btn-view-all-bookmarks")?.addEventListener("click", handleViewAllBookmarksClick);
  document.getElementById("btn-close-popup-bookmark")?.addEventListener("click", handleClosePopupBookmark);
  document.getElementById("btn-close-popup-bookmarks-list")?.addEventListener("click", () => {
    const section = document.getElementById("popup-bookmarks-list-section");
    if (section) section.style.display = "none";
  });
  document.getElementById("btn-cancel-popup-bookmark")?.addEventListener("click", handleClosePopupBookmark);
  document.getElementById("btn-save-popup-bookmark")?.addEventListener("click", handleSavePopupBookmark);
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

  // Load previously extracted text & images from storage if available
  chrome.storage.local.get(["lastExtractedText", "lastExtractedImages"], (stored) => {
    if (stored.lastExtractedText) {
      const section = document.getElementById("extracted-text-section");
      const textArea = document.getElementById("extracted-text-area");
      if (section && textArea) {
        section.style.display = "block";
        textArea.innerHTML = `<p>${stored.lastExtractedText}</p>`;
      }
    }
    if (stored.lastExtractedImages) {
      renderPopupExtractedImages(stored.lastExtractedImages);
    }
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

      if (message.success && message.images) {
        renderPopupExtractedImages(message.images);
      }
    }
  });
}

/**
 * Renders extracted images directly in the popup UI with Explain Image capabilities.
 */
function renderPopupExtractedImages(images) {
  const section = document.getElementById("extracted-images-section");
  const gallery = document.getElementById("popup-images-gallery");
  if (!section || !gallery) return;

  section.style.display = "block";
  gallery.innerHTML = "";

  if (!images || images.length === 0) {
    gallery.innerHTML = '<div style="color: var(--color-text-muted); font-size: 12px; font-style: italic;">No images found in this PDF document.</div>';
    return;
  }

  images.forEach((img) => {
    const card = document.createElement("div");
    card.style = "border: 1px solid var(--color-border); border-radius: 6px; padding: 10px; background: rgba(255,255,255,0.03); margin-bottom: 8px;";

    const imgEl = document.createElement("img");
    imgEl.src = `http://127.0.0.1:8000/image/${img.image_id}`;
    imgEl.style = "max-width: 100%; height: auto; border-radius: 4px; display: block; margin-bottom: 8px;";

    const meta = document.createElement("div");
    meta.style = "display: flex; justify-content: space-between; align-items: center; font-size: 11px; color: var(--color-text-muted);";
    meta.innerHTML = `<span>Page ${img.page}</span>`;

    const explainBtn = document.createElement("button");
    explainBtn.className = "btn btn-secondary";
    explainBtn.style = "padding: 4px 8px; font-size: 11px; font-weight: 600;";
    explainBtn.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles"></i> Explain Image';

    const explanationContainer = document.createElement("div");
    explanationContainer.style = "margin-top: 8px; font-size: 12px; display: none; background: rgba(0,0,0,0.4); padding: 10px; border-radius: 4px; border: 1px solid var(--color-border); color: #f1f5f9; line-height: 1.5;";

    explainBtn.addEventListener("click", () => {
      explainBtn.disabled = true;
      explainBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>';
      explanationContainer.style.display = "block";
      explanationContainer.innerHTML = '<em>Analyzing image...</em>';

      chrome.runtime.sendMessage({
        action: "EXPLAIN_IMAGE",
        payload: { image_id: img.image_id }
      }, (explainRes) => {
        explainBtn.disabled = false;
        explainBtn.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles"></i> Explain Image';

        if (chrome.runtime.lastError || !explainRes || !explainRes.success) {
          explanationContainer.innerHTML = '<span style="color: #ef4444;">Failed to analyze image.</span>';
          return;
        }

        const result = explainRes.data || explainRes;

        let componentsHtml = "";
        if (result.important_components && result.important_components.length > 0) {
          componentsHtml = `<div style="margin-top:6px;"><strong>Important Components:</strong><ul style="padding-left:16px; margin:4px 0;">` + result.important_components.map(c => `<li>${c}</li>`).join("") + `</ul></div>`;
        }

        let relationshipsHtml = "";
        if (result.relationships && result.relationships.length > 0) {
          relationshipsHtml = `<div style="margin-top:6px;"><strong>Relationships:</strong><ul style="padding-left:16px; margin:4px 0;">` + result.relationships.map(r => `<li>${r}</li>`).join("") + `</ul></div>`;
        }

        let takeawaysHtml = "";
        if (result.key_takeaways && result.key_takeaways.length > 0) {
          takeawaysHtml = `<div style="margin-top:6px;"><strong>Key Takeaways:</strong><ul style="padding-left:16px; margin:4px 0;">` + result.key_takeaways.map(k => `<li>${k}</li>`).join("") + `</ul></div>`;
        }

        let applicationHtml = "";
        if (result.real_world_application) {
          applicationHtml = `<div style="margin-top:6px;"><strong>Real-World Application:</strong><br/>${result.real_world_application}</div>`;
        }

        explanationContainer.innerHTML = `
          <strong style="color:#06b6d4; font-size:13px;">${result.title}</strong><br/>
          <em style="color:#94a3b8;">${result.summary}</em><br/>
          <p style="margin-top:6px;">${result.explanation}</p>
          <div style="margin-top:6px; border-top: 1px solid var(--color-border); padding-top: 6px;">
            ${componentsHtml}
            ${relationshipsHtml}
            ${takeawaysHtml}
            ${applicationHtml}
          </div>
        `;
      });
    });

    meta.appendChild(explainBtn);
    card.appendChild(imgEl);
    card.appendChild(meta);
    card.appendChild(explanationContainer);
    gallery.appendChild(card);
  });
}

document.addEventListener("DOMContentLoaded", initPopup);
