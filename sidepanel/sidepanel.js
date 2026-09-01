/**
 * AI PDF Assistant — Side Panel Script
 * Main workspace for PDF + AI interaction.
 * Navigation, UI rendering, and placeholder event handlers only.
 */

/* ==========================================================================
   Placeholder / Sample Data
   ========================================================================== */

const APP_DATA = {
  pdf: {
    name: "Machine Learning Basics.pdf",
    pages: 42,
    size: "2.4 MB",
    progress: 35,
    currentPage: 15,
  },
  version: "1.0.0",
};

const SUGGESTED_QUESTIONS = [
  "Summarize chapter 3",
  "What is gradient descent?",
  "List key terms",
  "Explain neural networks",
];


const NOTES = [
  {
    id: "note-1",
    title: "Key concept: overfitting",
    meta: "Page 12 · 2 hours ago",
  },
  {
    id: "note-2",
    title: "Review backpropagation section",
    meta: "Page 18 · Yesterday",
  },
];

const BOOKMARKS = []; // Not used directly, fetched dynamically

const RECENT_CHATS = [
  {
    id: "chat-1",
    title: "What is supervised learning?",
    meta: "Today · 3 messages",
  },
  {
    id: "chat-2",
    title: "Summarize the introduction",
    meta: "Yesterday · 5 messages",
  },
];

const RECENT_PDFS = [
  {
    id: "pdf-1",
    title: "Q3 Financial Report.pdf",
    meta: "18 pages · Opened 2 days ago",
  },
  {
    id: "pdf-2",
    title: "Product Roadmap 2026.pdf",
    meta: "27 pages · Opened 1 week ago",
  },
];

/** Currently visible panel section ID */
let activeSection = "chat";

/* ==========================================================================
   Utility Helpers
   ========================================================================== */

/**
 * Logs an action with a consistent prefix.
 * @param {string} action
 * @param {object} [details={}]
 */
function logAction(action, details = {}) {
  console.log(`[AI PDF Assistant · Side Panel] ${action}`, details);
}

/**
 * Shows a placeholder alert for user feedback.
 * @param {string} message
 */
function showAlert(message) {
  window.alert(message);
}

/**
 * Escapes HTML characters to prevent XSS.
 */
function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
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
  
  // 4. Parse tables
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
  
  // 5. Wrap blocks in <p> and replace remaining single newlines with <br>
  html = html.split(/\n{2,}/).map(block => {
    if (block.trim().startsWith('<ul') || block.trim().startsWith('<table')) {
      return block;
    }
    return `<p style="margin-bottom: 8px;">${block.replace(/\n/g, '<br>')}</p>`;
  }).join('');
  
  return html;
}

/* ==========================================================================
   Navigation
   ========================================================================== */

/**
 * Switches the visible panel section without reloading the page.
 * @param {string} sectionId - Target section identifier
 */
function navigateToSection(sectionId) {
  const dropdown = document.getElementById("nav-menu-dropdown");
  if (dropdown) dropdown.style.display = "none";

  if (sectionId === activeSection) {
    return;
  }

  const sections = document.querySelectorAll(".panel-section");
  const navItems = document.querySelectorAll(".nav-item, .nav-menu-option");

  sections.forEach((section) => {
    const isTarget = section.dataset.section === sectionId;
    section.classList.toggle("active", isTarget);
    section.hidden = !isTarget;
  });

  navItems.forEach((item) => {
    item.classList.toggle("active", item.dataset.section === sectionId);
  });

  // Update dropdown button label and icon
  const SECTION_MAP = {
    chat: { label: "AI Chat", icon: "fa-comments", color: "#3b82f6" },
    summary: { label: "PDF Summary", icon: "fa-wand-magic-sparkles", color: "#a855f7" },
    qa: { label: "Q&A", icon: "fa-circle-question", color: "#06b6d4" },
    images: { label: "Images", icon: "fa-image", color: "#f59e0b" },
    bookmarks: { label: "Bookmarks", icon: "fa-bookmark", color: "#ec4899" },
  };

  const info = SECTION_MAP[sectionId];
  if (info) {
    const menuLabel = document.getElementById("nav-menu-label");
    const menuIcon = document.getElementById("nav-menu-icon");
    if (menuLabel) menuLabel.textContent = info.label;
    if (menuIcon) {
      menuIcon.className = `fa-solid ${info.icon}`;
      menuIcon.style.color = info.color;
    }
  }

  activeSection = sectionId;
  logAction("Navigated to section", { section: sectionId });

  if (sectionId === "chat") {
    demoTypingIndicator();
  }
}

/**
 * Binds click handlers to navigation dropdown menu.
 */
function initNavigation() {
  const btnMenu = document.getElementById("btn-nav-menu");
  const dropdown = document.getElementById("nav-menu-dropdown");

  btnMenu?.addEventListener("click", (e) => {
    e.stopPropagation();
    if (dropdown) {
      const isVisible = dropdown.style.display === "block";
      dropdown.style.display = isVisible ? "none" : "block";
    }
  });

  dropdown?.addEventListener("click", (event) => {
    const optionBtn = event.target.closest(".nav-menu-option");
    if (optionBtn) {
      const sectionId = optionBtn.dataset.section;
      if (sectionId) navigateToSection(sectionId);
    }
  });

  // Close dropdown when clicking outside
  document.addEventListener("click", (event) => {
    if (dropdown && !dropdown.contains(event.target) && !btnMenu?.contains(event.target)) {
      dropdown.style.display = "none";
    }
  });
}

/* ==========================================================================
   DOM Rendering
   ========================================================================== */

/**
 * Renders suggested question chips in the AI Chat section.
 */
function renderSuggestedQuestions() {
  const container = document.getElementById("suggested-list");

  if (!container) {
    return;
  }

  container.innerHTML = "";

  SUGGESTED_QUESTIONS.forEach((question) => {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "suggested-chip";
    chip.textContent = question;
    chip.dataset.question = question;
    chip.addEventListener("click", () => handleSuggestedQuestion(question));
    container.appendChild(chip);
  });
}


/**
 * Creates a reusable list item card element.
 * @param {object} options
 * @returns {HTMLLIElement}
 */
function createListItemCard({ iconClass, iconType, title, meta, actionLabel, onAction }) {
  const item = document.createElement("li");
  item.className = "list-item-card";
  item.innerHTML = `
    <div class="list-item-icon ${iconType}">
      <i class="fa-solid ${iconClass}" aria-hidden="true"></i>
    </div>
    <div class="list-item-content">
      <span class="list-item-title">${title}</span>
      <span class="list-item-meta">${meta}</span>
    </div>
    <button type="button" class="list-item-action" aria-label="${actionLabel}" title="${actionLabel}">
      <i class="fa-solid fa-arrow-up-right-from-square" aria-hidden="true"></i>
    </button>
  `;

  item.querySelector(".list-item-action")?.addEventListener("click", onAction);

  return item;
}

/** Renders the notes list from sample data. */
function renderNotes() {
  const list = document.getElementById("notes-list");

  if (!list) {
    return;
  }

  list.innerHTML = "";

  NOTES.forEach((note) => {
    list.appendChild(
      createListItemCard({
        iconClass: "fa-note-sticky",
        iconType: "note",
        title: note.title,
        meta: note.meta,
        actionLabel: `Open note: ${note.title}`,
        onAction: () => {
          logAction("Note opened", note);
          showAlert(`Opening note: "${note.title}"\n(Not implemented yet.)`);
        },
      })
    );
  });
}

/* ==========================================================================
   Bookmark Helpers & Rendering
   ========================================================================== */

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function formatDate(isoString) {
  if (!isoString) return "";
  try {
    const d = new Date(isoString);
    return d.toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  } catch (e) {
    return isoString;
  }
}

function showToast(message, isError = false) {
  const toast = document.getElementById("bookmark-toast");
  const msgEl = document.getElementById("toast-message");
  if (!toast || !msgEl) return;

  msgEl.textContent = message;
  toast.classList.toggle("error", isError);
  toast.style.display = "flex";

  if (toast._timer) clearTimeout(toast._timer);
  toast._timer = setTimeout(() => {
    toast.style.display = "none";
  }, 3000);
}

let currentModalMode = "add";

function openBookmarkModal(mode = "add", data = {}) {
  const overlay = document.getElementById("bookmark-modal-overlay");
  const headingTitle = document.getElementById("modal-heading-title");
  const titleInput = document.getElementById("bookmark-modal-title-input");
  const pageInput = document.getElementById("bookmark-modal-page-input");
  const idInput = document.getElementById("bookmark-modal-id");

  if (!overlay || !titleInput || !pageInput) return;

  currentModalMode = mode;
  idInput.value = data.id || "";
  pageInput.value = data.pageNumber || 1;
  titleInput.value = data.title || `Bookmark - Page ${data.pageNumber || 1}`;

  if (headingTitle) {
    const titleSpan = headingTitle.querySelector("span");
    if (titleSpan) titleSpan.textContent = mode === "edit" ? "Edit Bookmark Title" : "Add Bookmark";
  }

  overlay.style.display = "flex";
  setTimeout(() => {
    titleInput.focus();
    titleInput.select();
  }, 50);
}

function closeBookmarkModal() {
  const overlay = document.getElementById("bookmark-modal-overlay");
  if (overlay) overlay.style.display = "none";
}

async function handleSaveBookmarkModal() {
  const titleInput = document.getElementById("bookmark-modal-title-input");
  const pageInput = document.getElementById("bookmark-modal-page-input");
  const idInput = document.getElementById("bookmark-modal-id");

  const title = titleInput ? titleInput.value.trim() : "";
  const pageNumber = pageInput ? parseInt(pageInput.value, 10) : 1;
  const bookmarkId = idInput ? idInput.value : "";

  if (!title) {
    showToast("Please enter a bookmark title.", true);
    return;
  }
  if (isNaN(pageNumber) || pageNumber < 1) {
    showToast("Please enter a valid page number.", true);
    return;
  }

  try {
    const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
    const activeTab = tabs[0];
    const pdfId = activeTab ? activeTab.url : "unknown-pdf";

    if (currentModalMode === "edit") {
      if (typeof BookmarkService !== "undefined") {
        await BookmarkService.updateBookmark(bookmarkId, title);
      } else {
        await new Promise((resolve, reject) => {
          chrome.runtime.sendMessage({
            action: "UPDATE_BOOKMARK",
            payload: { bookmarkId, title }
          }, (res) => {
            if (chrome.runtime.lastError || !res || res.success === false) {
              reject(new Error(chrome.runtime.lastError?.message || res?.error || "Failed to update"));
            } else {
              resolve(res);
            }
          });
        });
      }
      showToast("Bookmark updated successfully!");
    } else {
      if (typeof BookmarkService !== "undefined") {
        await BookmarkService.addBookmark({ pdfId, title, pageNumber });
      } else {
        await new Promise((resolve, reject) => {
          chrome.runtime.sendMessage({
            action: "SAVE_BOOKMARK",
            payload: { pdfId, title, pageNumber }
          }, (res) => {
            if (chrome.runtime.lastError || !res || res.success === false) {
              reject(new Error(chrome.runtime.lastError?.message || res?.error || "Failed to save"));
            } else {
              resolve(res);
            }
          });
        });
      }
      showToast("Bookmark saved successfully!");
    }

    closeBookmarkModal();
    renderBookmarks();
  } catch (err) {
    showToast(err.message || "Failed to save bookmark", true);
  }
}

async function jumpToBookmarkPage(bookmark) {
  logAction("Navigating to bookmark", bookmark);
  try {
    const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
    const activeTab = tabs[0];
    if (activeTab) {
      chrome.tabs.sendMessage(activeTab.id, {
        action: "NAVIGATE_TO_PAGE",
        pageNumber: bookmark.pageNumber
      }, () => {
        if (chrome.runtime.lastError) {
          logAction("Fallback URL hash navigation", chrome.runtime.lastError);
        }
      });

      if (bookmark.pdfId) {
        let cleanUrl = bookmark.pdfId.split("#")[0];
        const newUrl = `${cleanUrl}#page=${bookmark.pageNumber}`;
        if (activeTab.url !== newUrl) {
          chrome.tabs.update(activeTab.id, { url: newUrl });
        }
      }
    }
  } catch (err) {
    logAction("Failed to jump to bookmark page", err);
  }
}

async function handleBookmarkPage() {
  logAction("Add Bookmark button clicked");
  try {
    const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
    const activeTab = tabs[0];
    let pageNumber = 1;
    let title = "PDF Bookmark";

    if (activeTab) {
      try {
        const response = await chrome.tabs.sendMessage(activeTab.id, { action: "GET_PAGE_INFO" });
        if (response && response.success && response.data) {
          pageNumber = response.data.pageNumber || 1;
          title = `Page ${pageNumber} Notes`;
        }
      } catch (_) {
        if (activeTab.title) {
          title = `${activeTab.title} - Page ${pageNumber}`;
        }
      }
    }

    openBookmarkModal("add", { title, pageNumber });
  } catch (err) {
    showToast(err.message || "Failed to open bookmark modal", true);
  }
}

/** Renders saved bookmarks from storage dynamically. */
async function renderBookmarks() {
  const list = document.getElementById("bookmarks-list");
  const emptyState = document.getElementById("bookmarks-empty-state");
  const searchInput = document.getElementById("bookmark-search-input");
  const sortSelect = document.getElementById("bookmark-sort-select");

  if (!list) return;

  const searchQuery = searchInput ? searchInput.value.trim() : "";
  const sortBy = sortSelect ? sortSelect.value : "page-asc";

  let activeTabUrl = null;
  try {
    const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tabs[0]) activeTabUrl = tabs[0].url;
  } catch (_) {}

  let bookmarks = [];
  try {
    if (typeof BookmarkService !== "undefined") {
      bookmarks = await BookmarkService.searchBookmarks(activeTabUrl, searchQuery, sortBy);
    } else {
      bookmarks = await new Promise((resolve) => {
        chrome.runtime.sendMessage({
          action: "SEARCH_BOOKMARKS",
          payload: { pdfId: activeTabUrl, query: searchQuery, sortBy }
        }, (res) => {
          if (res && res.success && res.data) resolve(res.data);
          else resolve([]);
        });
      });
    }
  } catch (e) {
    logAction("Error searching bookmarks", e);
  }

  list.innerHTML = "";

  if (!bookmarks || bookmarks.length === 0) {
    if (emptyState) emptyState.style.display = "block";
    list.style.display = "none";
    return;
  }

  if (emptyState) emptyState.style.display = "none";
  list.style.display = "flex";

  bookmarks.forEach((bookmark) => {
    const card = document.createElement("li");
    card.className = "bookmark-card";
    card.innerHTML = `
      <div class="bookmark-card-left">
        <div class="bookmark-icon-badge">
          <i class="fa-solid fa-bookmark"></i>
        </div>
        <div class="bookmark-info">
          <span class="bookmark-title">${escapeHtml(bookmark.title)}</span>
          <div class="bookmark-meta-row">
            <span class="bookmark-page-badge">Page ${bookmark.pageNumber}</span>
            <span>·</span>
            <span>${formatDate(bookmark.timestamp)}</span>
          </div>
        </div>
      </div>
      <div class="bookmark-actions">
        <button type="button" class="action-btn-sm btn-jump" title="Jump to Page">
          <i class="fa-solid fa-arrow-up-right-from-square"></i>
        </button>
        <button type="button" class="action-btn-sm btn-edit" title="Edit Title">
          <i class="fa-solid fa-pen"></i>
        </button>
        <button type="button" class="action-btn-sm delete btn-delete" title="Delete Bookmark">
          <i class="fa-solid fa-trash"></i>
        </button>
      </div>
    `;

    const jumpAction = () => jumpToBookmarkPage(bookmark);
    card.querySelector(".bookmark-card-left").addEventListener("click", jumpAction);
    card.querySelector(".btn-jump").addEventListener("click", (e) => {
      e.stopPropagation();
      jumpAction();
    });

    card.querySelector(".btn-edit").addEventListener("click", (e) => {
      e.stopPropagation();
      openBookmarkModal("edit", bookmark);
    });

    card.querySelector(".btn-delete").addEventListener("click", async (e) => {
      e.stopPropagation();
      try {
        if (typeof BookmarkService !== "undefined") {
          await BookmarkService.deleteBookmark(bookmark.id);
        } else {
          await new Promise((resolve) => {
            chrome.runtime.sendMessage({
              action: "DELETE_BOOKMARK",
              payload: { bookmarkId: bookmark.id }
            }, resolve);
          });
        }
        showToast("Bookmark deleted");
        renderBookmarks();
      } catch (err) {
        showToast(err.message || "Failed to delete bookmark", true);
      }
    });

    list.appendChild(card);
  });
}

/** Renders history lists (chats + PDFs). */
function renderHistory() {
  const chatsList = document.getElementById("recent-chats-list");
  const pdfsList = document.getElementById("recent-pdfs-list");

  if (chatsList) {
    chatsList.innerHTML = "";

    RECENT_CHATS.forEach((chat) => {
      chatsList.appendChild(
        createListItemCard({
          iconClass: "fa-comments",
          iconType: "history",
          title: chat.title,
          meta: chat.meta,
          actionLabel: `Open chat: ${chat.title}`,
          onAction: () => {
            logAction("Recent chat opened", chat);
            showAlert(`Resuming chat: "${chat.title}"\n(Not implemented yet.)`);
          },
        })
      );
    });
  }

  if (pdfsList) {
    pdfsList.innerHTML = "";

    RECENT_PDFS.forEach((pdf) => {
      pdfsList.appendChild(
        createListItemCard({
          iconClass: "fa-file-pdf",
          iconType: "history",
          title: pdf.title,
          meta: pdf.meta,
          actionLabel: `Open PDF: ${pdf.title}`,
          onAction: () => {
            logAction("Recent PDF opened", pdf);
            showAlert(`Opening "${pdf.title}"\n(Not implemented yet.)`);
          },
        })
      );
    });
  }
}



/* ==========================================================================
   Event Handlers — Header & Global
   ========================================================================== */

function handleSettingsClick() {
  logAction("Settings clicked");
  showAlert("Settings panel will open here.");
}

/* ==========================================================================
   Event Handlers — AI Chat
   ========================================================================== */

function appendChatMessage(text, isUser = false) {
  const container = document.getElementById("chat-messages");
  const typingIndicator = document.getElementById("typing-indicator");
  if (!container) return;

  const msgDiv = document.createElement("div");
  msgDiv.className = isUser ? "message message-user" : "message message-ai";
  
  const avatarClass = isUser ? "user" : "ai";
  const avatarIcon = isUser ? "fa-user" : "fa-robot";
  
  msgDiv.innerHTML = `
    <div class="message-avatar ${avatarClass}">
      <i class="fa-solid ${avatarIcon}" aria-hidden="true"></i>
    </div>
    <div class="message-bubble">
      ${isUser ? `<p>${escapeHtml(text)}</p>` : formatMarkdown(text)}
    </div>
  `;

  if (typingIndicator) {
    container.insertBefore(msgDiv, typingIndicator);
  } else {
    container.appendChild(msgDiv);
  }
  container.scrollTop = container.scrollHeight;
}

async function handleSendChat() {
  const input = document.getElementById("chat-input");
  const btn = document.getElementById("btn-send-chat");
  const indicator = document.getElementById("typing-indicator");
  const message = input?.value.trim();

  if (!message) return;

  logAction("Send chat message", { message });
  appendChatMessage(message, true);
  if (input) input.value = "";
  if (btn) btn.disabled = true;
  if (indicator) indicator.hidden = false;

  try {
    const response = await new Promise((resolve) => {
      chrome.runtime.sendMessage({
        action: "CHAT_WITH_PDF",
        payload: { question: message }
      }, (res) => {
        if (chrome.runtime.lastError) {
          resolve({ success: false, error: chrome.runtime.lastError.message });
        } else {
          resolve(res || { success: false, error: "No response from background." });
        }
      });
    });

    if (indicator) indicator.hidden = true;
    if (btn) btn.disabled = false;

    if (!response || response.success === false) {
      const errDetail = response?.error || "Failed to get response from PDF.";
      appendChatMessage(`❌ Error: ${errDetail}`, false);
    } else {
      const answerData = response.data || response;
      const answer = answerData.answer || response.answer || "No response received.";
      appendChatMessage(answer, false);
    }
  } catch (err) {
    if (indicator) indicator.hidden = true;
    if (btn) btn.disabled = false;
    appendChatMessage(`❌ Error: ${err.message}`, false);
  }
}

function handleClearChat() {
  const container = document.getElementById("chat-messages");
  if (container) {
    container.innerHTML = `
      <div class="message message-ai">
        <div class="message-avatar ai">
          <i class="fa-solid fa-robot" aria-hidden="true"></i>
        </div>
        <div class="message-bubble">
          <p>Hello! I can help you understand this PDF. Ask me anything or try a suggested question below.</p>
        </div>
      </div>
      <div class="typing-indicator" id="typing-indicator" hidden>
        <div class="message-avatar ai">
          <i class="fa-solid fa-robot" aria-hidden="true"></i>
        </div>
        <div class="typing-dots">
          <span></span><span></span><span></span>
        </div>
      </div>
    `;
  }
  showToast("Chat cleared!");
}

/**
 * Inserts a suggested question into the chat input.
 * @param {string} question
 */
function handleSuggestedQuestion(question) {
  const input = document.getElementById("chat-input");

  if (input) {
    input.value = question;
    input.focus();
  }

  logAction("Suggested question selected", { question });
}

/** Briefly shows the typing indicator as a demo. */
function demoTypingIndicator() {
  const indicator = document.getElementById("typing-indicator");

  if (!indicator) {
    return;
  }

  indicator.hidden = false;

  setTimeout(() => {
    indicator.hidden = true;
  }, 2500);
}

/* ==========================================================================
   Event Handlers — Summary, Q&A, Search, Notes, Bookmarks
   ========================================================================== */

let currentSummaryLength = "medium";

function handleSummaryLengthToggle(event) {
  const btn = event.currentTarget;
  currentSummaryLength = btn.dataset.length;
  
  // Update active class
  document.querySelectorAll(".length-toggle").forEach(el => el.classList.remove("active"));
  btn.classList.add("active");
  
  logAction("Summary length changed", { length: currentSummaryLength });
}

async function handleGenerateSummary() {
  logAction("Generate summary clicked", { length: currentSummaryLength });
  
  const generateBtn = document.getElementById("btn-generate-summary");
  const summaryOutput = document.getElementById("executive-summary");
  
  if (!summaryOutput) return;

  // Map length toggles: "short" -> "small", "long" -> "large"
  let summaryType = currentSummaryLength;
  if (summaryType === "short") summaryType = "small";
  if (summaryType === "long") summaryType = "large";

  // Visual loading state
  if (generateBtn) {
    generateBtn.disabled = true;
    generateBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Generating Summary...';
  }

  summaryOutput.innerHTML = `
    <div style="display: flex; align-items: center; gap: 8px; color: var(--color-accent-teal, #20b2aa);">
      <i class="fa-solid fa-circle-notch fa-spin"></i> 
      Generating ${summaryType} summary via Groq AI...
    </div>
  `;

  try {
    const response = await chrome.runtime.sendMessage({
      action: "SUMMARIZE_PDF",
      payload: { summary_type: summaryType }
    });

    if (response && response.success && response.data) {
      const summaryText = response.data.summary || response.data;
      summaryOutput.innerHTML = formatMarkdown(summaryText);
    } else {
      const err = response?.error || "Failed to generate summary.";
      summaryOutput.innerHTML = `<span style="color: #ff6b6b;">⚠️ ${escapeHtml(err)}</span>`;
    }
  } catch (error) {
    summaryOutput.innerHTML = `<span style="color: #ff6b6b;">⚠️ Error: ${escapeHtml(error.message)}</span>`;
  } finally {
    if (generateBtn) {
      generateBtn.disabled = false;
      generateBtn.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles"></i> Generate Summary';
    }
  }
}

async function handleCopySummary(event) {
  const btn = event.currentTarget;
  const targetId = btn.dataset.target;
  const textElement = document.getElementById(targetId);
  
  if (textElement) {
    const textToCopy = textElement.innerText;
    try {
      await navigator.clipboard.writeText(textToCopy);
      
      // Visual feedback
      const originalHtml = btn.innerHTML;
      btn.innerHTML = '<i class="fa-solid fa-check"></i>';
      btn.style.color = "var(--color-success)";
      
      setTimeout(() => {
        btn.innerHTML = originalHtml;
        btn.style.color = "";
      }, 2000);
      
      logAction("Copied summary text", { targetId });
    } catch (err) {
      logAction("Failed to copy text", { error: err.message });
      showAlert("Failed to copy text to clipboard.");
    }
  }
}

function handleExportSummary() {
  const execSummary = document.getElementById("executive-summary")?.innerText || "";
  const bulletSummary = document.getElementById("bullet-summary")?.innerText || "";
  const pageSummary = document.getElementById("page-summary")?.innerText || "";
  
  const content = `AI PDF Assistant - Summary Export\n\n` +
                  `Executive Summary:\n${execSummary}\n\n` +
                  `Bullet Summary:\n${bulletSummary}\n\n` +
                  `Current Page Summary:\n${pageSummary}\n`;
                  
  const blob = new Blob([content], { type: 'text/plain' });
  const url = URL.createObjectURL(blob);
  
  const a = document.createElement('a');
  a.href = url;
  a.download = 'pdf_summary.txt';
  a.click();
  
  URL.revokeObjectURL(url);
  logAction("Exported summary to TXT");
}

async function handleAskQuestion() {
  const input = document.getElementById("qa-question-input");
  const btn = document.getElementById("btn-ask-question");
  const answerCard = document.getElementById("qa-answer-card");
  const loadingIndicator = document.getElementById("qa-loading-indicator");
  const answerText = document.getElementById("qa-answer-text");

  const question = input?.value.trim();

  if (!question) {
    showToast("Please enter a question about your PDF.", true);
    return;
  }

  logAction("Ask Question triggered", { question });

  if (answerCard) answerCard.style.display = "block";
  if (loadingIndicator) loadingIndicator.style.display = "flex";
  if (answerText) answerText.innerHTML = "";
  if (btn) btn.disabled = true;

  try {
    const response = await new Promise((resolve) => {
      chrome.runtime.sendMessage({
        action: "CHAT_WITH_PDF",
        payload: { question }
      }, (res) => {
        if (chrome.runtime.lastError) {
          resolve({ success: false, error: chrome.runtime.lastError.message });
        } else {
          resolve(res || { success: false, error: "No response from extension background." });
        }
      });
    });

    if (loadingIndicator) loadingIndicator.style.display = "none";
    if (btn) btn.disabled = false;

    if (!response || response.success === false) {
      if (answerText) {
        answerText.innerHTML = "Sorry, we not found answer in this time.";
      }
    } else {
      const answerData = response.data || response;
      const answer = answerData.answer || response.answer || "Sorry, we not found answer in this time.";
      if (answerText) {
        answerText.innerHTML = formatMarkdown(answer);
      }
      logAction("Question answered successfully");
    }
  } catch (err) {
    if (loadingIndicator) loadingIndicator.style.display = "none";
    if (btn) btn.disabled = false;
    if (answerText) {
      answerText.innerHTML = "Sorry, we not found answer in this time.";
    }
  }
}


function handleAddNote() {
  logAction("Add note clicked");
  showAlert("Add a new note.\n(Not implemented yet.)");
}

/**
 * Renders automatically extracted images.
 */
function renderExtractedImages(images) {
  const gallery = document.getElementById("images-gallery");
  if (!gallery) return;

  gallery.innerHTML = "";
  
  if (!images || images.length === 0) {
    gallery.innerHTML = '<div class="alert info">No images found in this PDF.</div>';
    return;
  }
  
  images.forEach(img => {
    const card = document.createElement("div");
    card.className = "image-card";
    card.style = "border: 1px solid var(--border-color); border-radius: var(--border-radius); padding: 0.5rem; background: var(--surface-color);";
    
    const imgEl = document.createElement("img");
    // Fetch image from the backend via the GET endpoint
    imgEl.src = `http://127.0.0.1:8000/image/${img.image_id}`;
    imgEl.style = "max-width: 100%; height: auto; border-radius: var(--border-radius);";
    
    const meta = document.createElement("div");
    meta.style = "display: flex; justify-content: space-between; align-items: center; margin-top: 0.5rem; font-size: var(--text-xs); color: var(--text-secondary);";
    meta.innerHTML = `<span>Page ${img.page}</span>`;
    
    const explainBtn = document.createElement("button");
    explainBtn.className = "btn btn-secondary";
    explainBtn.style = "padding: 0.25rem 0.5rem; font-size: var(--text-xs);";
    explainBtn.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles"></i> Explain Image';
    
    const explanationContainer = document.createElement("div");
    explanationContainer.style = "margin-top: 0.5rem; font-size: var(--text-sm); display: none; background: var(--background-color); padding: 0.5rem; border-radius: var(--border-radius); border: 1px solid var(--border-color);";
    
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
          explanationContainer.innerHTML = '<span style="color:var(--danger-color)">Failed to analyze image.</span>';
          return;
        }
        
        const result = explainRes.data || explainRes;
        
        let componentsHtml = "";
        if (result.important_components && result.important_components.length > 0) {
            componentsHtml = `<strong>Important Components:</strong><ul>` + result.important_components.map(c => `<li>${c}</li>`).join("") + `</ul>`;
        }
        
        let relationshipsHtml = "";
        if (result.relationships && result.relationships.length > 0) {
            relationshipsHtml = `<strong>Relationships:</strong><ul>` + result.relationships.map(r => `<li>${r}</li>`).join("") + `</ul>`;
        }
        
        let takeawaysHtml = "";
        if (result.key_takeaways && result.key_takeaways.length > 0) {
            takeawaysHtml = `<strong>Key Takeaways:</strong><ul>` + result.key_takeaways.map(k => `<li>${k}</li>`).join("") + `</ul>`;
        }
        
        let applicationHtml = "";
        if (result.real_world_application) {
            applicationHtml = `<strong>Real-World Application:</strong><br/>${result.real_world_application}`;
        }
        
        explanationContainer.innerHTML = `
          <strong>${result.title}</strong><br/>
          <em>${result.summary}</em><br/>
          <p style="margin-top:0.5rem">${result.explanation}</p>
          <div style="margin-top:0.5rem; border-top: 1px solid var(--border-color); padding-top: 0.5rem;">
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

/* ==========================================================================
   Event Binding
   ========================================================================== */

/**
 * Attaches all button and input event listeners.
 */
function bindEventListeners() {
  document.getElementById("btn-settings")?.addEventListener("click", handleSettingsClick);

  // AI Chat
  document.getElementById("btn-send-chat")?.addEventListener("click", handleSendChat);
  document.getElementById("btn-clear-chat")?.addEventListener("click", handleClearChat);

  document.getElementById("chat-input")?.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleSendChat();
    }
  });

  // Summary
  document.getElementById("btn-generate-summary")?.addEventListener("click", handleGenerateSummary);
  document.getElementById("btn-export-summary")?.addEventListener("click", handleExportSummary);
  
  document.querySelectorAll(".length-toggle").forEach(btn => {
    btn.addEventListener("click", handleSummaryLengthToggle);
  });
  
  document.querySelectorAll(".copy-btn").forEach(btn => {
    btn.addEventListener("click", handleCopySummary);
  });

  // Q&A
  document.getElementById("btn-ask-question")?.addEventListener("click", handleAskQuestion);
  document.getElementById("btn-copy-qa-answer")?.addEventListener("click", async () => {
    const answerText = document.getElementById("qa-answer-text")?.innerText;
    if (answerText) {
      try {
        await navigator.clipboard.writeText(answerText);
        showToast("Answer copied to clipboard!");
      } catch (_) {
        showToast("Failed to copy answer", true);
      }
    }
  });
  document.getElementById("qa-question-input")?.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      handleAskQuestion();
    }
  });


async function handleRefreshSidebar(btnId = "btn-refresh-sidebar") {
  const btn = document.getElementById(btnId);
  const icon = btn ? btn.querySelector("i") : null;

  if (icon) icon.classList.add("spinning");

  logAction("Sidebar refresh triggered");

  try {
    await new Promise((resolve) => {
      chrome.storage.local.remove(["lastExtractedText", "lastExtractedImages"], () => {
        resolve();
      });
    });
    await renderBookmarks();
    showToast("Workspace refreshed!");
    setTimeout(() => {
      window.location.reload();
    }, 600);
  } catch (err) {
    logAction("Refresh failed", err);
  } finally {
    setTimeout(() => {
      if (icon) icon.classList.remove("spinning");
    }, 600);
  }
}

  // Bookmarks
  document.getElementById("btn-refresh-sidebar")?.addEventListener("click", () => handleRefreshSidebar("btn-refresh-sidebar"));
  document.getElementById("btn-refresh-bookmarks")?.addEventListener("click", () => handleRefreshSidebar("btn-refresh-bookmarks"));
  document.getElementById("btn-quick-bookmarks")?.addEventListener("click", handleBookmarkPage);
  document.getElementById("btn-bookmark-page")?.addEventListener("click", handleBookmarkPage);
  document.getElementById("bookmark-search-input")?.addEventListener("input", () => renderBookmarks());
  document.getElementById("bookmark-sort-select")?.addEventListener("change", () => renderBookmarks());
  document.getElementById("btn-close-bookmark-modal")?.addEventListener("click", closeBookmarkModal);
  document.getElementById("btn-cancel-bookmark-modal")?.addEventListener("click", closeBookmarkModal);
  document.getElementById("btn-save-bookmark-modal")?.addEventListener("click", handleSaveBookmarkModal);
  document.getElementById("bookmark-modal-overlay")?.addEventListener("click", (e) => {
    if (e.target.id === "bookmark-modal-overlay") closeBookmarkModal();
  });

  // Extract Text from PDF
  document.getElementById("btn-extract-pdf")?.addEventListener("click", () => {
    logAction("Extract PDF clicked");
    const btn = document.getElementById("btn-extract-pdf");
    if (btn) btn.disabled = true;
    
    const statusArea = document.getElementById("extraction-status-area");
    if (statusArea) {
      statusArea.style.display = "block";
      statusArea.style.borderColor = "var(--color-primary)";
      statusArea.style.background = "rgba(6, 182, 212, 0.1)";
      statusArea.innerHTML = "<em>Extracting text and images... please wait.</em>";
    }
    
    chrome.runtime.sendMessage({ action: "EXTRACT_PDF_TEXT" });
  });
  
  // Dummy testing listener and extraction result listener
  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.action === "FORWARD_TEST_CONNECTION") {
      logAction("TEST MESSAGE RECEIVED", { source: message.source, data: message.data });
      showAlert(`Test message from ${message.source}: ${message.data}`);
    } else if (message.action === "EXTRACTED_TEXT_RESULT") {
      const statusArea = document.getElementById("extraction-status-area");
      const btn = document.getElementById("btn-extract-pdf");
      if (btn) btn.disabled = false;
      if (statusArea) {
        if (message.success) {
          statusArea.style.display = "block";
          statusArea.style.borderColor = "var(--color-success)";
          statusArea.style.background = "rgba(34, 197, 94, 0.1)";
          statusArea.textContent = message.text;
          
          if (message.images) {
            renderExtractedImages(message.images);
          }
          
          // Trigger AI Navigator generation
          if (typeof fetchNavigator === "function") {
            fetchNavigator();
          }
        } else {
          statusArea.style.display = "block";
          statusArea.style.borderColor = "#ef4444";
          statusArea.style.background = "rgba(239, 68, 68, 0.1)";
          statusArea.textContent = "Error: " + message.error;
        }
      }
    }
  });
}

/* ==========================================================================
   Initialization
   ========================================================================== */

/**
 * Bootstraps the side panel when the DOM is ready.
 */
function initSidePanel() {
  initNavigation();
  renderSuggestedQuestions();

  renderBookmarks();
  bindEventListeners();

  // Ensure only Chat is visible on load
  navigateToSection("chat");

  logAction("Side panel initialized");
}

document.addEventListener("DOMContentLoaded", initSidePanel);
