"""
dry_run_test.py -- Parametric AI Backend Dry-Run Test Suite
============================================================
Tests the full /api/process_evaluator_dataset pipeline end-to-end
WITHOUT a real Gemini API key (LLM extraction is gracefully skipped,
web scraping runs live). Validates:
  1. All 4 backend modules import cleanly
  2. Required packages are importable
  3. process_catalog_batch() runs on a 2-row mock CSV
  4. Output DataFrame has exactly 252 columns
  5. FastAPI endpoint returns HTTP 200 + valid XLSX bytes
  6. Output XLSX is parseable and has correct column count
"""

import io
import sys
import os
import traceback

# Force UTF-8 on Windows console to avoid cp1252 encode errors
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.abspath("."))

PASS = "[PASS]"
FAIL = "[FAIL]"
INFO = "[INFO]"

results = []


def check(label: str, fn):
    """Run fn(), record pass/fail, return the result value or None."""
    try:
        val = fn()
        results.append((PASS, label))
        print(f"  {PASS}  {label}")
        return val
    except Exception as exc:
        results.append((FAIL, label))
        print(f"  {FAIL}  {label}")
        print(f"         ERROR: {exc}")
        traceback.print_exc()
        return None


# =============================================================================
print("\n" + "="*65)
print("  PARAMETRIC AI -- BACKEND DRY-RUN TEST SUITE")
print("="*65)

# -- CHECK 1: Package imports --------------------------------------------------
print("\n[1/6] Package import checks")

check("import pandas",            lambda: __import__("pandas"))
check("import openpyxl",          lambda: __import__("openpyxl"))
check("import python_multipart",  lambda: __import__("multipart"))
check("import duckduckgo_search", lambda: __import__("duckduckgo_search"))
check("import beautifulsoup4",    lambda: __import__("bs4"))
check("import fastapi",           lambda: __import__("fastapi"))
check("import google-generativeai",lambda: __import__("google.generativeai"))

# -- CHECK 2: Backend module imports -------------------------------------------
print("\n[2/6] Backend module import checks")

check("from backend.search_scraper import search_product_sources",
      lambda: __import__("backend.search_scraper", fromlist=["search_product_sources"]))
check("from backend.extractor import extract_dynamic_attributes",
      lambda: __import__("backend.extractor", fromlist=["extract_dynamic_attributes"]))
check("from backend.pipeline import process_catalog_batch, build_252_headers",
      lambda: __import__("backend.pipeline", fromlist=["process_catalog_batch", "build_252_headers"]))
check("from backend.main import app (FastAPI instance)",
      lambda: __import__("backend.main", fromlist=["app"]))

# -- CHECK 3: Column schema validation -----------------------------------------
print("\n[3/6] Column schema validation")

def _check_schema():
    from backend.pipeline import build_252_headers
    headers = build_252_headers()
    assert len(headers) == 252, f"Expected 252, got {len(headers)}"
    required = [
        "MFR URL", "Ref URL 1", "Ref URL 5",
        "Mfg_Part_Num", "Part_Manuf", "Classpath",
        "INVOICE_DESC", "MOBILE_DESC", "SHORT_DESC",
        "LONG_DESC1", "LONG_DESC2", "RETAIL_DESC",
        "MARKETING_DESCRIPTION",
        "ITEM_FEATURES_1", "ITEM_FEATURES_20",
        "ATTRIBUTE_LABEL 1",  "ATTRIBUTE_VALUE 1",  "ATTRIBUTE_UOM 1",
        "ATTRIBUTE_LABEL 50", "ATTRIBUTE_VALUE 50", "ATTRIBUTE_UOM 50",
        "TEMPERATURE", "TEMPERATURE_UOM",
        "VOLTAGE", "VOLTAGE_UOM",
        "AMPERAGE", "AMPERAGE_UOM",
        "WEIGHT", "WEIGHT_UOM",
        "Product Image",
        "Alternate Image 1", "Alternate Image 4",
        "Specification Sheet",
        "Country Of Origin", "Discontinued", "Actual Image (Yes/No)",
    ]
    missing = [c for c in required if c not in headers]
    assert not missing, f"Missing required columns: {missing}"
    return len(headers)

col_count = check("build_252_headers() returns exactly 252 cols + spot-check", _check_schema)
if col_count:
    print(f"  {INFO}  Confirmed: {col_count} columns")

# -- CHECK 4: Pipeline dry run -------------------------------------------------
print("\n[4/6] Pipeline dry run -- process_catalog_batch() with 2-row mock CSV")
api_key_set = bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
print(f"  {INFO}  GEMINI_API_KEY: {'SET (LLM will run)' if api_key_set else 'NOT SET -- LLM extraction gracefully skipped, scraping still runs'}")

import pandas as pd

MOCK_CSV = (
    "Mfg_Part_Num,Part_Desc,E1_Brand,Unilog_Brand,DIB_Brand,Part_Manuf\n"
    "PDSH4816AF,Dishwasher SS,-- Unbranded --,-- No Unilog Brand --,-- No DIB Brand --,Frigidaire\n"
    "49-94-0013,Metal Cut Off Disc,-- Unbranded --,-- No Unilog Brand --,-- No DIB Brand --,Milwaukee\n"
)

df_output = None

def _run_pipeline():
    global df_output
    from backend.pipeline import process_catalog_batch
    df_in = pd.read_csv(io.StringIO(MOCK_CSV))
    print(f"  {INFO}  Input:  {len(df_in)} rows x {len(df_in.columns)} cols")
    df_out, metrics = process_catalog_batch(df_in)
    print(f"  {INFO}  Output: {df_out.shape[0]} rows x {df_out.shape[1]} cols")
    assert df_out.shape[1] == 252, f"Expected 252 cols, got {df_out.shape[1]}"
    assert df_out.shape[0] > 0,   "Output DataFrame has 0 rows"
    df_output = df_out
    return df_out

pipeline_result = check("process_catalog_batch() completes, returns 252-col DataFrame", _run_pipeline)

# -- CHECK 5: Constraint validation on output ----------------------------------
print("\n[5/6] Output constraint validation (INVOICE_DESC uppercase/length, MOBILE_DESC length)")

def _check_invoice():
    assert df_output is not None, "df_output unavailable (pipeline step failed)"
    for i, val in enumerate(df_output["INVOICE_DESC"]):
        val = str(val) if val else ""
        if val and val != "nan":
            assert val == val.upper(), f"Row {i}: INVOICE_DESC not uppercase: '{val}'"
            assert len(val) <= 40,    f"Row {i}: INVOICE_DESC exceeds 40 chars ({len(val)}): '{val}'"
    return True

def _check_mobile():
    assert df_output is not None, "df_output unavailable (pipeline step failed)"
    for i, val in enumerate(df_output["MOBILE_DESC"]):
        val = str(val) if val else ""
        if val and val != "nan":
            assert len(val) <= 80, f"Row {i}: MOBILE_DESC exceeds 80 chars ({len(val)}): '{val}'"
    return True

check("INVOICE_DESC: all values UPPERCASE and <= 40 chars", _check_invoice)
check("MOBILE_DESC: all values <= 80 chars",                _check_mobile)

# Show sample values for manual eyeballing
if df_output is not None:
    for col in ["Mfg_Part_Num", "Part_Manuf", "MFR URL", "INVOICE_DESC", "MOBILE_DESC", "SHORT_DESC", "Classpath"]:
        if col in df_output.columns:
            vals = df_output[col].tolist()
            print(f"  {INFO}  {col}: {vals}")

# -- CHECK 6: FastAPI endpoint -------------------------------------------------
print("\n[6/6] FastAPI endpoint -- POST /api/process_evaluator_dataset")

def _test_endpoint():
    from fastapi.testclient import TestClient
    from backend.main import app

    client = TestClient(app)
    csv_bytes = MOCK_CSV.encode("utf-8")

    response = client.post(
        "/api/process_evaluator_dataset",
        files={"file": ("test_sample.csv", io.BytesIO(csv_bytes), "text/csv")},
    )

    assert response.status_code == 200, (
        f"Expected HTTP 200, got {response.status_code}. Body: {response.text[:400]}"
    )

    ctype = response.headers.get("content-type", "")
    assert "spreadsheetml" in ctype, f"Wrong Content-Type: '{ctype}'"

    xlsx_bytes = response.content
    assert len(xlsx_bytes) > 500, f"Response body too small ({len(xlsx_bytes)} bytes)"

    # Parse the returned XLSX and validate
    df_xlsx = pd.read_excel(io.BytesIO(xlsx_bytes), sheet_name="Delivery Format")
    print(f"  {INFO}  XLSX parsed: {df_xlsx.shape[0]} rows x {df_xlsx.shape[1]} cols")
    assert df_xlsx.shape[1] == 252, f"XLSX has {df_xlsx.shape[1]} cols, expected 252"
    assert df_xlsx.shape[0] > 0,   "XLSX has 0 data rows"

    row0_mpn = str(df_xlsx.loc[0, "Mfg_Part_Num"]).strip()
    assert row0_mpn == "PDSH4816AF", f"Row 0 MPN mismatch: '{row0_mpn}'"

    cd = response.headers.get("content-disposition", "")
    assert "Parametric_AI_Delivery.xlsx" in cd, f"Bad Content-Disposition: '{cd}'"

    return {"status": response.status_code, "bytes": len(xlsx_bytes), "shape": df_xlsx.shape}

ep = check("POST /api/process_evaluator_dataset => HTTP 200 + valid 252-col XLSX", _test_endpoint)
if ep:
    print(f"  {INFO}  HTTP {ep['status']} | XLSX: {ep['bytes']:,} bytes | Shape: {ep['shape']}")

# =============================================================================
passed = sum(1 for r in results if r[0] == PASS)
failed = sum(1 for r in results if r[0] == FAIL)

print("\n" + "="*65)
print(f"  DRY-RUN RESULTS: {passed} PASSED / {failed} FAILED / {len(results)} TOTAL")
print("="*65)

if failed == 0:
    print("\n  ALL CHECKS PASSED -- Backend is demo-ready!\n")
    sys.exit(0)
else:
    print(f"\n  {failed} CHECK(S) FAILED -- See details above.\n")
    for status, label in results:
        if status == FAIL:
            print(f"      {FAIL}  {label}")
    sys.exit(1)
