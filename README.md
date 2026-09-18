# 📄 DocLens-AI — Intelligent Document Assistant

> **Transform any PDF into an interactive knowledge base with grounded AI Chat, multimodal vision analysis, and real-time document navigation.**

DocLens-AI is a high-performance Chrome Extension paired with a FastAPI backend that provides accurate, citation-backed document exploration directly in your browser.

---

## ✨ Key Features

- **💬 Grounded AI Chat**: Multi-turn conversation powered by Groq LLM with hybrid retrieval (ChromaDB vector + BM25 Okapi) and strict grounding verification to eliminate hallucinations.
- **🧭 Document Navigator**: Auto-extracts chapters, definitions, key formulas, tables, figures, code blocks, and embedded links with page jump shortcuts.
- **👁️ Multimodal Vision**: Click any chart, architecture diagram, or figure to receive instant, deep explanations using Vision AI.
- **📊 Table & Metric Intelligence**: Table-aware retrieval that deterministically calculates sums, averages, YoY growth, and maximums/minimums without math errors.
- **📑 PDF Summary Export**: Generate beautifully formatted ReportLab executive summary PDF reports directly from the extension.
- **🔖 Smart Bookmarking**: Save important pages, highlight notes, and jump directly to references across tabs.

---

## 🛠️ Architecture & Tech Stack

```
[ Browser / Chrome Extension (MV3) ]
       │  (Popup & Sidepanel UI, Content Scripts, Background Worker)
       ▼
[ FastAPI Backend API ]
  ├── Query Understanding & Rewriter (Multi-turn conversational context)
  ├── Hybrid Retrieval (Vector Search + BM25 Okapi + RRF Fusion)
  ├── Cross-Encoder Reranker & Parent Context Expansion
  ├── Specialized Pipelines (Table Analytics, Vision AI, Topic Hierarchy)
  └── Hallucination & Grounding Verification Layer (Audit before response)
```

- **Frontend**: Chrome Extension (Manifest V3), HTML5, Vanilla CSS, JavaScript.
- **Backend**: Python 3.10+, FastAPI, Uvicorn, PyMuPDF (fitz).
- **Retrieval & RAG**: ChromaDB, BM25Okapi, Cross-Encoder reranking (`ms-marco-MiniLM-L-6-v2`).
- **AI Models**: Groq Cloud LLM (`groq/compound-mini`), Vision AI (`qwen/qwen3.8-27b`, Gemini Vision).
- **PDF Generation**: ReportLab for executive document reports.

---

## 🚀 Getting Started

### 1. Backend Setup

```bash
# Navigate to the backend directory
cd backend

# Install dependencies
pip install -r ../requirements.txt

# Configure your environment variables
cp .env.example .env
# Edit .env and insert your GROQ_API_KEY and GEMINI_API_KEY

# Start the FastAPI server
python main.py
# Server runs at: http://127.0.0.1:8000
```

### 2. Chrome Extension Setup

1. Open Chrome and navigate to `chrome://extensions/`.
2. Enable **Developer mode** (toggle in the top-right corner).
3. Click **Load unpacked** and select the `DocLens-AI` root repository folder.
4. Click the **DocLens-AI** extension icon in your Chrome toolbar or open the **Side Panel** to begin.

---

## ⚙️ Environment Variables

Configure these in `backend/.env`:

| Variable | Description | Default |
| :--- | :--- | :--- |
| `GROQ_API_KEY` | Groq API key for fast inference & hybrid RAG | *Required* |
| `GROQ_MODEL` | Primary LLM model name | `groq/compound-mini` |
| `GROQ_VISION_API_KEY` | Groq Vision API key | *Optional (falls back to GROQ_API_KEY)* |
| `GROQ_VISION_MODEL` | Multimodal model for diagram analysis | `qwen/qwen3.8-27b` |
| `GEMINI_API_KEY` | Google Gemini API key for fallback vision | *Optional* |

---

## 🔒 Security & Privacy

- Documents are processed locally on your backend server.
- API keys, embeddings, and active document buffers remain strictly in your local environment.
- Grounding verification ensures answers strictly cite provided PDF text without fabricating information.

---

## 📄 License

This project is licensed under the MIT License.
