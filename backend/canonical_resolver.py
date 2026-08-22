"""
canonical_resolver.py — Parametric AI
Specification v2 Scalability: Unit of work is product, not row.

Structures product identity, generates canonical keys, deduplicates input datasets
prior to enrichment, and performs fan-out joins back to raw input rows at export.
"""

import re
import hashlib
import logging
from typing import Dict, List, Tuple, Any, Optional

logger = logging.getLogger(__name__)


def clean_brand_slug(brand_name: Optional[str], mpn: Optional[str] = None) -> str:
    """
    Normalizes a brand/manufacturer name into a clean, canonical slug.
    Example: 'Freud Inc. (2435)' -> 'freud', '3M Company' -> '3m'
    """
    raw_mfg = str(brand_name or "").strip()
    # Strip common boilerplate placeholders
    for placeholder in ["-- Unbranded --", "-- No Unilog Brand --", "-- No DIB Brand --", "nan", "null", "none"]:
        if raw_mfg.lower() == placeholder.lower():
            raw_mfg = ""
            break

    # Strip parenthetical IDs, legal entity suffixes
    clean = re.sub(r"\(.*?\)", "", raw_mfg).lower()
    clean = re.sub(r"\b(inc|llc|corp|corporation|company|co|gmbh|ltd|limited|holdings|usa|international)\b", "", clean).strip()
    slug = re.sub(r"[^a-z0-9]", "", clean)

    # Check for brand prefixes embedded in MPN like "3M-1234" or "MILW-5421"
    if mpn and len(slug) < 2:
        mpn_clean = str(mpn).strip().lower()
        if "-" in mpn_clean:
            prefix = mpn_clean.split("-")[0]
            if prefix in ("3m", "dewalt", "milw", "bosch", "bostitch", "stanley", "klein"):
                return prefix

    return slug if len(slug) >= 2 else "generic-industrial"


def clean_mpn_key(mpn: Optional[str]) -> str:
    """
    Normalizes a Manufacturer Part Number into a canonical comparison string.
    Strips non-alphanumeric noise while preserving core model sequences.
    """
    if not mpn:
        return ""
    raw = str(mpn).strip().upper()
    # Normalize by stripping all whitespace and punctuation noise for exact canonical equality
    norm = re.sub(r"[^A-Z0-9]", "", raw)
    return norm


def generate_canonical_key(brand: Optional[str], mpn: Optional[str], fallback_desc: str = "") -> str:
    """
    Generates a deterministic SHA256-based canonical product key.
    Ensures identical products with minor whitespace/casing differences map to the same key.
    """
    b_slug = clean_brand_slug(brand, mpn)
    m_key = clean_mpn_key(mpn)
    
    if not m_key and fallback_desc:
        desc_norm = re.sub(r"\s+", " ", fallback_desc.strip().lower())
        seed = f"{b_slug}::desc::{desc_norm}"
    else:
        seed = f"{b_slug}::{m_key}"
        
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:24]


class CanonicalDeduplicator:
    """
    Deduplicates raw catalog rows into unique canonical product work units.
    Maintains index mappings so enriched products can be joined back to all raw rows.
    """

    def __init__(self):
        self.canonical_map: Dict[str, Dict[str, Any]] = {}
        self.row_to_key_map: List[str] = []
        self.key_to_row_indices: Dict[str, List[int]] = {}
        self.total_input_rows: int = 0

    def process_rows(
        self,
        rows: List[Dict[str, Any]],
        brand_col: str = "Part_Manuf",
        mpn_col: str = "Mfg_Part_Num",
        desc_col: str = "Part_Desc"
    ) -> List[Dict[str, Any]]:
        """
        Takes raw input rows, registers mappings, and returns the deduplicated unique products.
        """
        self.total_input_rows = len(rows)
        self.canonical_map.clear()
        self.row_to_key_map.clear()
        self.key_to_row_indices.clear()

        for idx, row in enumerate(rows):
            brand_val = row.get(brand_col) or row.get("MANUFACTURER_NAME") or row.get("brand") or ""
            mpn_val = row.get(mpn_col) or row.get("PART_NUMBER") or row.get("sku") or ""
            desc_val = row.get(desc_col) or row.get("short_desc") or row.get("description") or ""

            canon_key = generate_canonical_key(brand_val, mpn_val, str(desc_val))
            self.row_to_key_map.append(canon_key)

            if canon_key not in self.key_to_row_indices:
                self.key_to_row_indices[canon_key] = []
                self.canonical_map[canon_key] = {
                    "canonical_key": canon_key,
                    "brand": str(brand_val).strip(),
                    "mpn": str(mpn_val).strip(),
                    "part_desc": str(desc_val).strip(),
                    "sample_raw_row": row,
                    "occurrence_count": 0,
                    "brand_slug": clean_brand_slug(brand_val, mpn_val),
                }

            self.key_to_row_indices[canon_key].append(idx)
            self.canonical_map[canon_key]["occurrence_count"] += 1

        unique_products = list(self.canonical_map.values())
        logger.info(
            "Deduplication complete: %d raw rows -> %d unique canonical products (Duplication: %.1f%%)",
            self.total_input_rows,
            len(unique_products),
            self.duplication_ratio * 100
        )
        return unique_products

    @property
    def unique_count(self) -> int:
        return len(self.canonical_map)

    @property
    def duplication_ratio(self) -> float:
        if self.total_input_rows == 0:
            return 0.0
        return max(0.0, 1.0 - (self.unique_count / self.total_input_rows))

    def fan_out_results(
        self,
        raw_rows: List[Dict[str, Any]],
        enriched_product_map: Dict[str, Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Joins enriched canonical product attributes back onto every raw input row.
        Preserves original row ordering, input pass-through columns, and adds enriched fields.
        """
        output_rows = []
        for idx, raw_row in enumerate(raw_rows):
            canon_key = self.row_to_key_map[idx]
            enriched_data = enriched_product_map.get(canon_key, {})

            combined_row = dict(raw_row)

            for k, v in enriched_data.items():
                if k not in combined_row or combined_row[k] is None or str(combined_row[k]).strip() == "":
                    combined_row[k] = v
                elif k.startswith("ATTRIBUTE_") or k.startswith("ITEM_FEATURES_") or k in (
                    "MFR URL", "Ref URL 1", "Ref URL 2", "Ref URL 3", "Ref URL 4", "Ref URL 5",
                    "INVOICE_DESC", "MOBILE_DESC", "SHORT_DESC", "LONG_DESC1", "LONG_DESC2",
                    "RETAIL_DESC", "MARKETING_DESCRIPTION", "Classpath", "Standard/Approvals",
                    "With", "Prop 65", "Application", "Includes", "Product Name"
                ):
                    combined_row[k] = v

            output_rows.append(combined_row)

        return output_rows
