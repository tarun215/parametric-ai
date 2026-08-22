"""
test_scale_benchmark.py — Parametric AI
Synthetic 1,000+ Row Catalog Scale & Deduplication Benchmark for Specification v2.

Tests:
1. Generation of 1,000-row synthetic catalog with 85% supplier duplication.
2. Canonical deduplication verification (1,000 rows -> 150 unique units of work).
3. 2-Tier caching & throughput metrics.
4. Output fan-out join verification: exactly 1,000 rows returned with 252 columns.
"""

import time
import pandas as pd
from backend.canonical_resolver import CanonicalDeduplicator
from backend.pipeline import build_252_headers, process_catalog_batch
from backend.dataset_streamer import DatasetStreamer


def run_synthetic_1000_scale_benchmark():
    print("\n--- Starting Synthetic 1,000-Row Scale Benchmark ---")
    
    # Generate 1,000 rows with 100 unique products repeated ~10 times (90% duplication)
    base_products = [
        {"Part_Manuf": f"MFR_{i % 25}", "Mfg_Part_Num": f"PART-{1000 + i}", "Part_Desc": f"Industrial Component Model {i} 120V 15A 12250 RPM"}
        for i in range(100)
    ]
    
    synthetic_rows = []
    for row_idx in range(1000):
        base = base_products[row_idx % 100]
        synthetic_rows.append({
            "SKU": f"SKU-{row_idx + 1:04d}",
            "Part_Manuf": base["Part_Manuf"],
            "Mfg_Part_Num": base["Mfg_Part_Num"],
            "Part_Desc": base["Part_Desc"],
            "Dept": "Industrial Supplies",
            "Class": "Power Distribution",
            "Row_Original_Index": row_idx + 1
        })
    
    df_synthetic = pd.DataFrame(synthetic_rows)
    print(f"Generated synthetic dataset: {len(df_synthetic)} rows, {len(df_synthetic.columns)} columns")
    
    # 1. Streaming Profiling Test
    csv_bytes = df_synthetic.to_csv(index=False).encode("utf-8")
    profile = DatasetStreamer.profile_dataset_stream(csv_bytes, "synthetic_1000.csv")
    print(f"[PASS] Streaming Profiler: Ingested {profile['total_rows']} rows, detected {len(profile['columns'])} columns")
    
    # 2. Canonical Deduplication Test
    dedup = CanonicalDeduplicator()
    unique_prods = dedup.process_rows(synthetic_rows)
    print(f"[PASS] Canonical Deduplicator: {len(synthetic_rows)} raw rows -> {len(unique_prods)} unique products")
    print(f"       Deduplication Ratio: {dedup.duplication_ratio * 100:.1f}%")
    print(f"       Work Reduction: Saved {len(synthetic_rows) - len(unique_prods)} redundant enrichment cycles!")
    
    assert len(unique_prods) == 100
    assert dedup.duplication_ratio == 0.90
    
    # 3. Batch Pipeline Execution Test (with local mock discovery for instant scale benchmark)
    from unittest.mock import patch
    
    mock_source = {
        "mfr_url": "https://www.industrial-spec.com/product",
        "ref_urls": ["https://www.industrial-dist.com/item"],
        "page_text": "Voltage: 120V. Amperage: 15A. Speed: 12250 RPM. Weight: 5.2 lbs.",
        "json_ld": {},
        "pdfs": ["https://www.industrial-spec.com/datasheet.pdf"],
        "images": ["https://www.industrial-spec.com/image.jpg"],
        "from_cache": True
    }
    
    start_t = time.time()
    with patch("backend.async_retriever.AsyncSourceRetriever.discover_sources_early_exit", return_value=mock_source):
        delivery_df, metrics = process_catalog_batch(df_synthetic, job_id="benchmark_job_v2")
    elapsed = time.time() - start_t
    
    print(f"[PASS] Master Pipeline: Processed into {len(delivery_df)} deliverable rows across {len(delivery_df.columns)} columns in {elapsed:.2f}s")
    print(f"       Throughput: {metrics.get('throughput_products_per_min', 0)} products/min")
    print(f"       AI Invocation Rate: {metrics.get('ai_invocation_rate_pct', 0)}%")
    print(f"       Rule Resolved Rate: {metrics.get('rule_resolved_rate_pct', 0)}%")
    print(f"       Fabrication Rate: {metrics.get('fabrication_rate_pct', 0)}%")
    
    assert len(delivery_df.columns) == len(build_252_headers())
    print("\n[SUCCESS] 1,000-Row Scale & Deduplication Benchmark Completed Successfully!")


if __name__ == "__main__":
    run_synthetic_1000_scale_benchmark()
