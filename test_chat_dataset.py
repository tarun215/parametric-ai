import sys
import os
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.abspath("."))

from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

print("--- Testing / ---")
r = client.get("/")
print("Root status:", r.status_code, r.json())
assert r.status_code == 200

print("\n--- Testing /api/chat (Active Product) ---")
r_chat = client.post("/api/chat", json={
    "product_id": "PDSH4816AF",
    "message": "What is the voltage and amperage rating?"
})
print("Chat status:", r_chat.status_code)
print("Chat response:", r_chat.json())
assert r_chat.status_code == 200
assert "Voltage Rating" in r_chat.json()["response"] or "120" in r_chat.json()["response"]

print("\n--- Testing /api/chat_dataset (Full Dataset Scope) ---")
r_dataset = client.post("/api/chat_dataset", json={
    "message": "Compare all dishwashers in the dataset",
    "dataset_scope": "catalog"
})
print("Dataset Chat status:", r_dataset.status_code)
print("Dataset Chat model:", r_dataset.json()["model"])
print("Dataset Chat preview:", r_dataset.json()["response"][:200])
assert r_dataset.status_code == 200

print("\n--- Testing Query-First Retrieval (Specific Entity Query) ---")
r_qfirst = client.post("/api/chat_dataset", json={
    "message": "What is the voltage rating of FRIGIDAIRE PDSH4816AF?",
    "dataset_scope": "catalog"
})
print("Query-First response:", r_qfirst.json()["response"])
assert "120 V" in r_qfirst.json()["response"]
assert "Dataset Overview" not in r_qfirst.json()["response"]

print("\n--- Testing Query-First Retrieval (Non-Existent Entity Query) ---")
r_notfound = client.post("/api/chat_dataset", json={
    "message": "What is the battery rating of SAMSUNG XYZ999?",
    "dataset_scope": "catalog"
})
print("Not-found response:", r_notfound.json()["response"])
assert "couldn't find" in r_notfound.json()["response"].lower() or "not available" in r_notfound.json()["response"].lower()
assert "Dataset Overview" not in r_notfound.json()["response"]

print("\n--- Testing MFR URL Query (Official Product Support URL) ---")
r_url = client.post("/api/chat_dataset", json={
    "message": 'What is the official product support URL for Mfg_Part_Num "PDSH4816AF"?',
    "dataset_scope": "catalog"
})
print("URL response:", r_url.json()["response"])
assert "https://www.frigidaire.com" in r_url.json()["response"] or "PDSH4816AF" in r_url.json()["response"]

print("\n--- Testing Custom Uploaded Dataset with Part Number Query ---")
r_custom_part = client.post("/api/chat_dataset", json={
    "message": 'What is the official product support URL for Mfg_Part_Num "PDSH4816AF"?',
    "dataset_scope": "custom",
    "custom_dataset": [
        {"Mfg_Part_Num": "49-94-0503", "Part_Desc": "Disc", "Part_Manuf": "Milwaukee"},
        {"Mfg_Part_Num": "PDSH4816AF", "Part_Desc": "Dishwasher SS", "Part_Manuf": "Frigidaire"}
    ]
})
print("Custom dataset part query response:", r_custom_part.json()["response"])
assert "PDSH4816AF" in r_custom_part.json()["response"]

print("\nALL BACKEND CHAT & DATASET QA TESTS PASSED SUCCESSFULLY! ✅")
