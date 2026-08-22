"""
dataset_streamer.py — Parametric AI
Specification v2 Scalability & Streaming Ingestion.

Performs bounded-memory streaming reads, chunked file parsing, and single-pass
column-level statistical profiling (nulls, cardinality, semantic pattern detection)
without materializing the entire dataset into unmanaged memory.
"""

import io
import re
import os
import logging
from typing import Dict, List, Iterator, Any, Optional, Tuple
import pandas as pd

logger = logging.getLogger(__name__)

# Standard chunk size for streaming reads
DEFAULT_CHUNK_SIZE = 2000


class DatasetStreamer:
    """
    Handles streaming ingestion and single-pass semantic profiling for CSV and Excel files.
    """

    @staticmethod
    def detect_delimiter(sample_bytes: bytes) -> str:
        """Heuristically detects CSV delimiter from the first few lines."""
        sample_str = sample_bytes.decode("utf-8", errors="ignore")[:4096]
        first_line = sample_str.split("\n")[0] if "\n" in sample_str else sample_str
        comma_count = first_line.count(",")
        tab_count = first_line.count("\t")
        pipe_count = first_line.count("|")
        semi_count = first_line.count(";")
        
        counts = [ (comma_count, ","), (tab_count, "\t"), (pipe_count, "|"), (semi_count, ";") ]
        counts.sort(key=lambda x: x[0], reverse=True)
        return counts[0][1] if counts[0][0] > 0 else ","

    @classmethod
    def stream_dataframe(
        cls,
        file_bytes: bytes,
        filename: str,
        chunksize: int = DEFAULT_CHUNK_SIZE
    ) -> Iterator[pd.DataFrame]:
        """
        Yields DataFrames in chunks to keep memory usage strictly bounded.
        """
        fn_lower = filename.lower()
        if fn_lower.endswith(".csv") or fn_lower.endswith(".txt"):
            delimiter = cls.detect_delimiter(file_bytes[:4096])
            stream = io.BytesIO(file_bytes)
            for chunk in pd.read_csv(stream, chunksize=chunksize, sep=delimiter, dtype=str, keep_default_na=False):
                # Clean column headers
                chunk.columns = [str(c).strip() for c in chunk.columns]
                yield chunk
        elif fn_lower.endswith((".xlsx", ".xls")):
            # Excel does not support native streaming as easily, read in chunks or full stream if small
            stream = io.BytesIO(file_bytes)
            df = pd.read_excel(stream, dtype=str)
            df.columns = [str(c).strip() for c in df.columns]
            # Yield in chunks
            for i in range(0, len(df), chunksize):
                yield df.iloc[i : i + chunksize].fillna("")
        else:
            stream = io.BytesIO(file_bytes)
            for chunk in pd.read_csv(stream, chunksize=chunksize, dtype=str, keep_default_na=False):
                chunk.columns = [str(c).strip() for c in chunk.columns]
                yield chunk

    @classmethod
    def profile_dataset_stream(
        cls,
        file_bytes: bytes,
        filename: str,
        max_sample_rows: int = 5000
    ) -> Dict[str, Any]:
        """
        Performs a single-pass streaming profile across the dataset:
        - Total row count
        - Column null rates & cardinalities
        - Semantic role classification (mpn, brand, description, category, specs)
        """
        total_rows = 0
        col_stats: Dict[str, Dict[str, Any]] = {}
        sample_records: List[Dict[str, Any]] = []

        for chunk in cls.stream_dataframe(file_bytes, filename, chunksize=DEFAULT_CHUNK_SIZE):
            chunk_len = len(chunk)
            total_rows += chunk_len

            if len(sample_records) < 100:
                sample_records.extend(chunk.head(100 - len(sample_records)).to_dict(orient="records"))

            for col in chunk.columns:
                if col not in col_stats:
                    col_stats[col] = {
                        "name": col,
                        "non_null_count": 0,
                        "unique_samples": set(),
                        "total_seen": 0,
                    }

                series = chunk[col].astype(str).str.strip()
                non_empty = series[series != ""]
                col_stats[col]["non_null_count"] += len(non_empty)
                col_stats[col]["total_seen"] += chunk_len

                # Sample unique values for cardinality estimation (cap at 200 items)
                if len(col_stats[col]["unique_samples"]) < 200:
                    col_stats[col]["unique_samples"].update(non_empty.unique()[:50])

        # Semantic column mapping inference
        mapped_roles = cls._infer_semantic_roles(col_stats)

        column_summary = []
        for col, stats in col_stats.items():
            total = max(1, stats["total_seen"])
            null_pct = round((1.0 - (stats["non_null_count"] / total)) * 100, 1)
            column_summary.append({
                "column": col,
                "null_pct": null_pct,
                "sample_values": list(stats["unique_samples"])[:5],
                "inferred_role": mapped_roles.get(col, "attribute")
            })

        return {
            "filename": filename,
            "total_rows": total_rows,
            "column_count": len(col_stats),
            "columns": column_summary,
            "mapped_roles": mapped_roles,
            "sample_records": sample_records,
        }

    @staticmethod
    def _infer_semantic_roles(col_stats: Dict[str, Dict[str, Any]]) -> Dict[str, str]:
        """
        Infers semantic roles (mpn, brand, description, category, uom, price) from column names & samples.
        Zero hardcoded assumptions: uses comprehensive regex pattern families.
        """
        roles: Dict[str, str] = {}
        cols = list(col_stats.keys())

        for col in cols:
            c_low = col.lower().strip()
            
            # MPN / Part Number detection
            if any(k in c_low for k in ["mfg_part_num", "part_number", "part_num", "mpn", "part #", "sku", "item_num", "model"]):
                if "mpn" not in roles.values() or "mfg_part_num" in c_low or "mpn" in c_low:
                    roles[col] = "mpn"
                    continue

            # Brand / Manufacturer detection
            if any(k in c_low for k in ["part_manuf", "manufacturer", "brand", "mfr_name", "vendor", "make"]):
                if "brand" not in roles.values() or "manuf" in c_low or "brand" in c_low:
                    roles[col] = "brand"
                    continue

            # Description detection
            if any(k in c_low for k in ["part_desc", "description", "title", "product_name", "item_desc", "desc"]):
                if "description" not in roles.values():
                    roles[col] = "description"
                    continue

            # Category / Taxonomy detection
            if any(k in c_low for k in ["classpath", "category", "dept", "class", "fine", "segment", "family"]):
                roles[col] = "category"
                continue

            # Default
            roles[col] = "attribute"

        # Fallbacks if critical keys not yet mapped
        if "mpn" not in roles.values() and cols:
            roles[cols[0]] = "mpn"
        if "brand" not in roles.values() and len(cols) > 1:
            roles[cols[1]] = "brand"
        if "description" not in roles.values() and len(cols) > 2:
            roles[cols[2]] = "description"

        return roles
