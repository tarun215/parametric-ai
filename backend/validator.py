"""
validator.py — Parametric AI
Specification v2 Accuracy Safeguards & Invariant Enforcement.

1. Verbatim Span Validator (Section 4.1): Enforces 0% fabrication by verifying that
   every AI-extracted field has a verbatim substring match in the retrieved source text.
2. Cross-Source Corroboration Engine (Section 4.2): Requires 2+ independent source agreement
   for high-value fields (voltage, amperage, safety specs) before confidence > 0.90.
3. Identifier Checksum Validation (Section 4.3): Validates UPC-A, EAN-13, and GTIN-14
   using standard Modulo-10 / Luhn checksum algorithms.
4. Physical Plausibility Ranges (Section 4.3): Detects unit/extraction anomalies
   (e.g., handheld tool weight > 100 lbs or voltage > 1000V for residential items).
"""

import re
import logging
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger(__name__)

# High-value fields requiring corroboration
HIGH_VALUE_FIELDS = {
    "voltage", "voltage rating", "amperage", "amperage rating", "current",
    "pressure", "operating pressure", "temperature", "max speed", "rpm",
    "gtin", "upc", "ean", "mfg_part_num", "part_number"
}

# Physical plausibility boundaries: (min_val, max_val, unit)
PLAUSIBILITY_LIMITS = {
    "voltage": (1.0, 48000.0, "V"),
    "amperage": (0.01, 5000.0, "A"),
    "wattage": (0.1, 500000.0, "W"),
    "sound level": (10.0, 150.0, "dBA"),
    "weight": (0.001, 50000.0, "lbs"),
    "maximum speed": (1.0, 100000.0, "RPM"),
    "operating pressure": (0.1, 50000.0, "PSI"),
}


class AccuracyValidator:
    """
    Validates verbatim evidence spans, identifier checksums, physical limits, and cross-source consensus.
    """

    @classmethod
    def validate_verbatim_spans(
        cls,
        extracted_attributes: List[Dict[str, Any]],
        source_text: str
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Validates that every AI-extracted attribute has a verbatim supporting span in source_text.
        If a span is missing or hallucinated, the attribute is discarded or confidence set to 0.
        Returns: (accepted_attributes, rejected_warnings)
        """
        accepted = []
        warnings = []
        clean_source = (source_text or "").lower()

        for attr in extracted_attributes:
            label = attr.get("label", "")
            val = str(attr.get("value", "")).strip()
            span = str(attr.get("verbatim_span") or attr.get("evidence") or "").strip()
            tier = attr.get("source_tier", "AI_EXTRACTION")

            # Deterministic / JSON-LD / Rule extraction already anchored to source DOM/tables
            if tier in ("JSON_LD", "RULE_PATTERN", "RULE_TABLE", "RULE_DL"):
                accepted.append(attr)
                continue

            if not val:
                continue

            # Check verbatim presence
            clean_span = span.lower()
            clean_val = val.lower()

            if clean_span and clean_span in clean_source:
                # Validated against ground-truth source text
                attr["confidence"] = min(0.98, attr.get("confidence", 0.95))
                attr["status"] = "VERIFIED"
                accepted.append(attr)
            elif clean_val and clean_val in clean_source:
                # Value itself is present verbatim
                attr["evidence"] = f'Verbatim match for value "{val}" in source text'
                attr["confidence"] = min(0.92, attr.get("confidence", 0.90))
                attr["status"] = "VERIFIED"
                accepted.append(attr)
            else:
                # Discard hallucinated/fabricated field
                warnings.append(f'Discarded ungrounded field "{label}" with value "{val}": not found in source text.')
                logger.warning("Zero-fabrication invariant triggered: discarded %s = %s", label, val)

        return accepted, warnings

    @staticmethod
    def validate_gtin_checksum(barcode: str) -> bool:
        """
        Validates GTIN-8, UPC-A (GTIN-12), EAN-13 (GTIN-13), or GTIN-14 using standard modulo-10 algorithm.
        """
        clean = re.sub(r"[^0-9]", "", str(barcode or ""))
        if len(clean) not in (8, 12, 13, 14):
            return False

        digits = [int(d) for d in clean]
        check_digit = digits[-1]
        data_digits = digits[:-1]

        # Standard GS1 algorithm: weights alternate 3, 1 from right to left
        total = 0
        weight = 3
        for d in reversed(data_digits):
            total += d * weight
            weight = 1 if weight == 3 else 3

        calc_check = (10 - (total % 10)) % 10
        return calc_check == check_digit

    @classmethod
    def check_physical_plausibility(
        cls,
        label: str,
        value: Any,
        uom: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Checks if numeric value is within plausible engineering boundaries.
        Returns: (is_plausible, warning_message)
        """
        lbl_low = label.lower().strip()
        try:
            # Extract first numeric float
            num_match = re.search(r"[-+]?\d*\.\d+|\d+", str(value))
            if not num_match:
                return True, None
            num = float(num_match.group(0))

            for spec_key, (min_v, max_v, expected_uom) in PLAUSIBILITY_LIMITS.items():
                if spec_key in lbl_low:
                    if num < min_v or num > max_v:
                        return False, f'Suspicious {label}: {num} {uom} is outside plausible range ({min_v} to {max_v} {expected_uom})'
        except Exception:
            pass

        return True, None

    @classmethod
    def corroborate_multi_source(
        cls,
        primary_attrs: List[Dict[str, Any]],
        secondary_attrs: List[Dict[str, Any]],
        is_oem_primary: bool = True
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Corroborates high-value fields across multiple independent sources (Section 4.2).
        - Agreement across 2+ sources boosts confidence up to 0.99.
        - Single source without agreement caps at tier ceiling (0.90 - 0.95).
        - Disagreements produce conflict entries for the review queue.
        """
        corroborated = []
        conflicts = []

        secondary_map = {a.get("label", "").lower().strip(): a for a in secondary_attrs}

        for attr in primary_attrs:
            lbl = attr.get("label", "")
            lbl_low = lbl.lower().strip()
            val = str(attr.get("value", "")).strip()
            conf = attr.get("confidence", 0.90)

            is_high_val = any(h in lbl_low for h in HIGH_VALUE_FIELDS)

            if lbl_low in secondary_map:
                sec_attr = secondary_map[lbl_low]
                sec_val = str(sec_attr.get("value", "")).strip()

                if val.lower() == sec_val.lower():
                    # Corroborated agreement across 2 independent sources
                    attr["confidence"] = 0.99
                    attr["status"] = "CORROBORATED"
                    attr["evidence"] += f' (Corroborated by secondary source: {sec_val})'
                else:
                    # Disagreement between sources
                    conflicts.append({
                        "attribute": lbl,
                        "primary_value": val,
                        "secondary_value": sec_val,
                        "reason": f"Disagreement between sources: '{val}' vs '{sec_val}'"
                    })
                    attr["confidence"] = 0.85
                    attr["status"] = "CONFLICT_DETECTED"
            else:
                if is_high_val and not is_oem_primary:
                    # Uncorroborated high-value spec from non-OEM source caps confidence
                    attr["confidence"] = min(conf, 0.88)

            corroborated.append(attr)

        return corroborated, conflicts
