<<<<<<< HEAD
# AI PDF Assistant 📄🤖

AI PDF Assistant is a powerful Chrome Extension paired with a FastAPI Python backend designed to read, summarize, analyze, and extract structure from PDF documents. It leverages advanced layout parsers (`pymupdf4llm`) and multimodal AI to assist users in navigating, bookmarking, and downloading structured document summaries.

---

## 🌟 Key Features

### 1. 📚 AI Document Navigator (Sidepanel Accordions)
When a PDF is loaded, the assistant automatically parses the document layout and generates a structured navigation sidebar with the following collapsible panels:
- **📑 Chapters & Headings**: Structured document outline.
- **⭐ Definitions**: Key terms extracted and defined.
- **🧮 Formulas**: Important equations highlighted.
- **📊 Figures & Tables**: Captions and locations of visuals.
- **🖼 Images**: Multimodal analysis card for every image.
- **💻 Code Blocks**: Highlights Courier-formatted coding snippets.
- **🔗 Document Links**: Automatically extracts **both interactive hyperlinks and plain-text URLs** using regex with clean normalization.
- **Frequently Mentioned Topics & References**.

### 2. 🖨 Premium PDF Generation & Download
Users can download a beautifully structured PDF summary sheet by clicking the download icon in the popup. Features include:
- **Document Overview Grid**: Page count, word count, difficulty level, and estimated reading time.
- **Visual Style Formatting**: Slate Blue accents, monospaced code blocks, and yellow highlight containers for equations.
- **Interactive Hyperlinks**: Clickable blue links embedded in the PDF that launch the external URL.

### 3. 🖼 Multimodal Image Analysis ("Explain Image")
Extracts images directly from the PDF and provides a quick AI explanation highlighting:
- Important Components.
- Structural Relationships.
- Key Takeaways.
- Real-World Applications.

---

## 🛠 Tech Stack

- **Extension Frontend**: HTML5, Vanilla CSS3 (Modern dark-mode glassmorphic theme), JavaScript (Chrome Extension API - Manifest V3).
- **Backend Service**: Python 3.13, FastAPI, Uvicorn.
- **PDF Extraction**: PyMuPDF (`fitz`), `pymupdf4llm` (Layout-aware Markdown parser).
- **PDF Generation**: ReportLab PDF library.

---

## 🚀 Installation & Setup

### 1. Backend Setup
1. Navigate to the `backend` directory:
   ```bash
   cd backend
   ```
2. Install the required Python packages:
   ```bash
   pip install -r requirements.txt
   # (Ensure pymupdf, pymupdf4llm, reportlab, fastapi, and uvicorn are installed)
   ```
3. Set your AI API key in the environment variables (e.g. `.env` or system variables).
4. Run the Uvicorn server:
   ```bash
   uvicorn main:app --reload
   ```
   The backend will be running on `http://127.0.0.1:8000`.

### 2. Chrome Extension Setup
1. Open Google Chrome and go to `chrome://extensions`.
2. Enable **Developer mode** (toggle in the top-right corner).
3. Click **Load unpacked** (top-left corner).
4. Select the project root folder (`AI-PDF-Assistant` directory).
5. The extension is now active! Pin it to your Chrome toolbar.

---

## 📖 How to Use

1. **Open a PDF** inside a Google Chrome tab (either a web PDF URL or a local `file:///` PDF).
2. **Click the AI PDF Assistant Extension Icon** to open the Popup.
3. Click **Extract Text & Images** to analyze the PDF.
4. Open the **📚 AI Navigator** in the sidebar to review the structured breakdown.
5. Click the **Download Icon** (top-right of the popup) to generate and download your custom **AI Navigator PDF**!

---

## 🤝 License
This project is licensed under the MIT License.
=======
# AI PDF Assistant 📄🤖

AI PDF Assistant is a powerful Chrome Extension paired with a FastAPI Python backend designed to read, summarize, analyze, and extract structure from PDF documents. It leverages advanced layout parsers (`pymupdf4llm`) and multimodal AI to assist users in navigating, bookmarking, and downloading structured document summaries.

---

## 🌟 Key Features

### 1. 📚 AI Document Navigator (Sidepanel Accordions)
When a PDF is loaded, the assistant automatically parses the document layout and generates a structured navigation sidebar with the following collapsible panels:
- **📑 Chapters & Headings**: Structured document outline.
- **⭐ Definitions**: Key terms extracted and defined.
- **🧮 Formulas**: Important equations highlighted.
- **📊 Figures & Tables**: Captions and locations of visuals.
- **🖼 Images**: Multimodal analysis card for every image.
- **💻 Code Blocks**: Highlights Courier-formatted coding snippets.
- **🔗 Document Links**: Automatically extracts **both interactive hyperlinks and plain-text URLs** using regex with clean normalization.
- **Frequently Mentioned Topics & References**.

### 2. 🖨 Premium PDF Generation & Download
Users can download a beautifully structured PDF summary sheet by clicking the download icon in the popup. Features include:
- **Document Overview Grid**: Page count, word count, difficulty level, and estimated reading time.
- **Visual Style Formatting**: Slate Blue accents, monospaced code blocks, and yellow highlight containers for equations.
- **Interactive Hyperlinks**: Clickable blue links embedded in the PDF that launch the external URL.

### 3. 🖼 Multimodal Image Analysis ("Explain Image")
Extracts images directly from the PDF and provides a quick AI explanation highlighting:
- Important Components.
- Structural Relationships.
- Key Takeaways.
- Real-World Applications.

---

## 🛠 Tech Stack

- **Extension Frontend**: HTML5, Vanilla CSS3 (Modern dark-mode glassmorphic theme), JavaScript (Chrome Extension API - Manifest V3).
- **Backend Service**: Python 3.13, FastAPI, Uvicorn.
- **PDF Extraction**: PyMuPDF (`fitz`), `pymupdf4llm` (Layout-aware Markdown parser).
- **PDF Generation**: ReportLab PDF library.

---

## 🚀 Installation & Setup

### 1. Backend Setup
1. Navigate to the `backend` directory:
   ```bash
   cd backend
   ```
2. Install the required Python packages:
   ```bash
   pip install -r requirements.txt
   # (Ensure pymupdf, pymupdf4llm, reportlab, fastapi, and uvicorn are installed)
   ```
3. Set your AI API key in the environment variables (e.g. `.env` or system variables).
4. Run the Uvicorn server:
   ```bash
   uvicorn main:app --reload
   ```
   The backend will be running on `http://127.0.0.1:8000`.

### 2. Chrome Extension Setup
1. Open Google Chrome and go to `chrome://extensions`.
2. Enable **Developer mode** (toggle in the top-right corner).
3. Click **Load unpacked** (top-left corner).
4. Select the project root folder (`AI-PDF-Assistant` directory).
5. The extension is now active! Pin it to your Chrome toolbar.

---

## 📖 How to Use

1. **Open a PDF** inside a Google Chrome tab (either a web PDF URL or a local `file:///` PDF).
2. **Click the AI PDF Assistant Extension Icon** to open the Popup.
3. Click **Extract Text & Images** to analyze the PDF.
4. Open the **📚 AI Navigator** in the sidebar to review the structured breakdown.
5. Click the **Download Icon** (top-right of the popup) to generate and download your custom **AI Navigator PDF**!

---

## 🤝 License
This project is licensed under the MIT License.
>>>>>>> 81d0d04f1a190963b4c0c4c2d55dd58e376de3a7
