/**
 * AI PDF Assistant — Storage Service
 * 
 * Handles all chrome.storage.local operations for Reading Progress.
 */

const STORAGE_PREFIX = "pdf_progress_";

/**
 * Saves reading progress for a specific PDF.
 * 
 * @param {string} pdfId - Unique identifier for the PDF (e.g., URL or hash).
 * @param {Object} data - Progress data to save.
 */
async function saveReadingProgress(pdfId, data) {
  const key = STORAGE_PREFIX + pdfId;
  
  const payload = {
    pdfId,
    title: data.title || "Unknown PDF",
    pageNumber: data.pageNumber || 1,
    scrollPosition: data.scrollPosition || 0,
    progressPercentage: data.progressPercentage || 0,
    lastRead: new Date().toISOString(),
  };

  await chrome.storage.local.set({ [key]: payload });
  return payload;
}

/**
 * Retrieves saved reading progress for a specific PDF.
 * 
 * @param {string} pdfId - Unique identifier for the PDF.
 * @returns {Object|null} The saved progress data, or null if none exists.
 */
async function getReadingProgress(pdfId) {
  const key = STORAGE_PREFIX + pdfId;
  const result = await chrome.storage.local.get([key]);
  return result[key] || null;
}

/**
 * Deletes reading progress for a specific PDF.
 * 
 * @param {string} pdfId - Unique identifier for the PDF.
 */
async function deleteReadingProgress(pdfId) {
  const key = STORAGE_PREFIX + pdfId;
  await chrome.storage.local.remove([key]);
}

/**
 * Updates existing reading progress for a specific PDF.
 * 
 * @param {string} pdfId - Unique identifier for the PDF.
 * @param {Object} updates - New progress data to merge.
 */
async function updateReadingProgress(pdfId, updates) {
  const existing = await getReadingProgress(pdfId);
  const newData = { ...existing, ...updates };
  return await saveReadingProgress(pdfId, newData);
}

/* ==========================================================================
   Bookmarks (Delegated to BookmarkService)
   ========================================================================== */

async function saveBookmark(pdfId, title, pageNumber) {
  if (typeof BookmarkService !== "undefined") {
    return await BookmarkService.addBookmark({ pdfId, title, pageNumber });
  }
  const bookmarks = await getBookmarks();
  const newBookmark = {
    id: `bm-${Date.now()}`,
    pdfId,
    title: title || "Unknown Document",
    pageNumber: pageNumber || 1,
    timestamp: new Date().toISOString()
  };
  bookmarks.push(newBookmark);
  await chrome.storage.local.set({ global_bookmarks: bookmarks });
  return newBookmark;
}

async function getBookmarks(pdfId = null) {
  if (typeof BookmarkService !== "undefined") {
    return await BookmarkService.getBookmarks(pdfId);
  }
  const result = await chrome.storage.local.get(["global_bookmarks"]);
  const all = result["global_bookmarks"] || [];
  if (!pdfId) return all;
  return all.filter(b => b.pdfId === pdfId);
}

async function updateBookmark(bookmarkId, newTitle) {
  if (typeof BookmarkService !== "undefined") {
    return await BookmarkService.updateBookmark(bookmarkId, newTitle);
  }
  throw new Error("BookmarkService unavailable");
}

async function deleteBookmark(bookmarkId) {
  if (typeof BookmarkService !== "undefined") {
    await BookmarkService.deleteBookmark(bookmarkId);
    return { deleted: true };
  }
  let bookmarks = await getBookmarks();
  bookmarks = bookmarks.filter(b => b.id !== bookmarkId);
  await chrome.storage.local.set({ global_bookmarks: bookmarks });
  return { deleted: true };
}

// Export for ES modules (if used) or keep global for importScripts
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    saveReadingProgress,
    getReadingProgress,
    deleteReadingProgress,
    updateReadingProgress,
    saveBookmark,
    getBookmarks,
    updateBookmark,
    deleteBookmark
  };
} else if (typeof window !== 'undefined') {
  window.saveReadingProgress = saveReadingProgress;
  window.getReadingProgress = getReadingProgress;
  window.deleteReadingProgress = deleteReadingProgress;
  window.updateReadingProgress = updateReadingProgress;
  window.saveBookmark = saveBookmark;
  window.getBookmarks = getBookmarks;
  window.updateBookmark = updateBookmark;
  window.deleteBookmark = deleteBookmark;
}
