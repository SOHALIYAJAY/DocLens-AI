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
let activeSection = "dashboard";

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

/* ==========================================================================
   Navigation
   ========================================================================== */

/**
 * Switches the visible panel section without reloading the page.
 * @param {string} sectionId - Target section identifier
 */
function navigateToSection(sectionId) {
  if (sectionId === activeSection) {
    return;
  }

  const sections = document.querySelectorAll(".panel-section");
  const navItems = document.querySelectorAll(".nav-item");

  sections.forEach((section) => {
    const isTarget = section.dataset.section === sectionId;

    section.classList.toggle("active", isTarget);
    section.hidden = !isTarget;
  });

  navItems.forEach((item) => {
    item.classList.toggle("active", item.dataset.section === sectionId);
  });

  activeSection = sectionId;
  logAction("Navigated to section", { section: sectionId });

  if (sectionId === "chat") {
    demoTypingIndicator();
  }
}

/**
 * Binds click handlers to navigation items.
 */
function initNavigation() {
  const navList = document.getElementById("nav-list");

  navList?.addEventListener("click", (event) => {
    const navButton = event.target.closest(".nav-item");

    if (!navButton) {
      return;
    }

    const sectionId = navButton.dataset.section;

    if (sectionId) {
      navigateToSection(sectionId);
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

/** Renders saved bookmarks from storage dynamically. */
function renderBookmarks() {
  const list = document.getElementById("bookmarks-list");

  if (!list) {
    return;
  }

  chrome.runtime.sendMessage({ action: "GET_BOOKMARKS" }, (response) => {
    list.innerHTML = "";
    
    if (chrome.runtime.lastError || !response || !response.success || !response.data) {
      logAction("Failed to fetch bookmarks", chrome.runtime.lastError);
      return;
    }

    const bookmarks = response.data;
    
    if (bookmarks.length === 0) {
      list.innerHTML = '<li class="list-item-card"><div class="list-item-content"><span class="list-item-title">No bookmarks yet</span></div></li>';
      return;
    }

    bookmarks.forEach((bookmark) => {
      list.appendChild(
        createListItemCard({
          iconClass: "fa-bookmark",
          iconType: "bookmark",
          title: bookmark.title,
          meta: `Page ${bookmark.pageNumber}`,
          actionLabel: `Go to bookmark: ${bookmark.title}`,
          onAction: () => {
            logAction("Bookmark opened", bookmark);
            showAlert(`Jump to Page ${bookmark.pageNumber}: "${bookmark.title}"\n(Jumping not implemented yet.)`);
          },
        })
      );
    });
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

function handleSendChat() {
  const input = document.getElementById("chat-input");
  const message = input?.value.trim();

  if (!message) {
    showAlert("Please enter a message.");
    return;
  }

  logAction("Send chat message", { message });
  showAlert(`Message sent: "${message}"\n(AI response not implemented yet.)`);
  input.value = "";
}

function handleClearChat() {
  logAction("Clear chat clicked");
  showAlert("Chat history will be cleared.\n(Not implemented yet.)");
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

function handleGenerateSummary() {
  logAction("Generate summary clicked", { length: currentSummaryLength });
  showAlert(`Generating ${currentSummaryLength} AI summary...\n(Not implemented yet.)`);
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

function handleAskQuestion() {
  const input = document.getElementById("qa-question-input");
  const question = input?.value.trim();

  if (!question) {
    showAlert("Please enter a question.");
    return;
  }

  logAction("Ask question", { question });
  showAlert(`Question submitted: "${question}"\n(AI answer not implemented yet.)`);
}


function handleAddNote() {
  logAction("Add note clicked");
  showAlert("Add a new note.\n(Not implemented yet.)");
}

function handleBookmarkPage() {
  logAction("Bookmark current page clicked");
  
  chrome.runtime.sendMessage({ action: "SAVE_BOOKMARK", payload: {} }, (response) => {
    if (chrome.runtime.lastError || !response || !response.success) {
      const errorMsg = chrome.runtime.lastError?.message || response?.error || "Unknown error";
      logAction("Failed to bookmark page", { error: errorMsg });
      showAlert("Failed to bookmark page: " + errorMsg);
    } else {
      logAction("Page bookmarked successfully");
      showAlert(`Bookmarked page ${response.data.pageNumber} successfully!`);
      // Refresh the list immediately
      renderBookmarks();
    }
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
  document.getElementById("qa-question-input")?.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      handleAskQuestion();
    }
  });


  // Notes & Bookmarks
  document.getElementById("btn-add-note")?.addEventListener("click", handleAddNote);
  document.getElementById("btn-bookmark-page")?.addEventListener("click", handleBookmarkPage);

  // Dummy testing listener
  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.action === "FORWARD_TEST_CONNECTION") {
      logAction("TEST MESSAGE RECEIVED", { source: message.source, data: message.data });
      showAlert(`Test message from ${message.source}: ${message.data}`);
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

  renderNotes();
  renderBookmarks();
  renderHistory();
  bindEventListeners();

  // Ensure only Dashboard is visible on load
  navigateToSection("dashboard");

  logAction("Side panel initialized");
}

document.addEventListener("DOMContentLoaded", initSidePanel);
