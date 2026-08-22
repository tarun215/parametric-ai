# ⚡ Parametric AI — Autonomous Industrial Product Intelligence Engine

[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-19.0-61DAFB?style=flat&logo=react&logoColor=black)](https://react.dev)
[![Vite](https://img.shields.io/badge/Vite-8.0-646CFF?style=flat&logo=vite&logoColor=white)](https://vitejs.dev)
[![Gemini 1.5 Flash](https://img.shields.io/badge/Google%20Gemini-1.5%20%2F%202.0%20Flash-4285F4?style=flat&logo=google&logoColor=white)](https://ai.google.dev)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat&logo=python&logoColor=white)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

> **Autonomous industrial product data enrichment, visual spatial provenance, truth reconciliation, and zero-truncation dataset reasoning engine for modern industrial commerce.**

---

## 📌 Overview

Industrial product catalogs are plagued by fragmented attributes, missing technical specifications, inconsistent units of measure (UOM), and hallucinated e-commerce data. **Parametric AI** solves this through an end-to-end autonomous pipeline that extracts, standardizes, verifies, and reasons over technical product data at enterprise scale.

Whether processing a single complex industrial part or ingesting ultra-wide catalogs (**2,500+ rows** and **1,000+ columns**), Parametric AI guarantees **100% data preservation (0% row/column truncation)** and delivers deterministic, query-first accuracy with visual audit trails.

---

## 🚀 Key Features

### 1. 🔍 Autonomous Web Sourcing & Multi-Source Extraction
- **Zero-Input Sourcing**: Automatically queries OEM domains via DuckDuckGo search to locate official manufacturer datasheets, manuals, and technical tables.
- **Deep Document Ingestion**: Scrapes and parses high-density technical HTML, specification matrices, and multi-page engineering PDFs.

### 2. 🧠 Gemini Flash Parametric AI Extraction
- **50-Slot Attribute Extraction**: Parses dense engineering text into structured `(Key, Value, UOM)` triplets.
- **252-Column Unilog Master Delivery Schema**: Formats raw specs into standard 252-column industrial commerce distribution sheets.
- **Hierarchical Taxonomy Classification**: Maps products into structured Department (`dept`), Class (`class`), and Fine-grained classification paths.

### 3. 🔬 SpecLens™ Visual Spatial Provenance
- **Audit-Ready Evidence**: Pinpoints the exact bounding-box coordinates $(x_0, y_0, x_1, y_1)$ on original manufacturer PDF datasheets for every extracted attribute.
- **Human-in-the-Loop Validation**: Allows engineers and catalog managers to inspect source evidence and override values in real time.

### 4. ⚖️ Truth Reconciliation & Conflict Resolution
- **Multi-Source Conflict Detection**: Automatically flags discrepancies when manufacturer datasheets and distributor catalogs provide conflicting electrical, mechanical, or thermal ratings.
- **Deterministic Priority Rules**: Resolves conflicting values using source authority hierarchies and confidence scoring.

### 5. 📏 Industrial Unit Normalization
- Converts arbitrary regional engineering units into standardized SI / Imperial equivalents (e.g., `PSI` ↔ `bar`, `HP` ↔ `kW`, `mm` ↔ `in`, `V`, `A`, `RPM`, `N·m`).
- Standardizes international regulatory and compliance standards (`UL`, `CSA`, `CE`, `NEMA`, `ANSI`, `RoHS`).

### 6. ⚡ Scalable Inverted Index & Dataset QA Engine
- **Ultra-Wide & Deep Datasets**: Ingests and indexes massive datasets exceeding **2,500+ rows** and **1,000+ columns** with strict assertion checks:
  $$\text{TOTAL CSV ROWS} == \text{TOTAL INDEXED ROWS}$$
  $$\text{TOTAL CSV COLUMNS} == \text{TOTAL INDEXED COLUMNS}$$
- **Query-First Retrieval**: Prevents generic catalog overviews when querying specific SKUs, models, or part numbers.
- **Full-Catalog Ranking**: Answers superlative queries (*"Which product has the highest pressure?"*) by evaluating across all rows and columns in sub-millisecond memory lookups.
- **Zero Hallucination Guarantee**: Returns explicit *not found* acknowledgments when items or specifications do not exist in the dataset.

---

## 🏗️ System Architecture

```mermaid
flowchart TD
    subgraph Input ["📥 Data Ingestion"]
        A[CSV / Excel Catalog<br/>>1,000 Rows & >1,000 Cols] --> B[FastAPI Chunked Ingest Engine]
        PDF[PDF Datasheets / Text] --> C[Document Parser Engine]
    end

    subgraph Processing ["⚙️ Processing & Enrichment Core"]
        B --> D[Inverted Token & Identifier Indexer]
        B --> E[Batch Autonomous Pipeline]
        E --> F[Autonomous Web Search]
        F --> G[Gemini Flash LLM Extraction]
        G --> H[50-Slot Key/Value/UOM Mapper]
        H --> I[Unit Normalizer & Standard Approvals]
        I --> J[Truth Reconciler & Conflict Engine]
        C --> K[SpecLens™ Spatial Evidence Engine]
    end

    subgraph Intelligence ["🧠 Intelligence & Distribution"]
        D --> L[Universal Dataset QA Chatbot<br/>Query-First + Ranking]
        J --> M[252-Column Unilog Delivery Excel]
        K --> N[Interactive Park UI Dashboard]
        L --> N
        M --> N
    end
```

---

## 💻 Tech Stack

- **Backend**: Python 3.10+, FastAPI, Uvicorn, Pandas, OpenPyXL, Pydantic, Requests, BeautifulSoup4
- **AI & Reasoning**: Google Gemini Flash (`gemini-2.0-flash` / `gemini-1.5-flash`), Custom Token Inverted Indexer
- **Frontend**: React 19, Vite 8, Lucide Icons, Canvas Confetti, Park UI Modern Dark-Mode Design System
- **Testing**: FastAPI TestClient, Starlette, Pytest

---

## 📂 Project Structure

```bash
parametric-ai/
├── backend/
│   ├── main.py                   # FastAPI service & API endpoints
│   ├── dataset_indexer.py        # Scalable inverted index engine (1,000+ rows/cols)
│   ├── gemini_engine.py          # Gemini Flash AI reasoning & query-first chatbot
│   ├── pipeline.py               # Autonomous batch catalog enrichment pipeline
│   ├── unit_normalizer.py        # Industrial engineering unit conversion engine
│   ├── truth_reconciler.py       # Multi-source conflict detection & resolution
│   ├── knowledge_graph.py        # Product relationship & taxonomy graph
│   ├── pdf_parser.py             # Spatial PDF bounding-box extractor
│   └── dataset.py                # Built-in industrial product catalog
├── src/
│   ├── components/
│   │   ├── BatchProcessor.jsx    # Evaluator batch CSV/Excel processing UI
│   │   ├── SpecLensViewer.jsx    # Visual spatial PDF bounding-box evidence viewer
│   │   ├── AIChatBot.jsx         # Contextual & dataset-wide conversational QA
│   │   ├── ProductCatalog.jsx    # Interactive parametric catalog view
│   │   └── AttributeTable.jsx    # Reconciled attribute table with edit overrides
│   ├── App.jsx                   # Main application orchestrator
│   └── index.css                 # Park UI design tokens and micro-animations
├── test_large_dataset_qa.py      # QA test suite for 2,500+ row datasets
├── test_large_columns_dataset_qa.py # QA test suite for 1,050+ column datasets
├── test_chat_dataset.py          # Backend dataset chat & retrieval tests
├── dry_run_test.py               # Full catalog pipeline dry-run validator
├── package.json                  # Node.js dependencies (Vite + React)
└── requirements.txt              # Python dependencies
```

---

## ⚡ Getting Started

### Prerequisites
- **Python 3.10+** installed
- **Node.js 18+** & `npm` installed
- *(Optional)* Google Gemini API Key (a deterministic zero-cost index engine runs natively without an API key)

### 1. Clone Repository & Install Dependencies

```bash
# Clone the repository
git clone https://github.com/your-username/parametric-ai.git
cd parametric-ai

# Install Python backend requirements
pip install -r requirements.txt

# Install Frontend dependencies
npm install
```

### 2. Configure Environment (Optional)

```bash
# Set Gemini API Key (optional for live LLM reasoning)
export GEMINI_API_KEY="your-gemini-api-key-here"
```

### 3. Run the Development Servers

**Start Backend (FastAPI):**
```bash
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

**Start Frontend (Vite + React):**
```bash
npm run dev
```

Visit the application in your browser:
- 🌐 **Web UI**: [http://localhost:5173](http://localhost:5173)
- 📚 **API Docs (Swagger UI)**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 📈 Specification v2: Scalability, Efficiency & Accuracy

### 1. Product-Level Unit of Work & Canonical Deduplication
- Throughput scales with **unique canonical products**, not raw row count.
- A 10,000-row catalog with 90% supplier duplication performs **~1,000 units of real enrichment work**, fanning back out to 10,000 rows during export.
- Streaming ingestion (`DatasetStreamer`) computes null rates, cardinalities, and semantic roles in a single bounded-memory pass.

### 2. 2-Tier Caching & Crash Resilience
- **Tier 1 (Source Cache)**: Keyed by `URL` and `SHA256(content)`.
- **Tier 2 (Product Cache)**: Keyed by `canonical_product_key`.
- SQLite/DB-backed `processing_checkpoints` table keyed by `(job_id, canonical_key)` guarantees instant resume-after-crash without reprocessing completed products.

### 3. Rule-Based Extraction Before AI
- **Tier 1**: Structured JSON-LD / Schema.org property extraction.
- **Tier 2**: Deterministic HTML table (`<table>`, `<dl>`) and regex pattern rules (`Voltage: 120V`, `Speed: 12250 RPM`).
- **Tier 3 (AI Residual)**: Gemini Flash LLM invoked strictly for residual ambiguous fields.

### 4. 0% Fabrication Verbatim Invariant & Review Queue
- Every AI-extracted field is required to return a `verbatim_span`.
- Post-extraction validator verifies that the verbatim span is present in the source text; ungrounded fields are discarded with confidence = 0.
- Checksums validate UPC-A, EAN-13, and GTIN-14 barcodes (Modulo-10).
- Flagged items (low confidence, conflicts, failed sanity checks) surface in the interactive **Human-in-the-Loop Review Queue**.

---

## 🧪 Testing & Validation Suites

Parametric AI includes automated verification suites covering large-scale ingestion, zero-truncation assertions, and Specification v2 benchmarks:

```bash
# 1. Test Specification v2 Master Test Suite (All 10 Verification Areas)
python -m backend.tests.test_v2_spec

# 2. Test Synthetic Scale & Deduplication Benchmark (1,000+ rows)
python -m backend.tests.test_scale_benchmark

# 3. Test 1,000+ Row Dataset Ingestion & QA (2,500 data rows)
python test_large_dataset_qa.py

# 4. Test 1,000+ Column Wide Dataset Ingestion & QA (1,050 columns)
python test_large_columns_dataset_qa.py
```

---

## 📡 Key API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/` | Service health, active product counts & v2 specification metadata |
| `POST` | `/api/process_evaluator_dataset` | Evaluator batch pipeline generating downloadable 252-column Unilog Excel deliverable |
| `POST` | `/api/process_evaluator_dataset_json` | Evaluator batch pipeline returning enriched JSON and Specification v2 observability metrics |
| `GET` | `/api/jobs/{job_id}/metrics` | Real-time observability: queue depth, throughput, AI invocation %, cache hit %, dedup ratio |
| `GET` | `/api/jobs/{job_id}/review` | Human-in-the-loop review queue for flagged products requiring verification |
| `POST` | `/api/jobs/{job_id}/review/action` | Apply human review decision (ACCEPT, CORRECT, REJECT) with live cache write-back |
| `POST` | `/api/profile_dataset_stream` | Streaming single-pass dataset profiler for arbitrarily large CSV/Excel files |
| `POST` | `/api/chat_dataset` | Dataset-wide query-first QA across all indexed rows and columns |
| `POST` | `/api/test_api_key` | Validate Google Gemini Flash API key connectivity |

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.
