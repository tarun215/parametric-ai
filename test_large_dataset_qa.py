"""
test_large_dataset_qa.py -- Parametric AI Large Dataset QA Test Suite
Validates ingestion and full indexing of CSV files with > 1,000 rows (e.g. 2,500+ rows).
Verifies:
  1. TOTAL CSV ROWS == TOTAL INDEXED ROWS validation.
  2. Products at the beginning, middle, and very end of the CSV can be retrieved and accurately queried.
  3. Non-existent items return a clean 'not found' message without hallucination.
  4. Ranking / superlative queries evaluate across all 2,500+ rows.
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
print("  TESTING LARGE CSV DATASET INGESTION & QA (>1,000 ROWS)")
print("=" * 70)

# ── 1. Generate a CSV with 2,500 rows ─────────────────────────────────────────
TOTAL_TEST_ROWS = 2500
print(f"\n[Step 1] Generating test CSV dataset with {TOTAL_TEST_ROWS} rows...")

csv_buffer = io.StringIO()
writer = csv.writer(csv_buffer)
headers = [
    "Mfg_Part_Num", "Part_Manuf", "Part_Desc", "Voltage", "Amperage", "Pressure_PSI", "MFR_URL"
]
writer.writerow(headers)

for i in range(1, TOTAL_TEST_ROWS + 1):
    mpn = f"IND-PART-{i:05d}"
    manuf = f"Manufacturer-{((i % 20) + 1):02d}"
    desc = f"Industrial Grade Hydraulic Fitting Component Model {i}"
    voltage = f"{(100 + (i % 200))} V"
    amperage = f"{(5 + (i % 50))} A"
    pressure = f"{1000 + i} PSI"
    mfr_url = f"https://www.manufacturer{((i % 20) + 1):02d}.com/products/{mpn}"
    writer.writerow([mpn, manuf, desc, voltage, amperage, pressure, mfr_url])

csv_content_bytes = csv_buffer.getvalue().encode("utf-8")
print(f"Generated CSV size: {len(csv_content_bytes):,} bytes ({TOTAL_TEST_ROWS} data rows).")

# ── 2. Test Ingestion via /api/upload_dataset ─────────────────────────────────
print("\n[Step 2] Uploading CSV to /api/upload_dataset...")
files = {
    "file": ("industrial_evaluator_2500.csv", io.BytesIO(csv_content_bytes), "text/csv")
}
r_upload = client.post("/api/upload_dataset", files=files)
print("Upload status:", r_upload.status_code)
upload_data = r_upload.json()
print("Upload response:", upload_data)

assert r_upload.status_code == 200, f"Upload failed: {upload_data}"
assert upload_data["total_csv_rows"] == TOTAL_TEST_ROWS, f"Expected {TOTAL_TEST_ROWS}, got {upload_data['total_csv_rows']}"
assert upload_data["total_indexed_rows"] == TOTAL_TEST_ROWS, f"Expected {TOTAL_TEST_ROWS}, got {upload_data['total_indexed_rows']}"
assert upload_data["is_valid"] is True, "Validation is_valid must be True"
dataset_id = upload_data["dataset_id"]
print(f"✅ Ingestion Verified: TOTAL CSV ROWS ({upload_data['total_csv_rows']}) == TOTAL INDEXED ROWS ({upload_data['total_indexed_rows']})")

# ── 3. Test QA on Product near the BEGINNING of file (Row 5) ─────────────────
print("\n[Step 3] Querying Product at the beginning of the file (Row 5: IND-PART-00005)...")
r_row5 = client.post("/api/chat_dataset", json={
    "dataset_id": dataset_id,
    "message": "What is the Voltage and MFR_URL of IND-PART-00005?"
})
print("Row 5 QA response:", r_row5.json()["response"])
assert r_row5.status_code == 200
assert "IND-PART-00005" in r_row5.json()["response"]
assert "105 V" in r_row5.json()["response"]
print("✅ Beginning of file product query passed.")

# ── 4. Test QA on Product in the MIDDLE of file (Row 1250) ───────────────────
print("\n[Step 4] Querying Product in the middle of the file (Row 1250: IND-PART-01250)...")
r_row1250 = client.post("/api/chat_dataset", json={
    "dataset_id": dataset_id,
    "message": "What is the Pressure_PSI of Mfg_Part_Num IND-PART-01250?"
})
print("Row 1250 QA response:", r_row1250.json()["response"])
assert r_row1250.status_code == 200
assert "2250 PSI" in r_row1250.json()["response"] or "2250" in r_row1250.json()["response"]
print("✅ Middle of file product query passed.")

# ── 5. Test QA on Product at the VERY END of file (Row 2499) ──────────────────
print("\n[Step 5] Querying Product at the very end of the file (Row 2499: IND-PART-02499)...")
r_end = client.post("/api/chat_dataset", json={
    "dataset_id": dataset_id,
    "message": 'What is the official product support URL for Mfg_Part_Num "IND-PART-02499"?'
})
print("End of file QA response:", r_end.json()["response"])
assert r_end.status_code == 200
assert "IND-PART-02499" in r_end.json()["response"]
assert "https://www.manufacturer" in r_end.json()["response"]
print("✅ End of file product query passed.")

# ── 6. Test Non-Existent Product Query ────────────────────────────────────────
print("\n[Step 6] Querying non-existent entity...")
r_none = client.post("/api/chat_dataset", json={
    "dataset_id": dataset_id,
    "message": "What is the voltage of GHOST-PART-99999?"
})
print("Non-existent response:", r_none.json()["response"])
assert r_none.status_code == 200
assert "not found" in r_none.json()["response"].lower() or "couldn't find" in r_none.json()["response"].lower()
print("✅ Non-hallucinatory not-found test passed.")

# ── 7. Test Ranking Query Across All 2,500 Rows ───────────────────────────────
print("\n[Step 7] Testing dataset-wide ranking query across all 2,500 rows...")
r_rank = client.post("/api/chat_dataset", json={
    "dataset_id": dataset_id,
    "message": "Which product has the highest pressure in the dataset?"
})
print("Ranking response:", r_rank.json()["response"])
assert r_rank.status_code == 200
assert "3500 PSI" in r_rank.json()["response"] or "IND-PART-02500" in r_rank.json()["response"]
print("✅ Dataset-wide ranking query passed.")

print("\n" + "=" * 70)
print("  ALL 2,500+ ROW LARGE DATASET INGESTION & QA TESTS PASSED! ✅")
print("=" * 70)
