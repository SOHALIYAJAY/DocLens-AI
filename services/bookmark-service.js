/**
 * AI PDF Assistant — Bookmark Service
 * 
 * Reusable service handling CRUD operations, deduplication, filtering, search, and sorting for PDF bookmarks.
 */

class BookmarkService {
  static STORAGE_KEY = "global_bookmarks";

  /**
   * Generates a unique bookmark ID.
   * @returns {string}
   */
  static generateId() {
    return `bm-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`;
  }

  /**
   * Normalizes PDF identifier (e.g. strips hashes or extra query params).
   * @param {string} pdfId 
   * @returns {string}
   */
  static normalizePdfId(pdfId) {
    if (!pdfId) return "";
    let clean = pdfId.split("#")[0];
    return clean;
  }

  /**
   * Retrieves all saved bookmarks from chrome.storage.local.
   * @returns {Promise<Array>}
   */
  static async getAllBookmarks() {
    try {
      const result = await chrome.storage.local.get([this.STORAGE_KEY]);
      return result[this.STORAGE_KEY] || [];
    } catch (err) {
      console.error("[BookmarkService] Failed to fetch bookmarks:", err);
      return [];
    }
  }

  /**
   * Retrieves bookmarks for a specific PDF (or all if pdfId is omitted).
   * @param {string|null} [pdfId=null]
   * @returns {Promise<Array>}
   */
  static async getBookmarks(pdfId = null) {
    const all = await this.getAllBookmarks();
    if (!pdfId) return all;
    
    const cleanId = this.normalizePdfId(pdfId);
    return all.filter(b => this.normalizePdfId(b.pdfId) === cleanId);
  }

  /**
   * Adds a new bookmark with deduplication check.
   * 
   * @param {Object} params
   * @param {string} params.pdfId - PDF identifier/URL
   * @param {string} params.title - Bookmark title
   * @param {number} params.pageNumber - Page number
   * @returns {Promise<Object>} The newly created bookmark object
   */
  static async addBookmark({ pdfId, title, pageNumber }) {
    if (!pdfId) throw new Error("PDF identifier is required.");
    if (!title || !title.trim()) throw new Error("Bookmark title is required.");
    
    const pageNum = parseInt(pageNumber, 10);
    if (isNaN(pageNum) || pageNum < 1) throw new Error("Valid page number is required.");

    const cleanTitle = title.trim();
    const cleanPdfId = this.normalizePdfId(pdfId);

    const allBookmarks = await this.getAllBookmarks();

    // Prevent duplicate bookmarks for the same PDF, page, and title
    const duplicate = allBookmarks.find(b => 
      this.normalizePdfId(b.pdfId) === cleanPdfId &&
      b.pageNumber === pageNum &&
      b.title.toLowerCase() === cleanTitle.toLowerCase()
    );

    if (duplicate) {
      throw new Error(`Bookmark "${cleanTitle}" already exists for Page ${pageNum}.`);
    }

    const newBookmark = {
      id: this.generateId(),
      pdfId: cleanPdfId,
      title: cleanTitle,
      pageNumber: pageNum,
      timestamp: new Date().toISOString()
    };

    allBookmarks.push(newBookmark);
    await chrome.storage.local.set({ [this.STORAGE_KEY]: allBookmarks });
    return newBookmark;
  }

  /**
   * Updates an existing bookmark's title and page number.
   * 
   * @param {string} bookmarkId 
   * @param {string} newTitle 
   * @param {number|string|null} [newPageNumber=null]
   * @returns {Promise<Object>} Updated bookmark
   */
  static async updateBookmark(bookmarkId, newTitle, newPageNumber = null) {
    if (!bookmarkId) throw new Error("Bookmark ID is required.");
    if (!newTitle || !newTitle.trim()) throw new Error("Bookmark title cannot be empty.");

    const cleanTitle = newTitle.trim();
    const allBookmarks = await this.getAllBookmarks();
    const index = allBookmarks.findIndex(b => b.id === bookmarkId);

    if (index === -1) {
      throw new Error("Bookmark not found.");
    }

    const existing = allBookmarks[index];
    const pageNum = newPageNumber !== null && newPageNumber !== undefined ? parseInt(newPageNumber, 10) : existing.pageNumber;
    if (isNaN(pageNum) || pageNum < 1) throw new Error("Valid page number is required.");

    const duplicate = allBookmarks.find(b => 
      b.id !== bookmarkId &&
      this.normalizePdfId(b.pdfId) === this.normalizePdfId(existing.pdfId) &&
      b.pageNumber === pageNum &&
      b.title.toLowerCase() === cleanTitle.toLowerCase()
    );

    if (duplicate) {
      throw new Error(`Another bookmark titled "${cleanTitle}" already exists for Page ${pageNum}.`);
    }

    allBookmarks[index].title = cleanTitle;
    allBookmarks[index].pageNumber = pageNum;
    allBookmarks[index].updatedAt = new Date().toISOString();

    await chrome.storage.local.set({ [this.STORAGE_KEY]: allBookmarks });
    return allBookmarks[index];
  }

  /**
   * Deletes a bookmark by ID.
   * 
   * @param {string} bookmarkId 
   * @returns {Promise<boolean>} True if deleted
   */
  static async deleteBookmark(bookmarkId) {
    if (!bookmarkId) throw new Error("Bookmark ID is required.");

    const allBookmarks = await this.getAllBookmarks();
    const filtered = allBookmarks.filter(b => b.id !== bookmarkId);

    await chrome.storage.local.set({ [this.STORAGE_KEY]: filtered });
    return true;
  }

  /**
   * Searches and sorts bookmarks.
   * 
   * @param {string|null} [pdfId=null] 
   * @param {string} [query=""] 
   * @param {string} [sortBy="page-asc"] - "page-asc", "title-asc", "newest", "oldest"
   * @returns {Promise<Array>}
   */
  static async searchBookmarks(pdfId = null, query = "", sortBy = "page-asc") {
    let list = await this.getBookmarks(pdfId);

    // Search filter by title
    if (query && query.trim()) {
      const q = query.trim().toLowerCase();
      list = list.filter(b => b.title.toLowerCase().includes(q));
    }

    // Sorting
    list.sort((a, b) => {
      switch (sortBy) {
        case "title-asc":
        case "title":
          return a.title.localeCompare(b.title);
        case "newest":
          return new Date(b.timestamp) - new Date(a.timestamp);
        case "oldest":
          return new Date(a.timestamp) - new Date(b.timestamp);
        case "page-desc":
          return b.pageNumber - a.pageNumber;
        case "page-asc":
        default:
          return a.pageNumber - b.pageNumber;
      }
    });

    return list;
  }
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = BookmarkService;
} else if (typeof window !== 'undefined') {
  window.BookmarkService = BookmarkService;
} else if (typeof self !== 'undefined') {
  self.BookmarkService = BookmarkService;
}
