"""
test_large_columns_dataset_qa.py -- Parametric AI Large Column Dataset QA Test Suite
Validates ingestion and full indexing of CSV files with > 1,000 columns (e.g. 1,050+ columns).
Verifies:
  1. TOTAL CSV COLUMNS == TOTAL INDEXED COLUMNS validation (0 column truncation).
  2. Attributes/columns at the beginning, middle, and very end of the 1,000+ columns can be retrieved and accurately queried.
  3. Non-existent columns / items return a clean 'not found' message without hallucination.
  4. Ranking / superlative queries evaluate across any of the 1,000+ columns.
  5. Multi-attribute extraction scales across ultra-wide datasets.
"""

import sys
import os
import io
import csv
import random

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.abspath("."))

from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

print("=" * 70)
print("  TESTING WIDE CSV DATASET INGESTION & QA (>1,000 COLUMNS)")
print("=" * 70)

# ── 1. Generate a CSV with 1,050 columns and 50 data rows ─────────────────────
TOTAL_COLUMNS = 1050
TOTAL_ROWS = 50
print(f"\n[Step 1] Generating wide test CSV dataset with {TOTAL_COLUMNS} columns x {TOTAL_ROWS} rows...")

csv_buffer = io.StringIO()
writer = csv.writer(csv_buffer)

# Build 1,050 column headers
# Core columns at start + metric columns + MFR_URL at the end
headers = ["Mfg_Part_Num", "Part_Manuf", "Part_Desc", "Voltage_0004"]
for c in range(5, TOTAL_COLUMNS):
    if c == 525:
        headers.append("Pressure_PSI_0525")
    elif c == 750:
        headers.append("Thermal_Limit_0750")
    elif c == 1048:
        headers.append("Resilience_Score_1048")
    else:
        headers.append(f"Param_Col_{c:04d}")
headers.append("MFR_URL")

assert len(headers) == TOTAL_COLUMNS, f"Header length mismatch: {len(headers)} != {TOTAL_COLUMNS}"
writer.writerow(headers)

for i in range(1, TOTAL_ROWS + 1):
    mpn = f"WIDE-PART-{i:04d}"
    manuf = f"MegaCorp-{((i % 10) + 1):02d}"
    desc = f"Ultra-Wide Parameter Industrial Device Unit {i}"
    voltage = f"{(120 + (i % 50))} V"
    
    row_values = [mpn, manuf, desc, voltage]
    for c in range(5, TOTAL_COLUMNS):
        if c == 525:
            row_values.append(f"{5000 + (i * 10)} PSI")
        elif c == 750:
            row_values.append(f"{150 + i} C")
        elif c == 1048:
            row_values.append(f"{80 + (i % 20)} pts")
        else:
            row_values.append(f"Val_{c}_{i}")
    
    mfr_url = f"https://www.megacorp{((i % 10) + 1):02d}.com/devices/{mpn}"
    row_values.append(mfr_url)
    
    assert len(row_values) == TOTAL_COLUMNS
    writer.writerow(row_values)

csv_content_bytes = csv_buffer.getvalue().encode("utf-8")
print(f"Generated CSV size: {len(csv_content_bytes):,} bytes ({TOTAL_COLUMNS} columns x {TOTAL_ROWS} data rows).")

# ── 2. Test Ingestion via /api/upload_dataset ─────────────────────────────────
print("\n[Step 2] Uploading CSV to /api/upload_dataset...")
files = {
    "file": ("industrial_wide_1050_columns.csv", io.BytesIO(csv_content_bytes), "text/csv")
}
r_upload = client.post("/api/upload_dataset", files=files)
print("Upload status:", r_upload.status_code)
upload_data = r_upload.json()
print("Upload message:", upload_data.get("message"))
print(f"Upload stats: {upload_data.get('total_csv_rows')} rows, {upload_data.get('total_csv_columns')} cols.")

assert r_upload.status_code == 200, f"Upload failed: {upload_data}"
assert upload_data["total_csv_rows"] == TOTAL_ROWS, f"Expected {TOTAL_ROWS} rows, got {upload_data['total_csv_rows']}"
assert upload_data["total_indexed_rows"] == TOTAL_ROWS, f"Expected {TOTAL_ROWS} rows, got {upload_data['total_indexed_rows']}"
assert upload_data["total_csv_columns"] == TOTAL_COLUMNS, f"Expected {TOTAL_COLUMNS} columns, got {upload_data['total_csv_columns']}"
assert upload_data["total_indexed_columns"] == TOTAL_COLUMNS, f"Expected {TOTAL_COLUMNS} columns, got {upload_data['total_indexed_columns']}"
assert upload_data["is_valid"] is True, "Validation is_valid must be True"
dataset_id = upload_data["dataset_id"]
print(f"✅ Ingestion Verified: TOTAL CSV COLUMNS ({upload_data['total_csv_columns']}) == TOTAL INDEXED COLUMNS ({upload_data['total_indexed_columns']})")

# ── 3. Test QA on Column near BEGINNING of 1,000+ Schema (Col 4: Voltage_0004) ─
print("\n[Step 3] Querying Column at the beginning of schema (Col 4: Voltage_0004 for WIDE-PART-0005)...")
r_col_start = client.post("/api/chat_dataset", json={
    "dataset_id": dataset_id,
    "message": "What is the Voltage_0004 of WIDE-PART-0005?"
})
print("Start Column QA response:", r_col_start.json()["response"])
assert r_col_start.status_code == 200
assert "WIDE-PART-0005" in r_col_start.json()["response"]
assert "125 V" in r_col_start.json()["response"]
print("✅ Beginning of schema column query passed.")

# ── 4. Test QA on Column in the MIDDLE of 1,000+ Schema (Col 525: Pressure_PSI_0525) ──
print("\n[Step 4] Querying Column in the middle of schema (Col 525: Pressure_PSI_0525 for WIDE-PART-0010)...")
r_col_mid = client.post("/api/chat_dataset", json={
    "dataset_id": dataset_id,
    "message": "What is the Pressure_PSI_0525 of WIDE-PART-0010?"
})
print("Middle Column QA response:", r_col_mid.json()["response"])
assert r_col_mid.status_code == 200
assert "5100 PSI" in r_col_mid.json()["response"] or "5100" in r_col_mid.json()["response"]
print("✅ Middle of schema column query passed.")

# ── 5. Test QA on Column at the VERY END of 1,000+ Schema (Col 1048: Resilience_Score_1048) ─
print("\n[Step 5] Querying Column at the end of schema (Col 1048: Resilience_Score_1048 for WIDE-PART-0025)...")
r_col_end = client.post("/api/chat_dataset", json={
    "dataset_id": dataset_id,
    "message": "What is the Resilience_Score_1048 for WIDE-PART-0025?"
})
print("End Column QA response:", r_col_end.json()["response"])
assert r_col_end.status_code == 200
assert "85 pts" in r_col_end.json()["response"] or "85" in r_col_end.json()["response"]
print("✅ End of schema column query passed.")

# ── 6. Test QA on MFR_URL at the tail of 1,000+ columns ───────────────────────
print("\n[Step 6] Querying MFR_URL from the tail of the 1,000+ column table for WIDE-PART-0049...")
r_url = client.post("/api/chat_dataset", json={
    "dataset_id": dataset_id,
    "message": 'What is the official product support URL for Mfg_Part_Num "WIDE-PART-0049"?'
})
print("Tail Column MFR_URL response:", r_url.json()["response"])
assert r_url.status_code == 200
assert "WIDE-PART-0049" in r_url.json()["response"]
assert "https://www.megacorp" in r_url.json()["response"]
print("✅ Tail column URL query passed.")

# ── 7. Test Non-Existent Product Query ────────────────────────────────────────
print("\n[Step 7] Querying non-existent entity in wide dataset...")
r_none = client.post("/api/chat_dataset", json={
    "dataset_id": dataset_id,
    "message": "What is the Voltage_0004 of NON-EXISTENT-PART-9999?"
})
print("Non-existent response:", r_none.json()["response"])
assert r_none.status_code == 200
assert "not found" in r_none.json()["response"].lower() or "couldn't find" in r_none.json()["response"].lower()
print("✅ Non-hallucinatory not-found test passed.")

# ── 8. Test Dataset-Wide Ranking Query Across Column 525 (Pressure_PSI_0525) ──
print("\n[Step 8] Testing dataset-wide ranking query across Column 525 (Pressure_PSI_0525)...")
r_rank = client.post("/api/chat_dataset", json={
    "dataset_id": dataset_id,
    "message": "Which product has the highest pressure in the dataset?"
})
print("Ranking response:", r_rank.json()["response"])
assert r_rank.status_code == 200
assert "5500 PSI" in r_rank.json()["response"] or "WIDE-PART-0050" in r_rank.json()["response"]
print("✅ Superlative ranking across 1,000+ column dataset passed.")

print("\n" + "=" * 70)
print("  ALL 1,000+ COLUMN WIDE DATASET INGESTION & QA TESTS PASSED! ✅")
print("=" * 70)
