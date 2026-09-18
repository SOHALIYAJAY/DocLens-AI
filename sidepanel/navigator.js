/**
 * AI Document Navigator Script
 * Handles generating and rendering the intelligent PDF sidebar navigation.
 */

// Global state for navigator
let navigatorData = null;
let isGeneratingNavigator = false;

/**
 * Triggered to extract and fetch the navigator data.
 */
function fetchNavigator() {
  if (isGeneratingNavigator) return;
  isGeneratingNavigator = true;
  
  const skeleton = document.getElementById("navigator-skeleton");
  const emptyState = document.getElementById("navigator-empty-state");
  const accordion = document.getElementById("navigator-accordion");
  const overview = document.getElementById("navigator-overview");
  
  if (emptyState) emptyState.style.display = "none";
  if (accordion) accordion.innerHTML = "";
  if (overview) overview.style.display = "none";
  if (skeleton) skeleton.style.display = "block";
  
  chrome.runtime.sendMessage({ action: "EXTRACT_PDF_NAVIGATOR" }, (response) => {
    isGeneratingNavigator = false;
    if (skeleton) skeleton.style.display = "none";
    
    if (chrome.runtime.lastError || !response || !response.success) {
      const errorMsg = chrome.runtime.lastError?.message || response?.error || "Unknown error";
      console.error("Navigator Error:", errorMsg);
      if (emptyState) {
        emptyState.style.display = "block";
        emptyState.innerHTML = `
          <div style="font-size: 28px; color: var(--danger-color, #ef4444); margin-bottom: 8px;">
            <i class="fa-solid fa-triangle-exclamation"></i>
          </div>
          <h3 style="font-size: 14px; font-weight: 600; color: var(--color-text); margin-bottom: 4px;">Navigator Unavailable</h3>
          <p style="font-size: 11px; color: var(--color-text-muted); line-height: 1.4; margin-bottom: 12px; word-break: break-word;">${errorMsg}</p>
          <button type="button" class="btn btn-sm btn-primary" id="btn-retry-navigator" style="display: inline-flex; align-items: center; gap: 6px; margin: 0 auto; font-size: 11px; padding: 6px 14px;">
            <i class="fa-solid fa-rotate-right"></i>
            <span>Retry</span>
          </button>
        `;
        document.getElementById("btn-retry-navigator")?.addEventListener("click", () => fetchNavigator());
      }
      return;
    }
    
    const rawData = response.data || response;
    navigatorData = (rawData && rawData.data && !rawData.sections) ? rawData.data : rawData;
    renderNavigator(navigatorData);
  });
}

// Bind navigator actions once DOM is ready
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initNavigatorListeners);
} else {
  initNavigatorListeners();
}

function initNavigatorListeners() {
  document.getElementById("btn-refresh-navigator")?.addEventListener("click", () => {
    navigatorData = null;
    fetchNavigator();
  });
  document.getElementById("btn-trigger-fetch-navigator")?.addEventListener("click", () => {
    fetchNavigator();
  });
}

function createOverviewAccordionGroup(data) {
  const container = document.createElement("div");
  container.className = "accordion-group";
  container.style.background = "rgba(15, 23, 42, 0.4)";
  container.style.border = "1px solid var(--color-border)";
  container.style.borderRadius = "var(--radius-md)";
  container.style.overflow = "hidden";
  
  const header = document.createElement("button");
  header.className = "accordion-header";
  header.style.width = "100%";
  header.style.display = "flex";
  header.style.justifyContent = "space-between";
  header.style.alignItems = "center";
  header.style.padding = "10px 12px";
  header.style.background = "transparent";
  header.style.border = "none";
  header.style.color = "var(--color-text)";
  header.style.cursor = "pointer";
  header.style.fontWeight = "600";
  header.style.fontSize = "13px";
  
  header.innerHTML = `
    <span style="display:flex; align-items:center; gap:8px;">
      <span>📑</span> 
      Overview
    </span>
    <i class="fa-solid fa-chevron-down chevron-icon" style="transition: transform 0.2s; font-size: 11px; transform: rotate(180deg);"></i>
  `;
  
  const content = document.createElement("div");
  content.className = "accordion-content";
  content.style.display = "flex"; // expanded by default
  content.style.padding = "8px";
  content.style.flexDirection = "column";
  content.style.gap = "8px";
  content.style.borderTop = "1px solid var(--color-border)";
  
  // Note: sections_found might not exist on data, but we can fall back safely
  content.innerHTML = `
      <div style="font-size: 12px; color: var(--color-text-muted); display: grid; grid-template-columns: 1fr 1fr; gap: 4px; background: rgba(30, 41, 59, 0.4); padding: 8px; border-radius: var(--radius-md);">
        <div><strong>Pages:</strong> ${data.pages}</div>
        <div><strong>Words:</strong> ${data.word_count}</div>
        <div><strong>Time:</strong> ${data.estimated_reading_time}</div>
        <div><strong>Level:</strong> ${data.estimated_difficulty}</div>
      </div>
      <div style="font-size: 11px; color: var(--color-primary); display: flex; flex-wrap: wrap; gap: 6px;">
        ${data.chapters_found > 0 ? `<span>📖 ${data.chapters_found} Chapters</span>` : ""}
        ${data.sections && data.sections.length > 0 ? `<span>📖 ${data.sections.length} Sections</span>` : ""}
        ${data.definitions_found > 0 ? `<span>⭐ ${data.definitions_found} Defs</span>` : ""}
        ${data.formulas_found > 0 ? `<span>🧮 ${data.formulas_found} Formulas</span>` : ""}
        ${data.figures_found > 0 ? `<span>📊 ${data.figures_found} Figures</span>` : ""}
        ${data.diagrams_found > 0 ? `<span>🖼 ${data.diagrams_found} Diagrams</span>` : ""}
        ${data.tables_found > 0 ? `<span>📋 ${data.tables_found} Tables</span>` : ""}
        ${data.code_blocks_found > 0 ? `<span>💻 ${data.code_blocks_found} Code</span>` : ""}
        ${data.references_found > 0 ? `<span>📚 ${data.references_found} Refs</span>` : ""}
      </div>
  `;
  
  header.addEventListener("click", () => {
    const isExpanded = content.style.display === "flex";
    content.style.display = isExpanded ? "none" : "flex";
    header.querySelector(".chevron-icon").style.transform = isExpanded ? "rotate(0deg)" : "rotate(180deg)";
  });
  
  container.appendChild(header);
  container.appendChild(content);
  return container;
}

function renderNavigator(data) {
  if (!data) return;
  
  const overview = document.getElementById("navigator-overview");
  if (overview) {
    overview.style.display = "none";
  }

  const accordion = document.getElementById("navigator-accordion");
  if (!accordion) return;
  
  accordion.innerHTML = "";
  
  const overviewGroup = createOverviewAccordionGroup(data);
  accordion.appendChild(overviewGroup);
  
  if (data.sections && data.sections.length > 0) {
    data.sections.forEach(sec => {
      const group = createAccordionGroup(sec);
      accordion.appendChild(group);
    });
  }
}

function createAccordionGroup(sectionData) {
  const container = document.createElement("div");
  container.className = "accordion-group";
  container.style.background = "rgba(15, 23, 42, 0.4)";
  container.style.border = "1px solid var(--color-border)";
  container.style.borderRadius = "var(--radius-md)";
  container.style.overflow = "hidden";
  
  const header = document.createElement("button");
  header.className = "accordion-header";
  header.style.width = "100%";
  header.style.display = "flex";
  header.style.justifyContent = "space-between";
  header.style.alignItems = "center";
  header.style.padding = "10px 12px";
  header.style.background = "transparent";
  header.style.border = "none";
  header.style.color = "var(--color-text)";
  header.style.cursor = "pointer";
  header.style.fontWeight = "600";
  header.style.fontSize = "13px";
  
  let emojiIcon = "📁";
  if (sectionData.title === "Chapters" || sectionData.title === "Sections" || sectionData.title === "Headings") emojiIcon = "📖";
  else if (sectionData.title === "Definitions") emojiIcon = "⭐";
  else if (sectionData.title === "Formulas") emojiIcon = "🧮";
  else if (sectionData.title === "Figures") emojiIcon = "📊";
  else if (sectionData.title === "Tables") emojiIcon = "📋";
  else if (sectionData.title === "Diagrams" || sectionData.title === "Images") emojiIcon = "🖼";
  else if (sectionData.title === "Code Blocks") emojiIcon = "💻";
  else if (sectionData.title === "References") emojiIcon = "📚";
  else if (sectionData.title === "Frequently Mentioned Topics") emojiIcon = "💡";
  
  header.innerHTML = `
    <span style="display:flex; align-items:center; gap:8px;">
      <span>${emojiIcon}</span> 
      ${sectionData.title}
      <span style="background: rgba(255,255,255,0.1); padding: 2px 6px; border-radius: 10px; font-size: 10px; margin-left: 6px;">${sectionData.items.length}</span>
    </span>
    <i class="fa-solid fa-chevron-down chevron-icon" style="transition: transform 0.2s; font-size: 11px;"></i>
  `;
  
  const content = document.createElement("div");
  content.className = "accordion-content";
  content.style.display = "none";
  content.style.padding = "8px";
  content.style.flexDirection = "column";
  content.style.gap = "4px";
  content.style.borderTop = "1px solid var(--color-border)";
  
  if (sectionData.summary) {
    const summaryEl = document.createElement("div");
    summaryEl.style.fontSize = "11px";
    summaryEl.style.color = "var(--color-text-muted)";
    summaryEl.style.padding = "4px 8px";
    summaryEl.style.marginBottom = "6px";
    summaryEl.style.borderLeft = "2px solid var(--color-primary)";
    summaryEl.innerText = sectionData.summary;
    content.appendChild(summaryEl);
  }
  
  sectionData.items.forEach(item => {
    const itemEl = document.createElement("button");
    itemEl.className = "navigator-item";
    itemEl.style.width = "100%";
    itemEl.style.textAlign = "left";
    itemEl.style.padding = "8px";
    itemEl.style.background = "transparent";
    itemEl.style.border = "1px solid transparent";
    itemEl.style.borderRadius = "4px";
    itemEl.style.cursor = "pointer";
    itemEl.style.display = "flex";
    itemEl.style.flexDirection = "column";
    itemEl.style.transition = "background 0.2s";
    
    // Dataset for searching
    itemEl.dataset.searchtext = `${item.title} ${item.description || ""}`.toLowerCase();
    
    itemEl.innerHTML = `
      <div style="display:flex; justify-content:space-between; align-items:center; width:100%; color:var(--color-text); font-size: 12px; font-weight: 500;">
        <span>${item.title}</span>
        <div style="display:flex; align-items:center; gap:4px;">
          <span style="font-size: 10px; color:var(--color-primary); background: rgba(6,182,212,0.1); padding: 2px 6px; border-radius: 4px;">P.${item.page}</span>
          <button type="button" class="btn-nav-open-new-tab" title="Open in new tab at Page ${item.page}" style="background:none; border:none; color:var(--color-primary, #3b82f6); cursor:pointer; padding:2px 4px; border-radius:4px; display:inline-flex; align-items:center;">
            <i class="fa-solid fa-arrow-up-right-from-square" style="font-size: 10px;"></i>
          </button>
        </div>
      </div>
      ${item.description ? `<div style="font-size: 11px; color:var(--color-text-muted); margin-top: 4px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${item.description}</div>` : ""}
    `;
    
    itemEl.addEventListener("mouseenter", () => {
      itemEl.style.background = "rgba(255, 255, 255, 0.05)";
    });
    itemEl.addEventListener("mouseleave", () => {
      itemEl.style.background = "transparent";
    });

    itemEl.querySelector(".btn-nav-open-new-tab")?.addEventListener("click", async (e) => {
      e.stopPropagation();
      const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
      if (tabs[0] && tabs[0].url) {
        let cleanUrl = tabs[0].url.split("#")[0];
        const newUrl = `${cleanUrl}#page=${item.page}`;
        chrome.tabs.create({ url: newUrl, active: true });
      }
    });
    
    itemEl.addEventListener("click", async () => {
      // Jump and highlight in current tab
      const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
      if (tabs[0]) {
        chrome.tabs.sendMessage(tabs[0].id, {
          action: "NAVIGATE_TO_PAGE",
          pageNumber: item.page,
          highlightText: item.title
        });
      }
    });
    
    content.appendChild(itemEl);
  });
  
  header.addEventListener("click", () => {
    const isExpanded = content.style.display === "flex";
    content.style.display = isExpanded ? "none" : "flex";
    header.querySelector(".chevron-icon").style.transform = isExpanded ? "rotate(0deg)" : "rotate(180deg)";
  });
  
  container.appendChild(header);
  container.appendChild(content);
  return container;
}

// Search Logic
document.getElementById("navigator-search")?.addEventListener("input", (e) => {
  const query = e.target.value.toLowerCase().trim();
  const groups = document.querySelectorAll(".accordion-group");
  
  groups.forEach(group => {
    const items = group.querySelectorAll(".navigator-item");
    let hasVisibleItems = false;
    
    items.forEach(item => {
      const match = item.dataset.searchtext.includes(query);
      item.style.display = match ? "flex" : "none";
      if (match) hasVisibleItems = true;
    });
    
    // Auto expand group if search matches, collapse if empty, but respect original state if query is empty
    const content = group.querySelector(".accordion-content");
    const chevron = group.querySelector(".chevron-icon");
    
    if (query.length > 0) {
      if (hasVisibleItems) {
        group.style.display = "block";
        content.style.display = "flex";
        chevron.style.transform = "rotate(180deg)";
      } else {
        group.style.display = "none";
      }
    } else {
      group.style.display = "block";
      content.style.display = "none";
      chevron.style.transform = "rotate(0deg)";
      items.forEach(i => i.style.display = "flex");
    }
  });
});
