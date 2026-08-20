# UNIHACK 2026 - PARAMETRIC AI MASTER PLAN

## 1. Branding & Hardcode Cleanup
- **Change App Name:** Replace all instances of "ForgeSpec AI" with "Parametric AI".
- **The Hardcoded Demo:** The current UI (Graph, Chatbot, SpecLens) is hardcoded to "PDSH4816AF Frigidaire". DO NOT DELETE THIS. Instead, wrap it in a UI state called "Showcase Mode (Sample)" so it is clearly labelled as a demo of our visual provenance capabilities.

## 2. The Core Requirement: Dynamic Evaluator Batch Mode
We must build an end-to-end dynamic pipeline that accepts an unseen CSV/Excel file, scrapes the web, and outputs a 252-column Excel file.

### Backend Requirements (FastAPI)
- Create `POST /api/process_evaluator_dataset`.
- It must read an uploaded CSV/Excel containing `Mfg_Part_Num` and `Part_Manuf`.
- It must use `duckduckgo-search` to autonomously find the official manufacturer URL (blocking Amazon, eBay, Walmart).
- It must scrape the text and use Gemini 1.5/2.5 Flash to extract attributes.
- It must output a Pandas DataFrame formatted exactly to Unilog's 252-column schema (MFR URL, 5 Descriptions, 50 Attribute Triplets, etc.).

### Frontend Requirements (React)
- Create a new tab or section called "Evaluator Batch Processor".
- Provide a drag-and-drop file upload for the evaluator's test CSV.
- Provide a "Run Autonomous Pipeline" button.
- Provide a "Download Enriched 252-Column Excel" button upon completion.