"""
rule_extractor.py — Parametric AI
Specification v2 Efficiency: Rule-Based Extraction Before AI.

1. JSON-LD / schema.org / OpenGraph extraction — extracts structured catalog specs directly.
2. Deterministic pattern & HTML spec table extraction — regex key-value extraction,
   bullet specs ("Voltage: 120V"), and tabular dimensions without AI invocation.
3. Tags each extracted attribute with its source tier: 'JSON_LD' or 'RULE_PATTERN'.
"""

import re
import json
import logging
from typing import Dict, List, Any, Optional, Tuple

from bs4 import BeautifulSoup
from backend.unit_normalizer import UnitNormalizer

logger = logging.getLogger(__name__)

# Standard spec regex patterns commonly found in industrial datasheets & spec sheets
SPEC_PATTERNS = [
    # Voltage: "Voltage: 120V AC" or "Rated Voltage: 240 Volts"
    (r"(?:operating\s+|rated\s+|supply\s+)?voltage(?:\s+rating)?[:\s\-]+([0-9\.\-/]+)\s*([a-zA-Z]+)?", "Voltage Rating", "V"),
    # Amperage: "Amperage: 15A" or "Current: 20 Amps"
    (r"(?:rated\s+|current\s+|operating\s+)?amperage(?:\s+rating)?[:\s\-]+([0-9\.\-/]+)\s*([a-zA-Z]+)?", "Amperage Rating", "A"),
    # Wattage / Power: "Power: 1500W"
    (r"(?:rated\s+|power\s+)?wattage[:\s\-]+([0-9\.\-/]+)\s*([a-zA-Z]+)?", "Wattage", "W"),
    # Sound: "Sound Level: 47 dBA" or "Noise: 52 dB"
    (r"(?:sound\s+level|noise\s+level|quiet\s+operation)[:\s\-]+([0-9\.\-/]+)\s*(dba|db)", "Sound Level", "dBA"),
    # Energy: "Annual Energy: 240 kWh"
    (r"(?:annual\s+energy(?:\s+consumption)?|energy\s+consumption)[:\s\-]+([0-9\.\-/]+)\s*(kwh|kw-hr)", "Annual Energy Consumption", "kWh"),
    # Speed: "Speed: 12250 RPM"
    (r"(?:max\s+|rated\s+)?(?:speed|rpm)[:\s\-]+([0-9,]+)\s*(rpm)", "Maximum Speed", "RPM"),
    # Pressure: "Max Pressure: 150 PSI"
    (r"(?:max\s+|operating\s+)?pressure[:\s\-]+([0-9\.\-/]+)\s*(psi|bar|kpa)", "Operating Pressure", "PSI"),
    # Temperature: "Operating Temp: -40 to 120 °F"
    (r"(?:operating\s+|temperature\s+range|temp)[:\s\-]+([0-9\.\-/°\s]+)\s*(°f|°c|f|c)", "Operating Temperature", "°F"),
    # Weight: "Product Weight: 5.2 lbs"
    (r"(?:item\s+|product\s+|net\s+)?weight[:\s\-]+([0-9\.\-/]+)\s*(lbs|lb|kg|g|oz)", "Weight", "lbs"),
    # Dimensions: "Dimensions: 33-7/16 in H x 23-7/8 in W x 22-5/8 in D"
    (r"(?:dimensions|size|overall\s+dimensions)[:\s\-]+([0-9\.\-/\s\"'xXhHwWdD]+(?:in|inch|mm|cm|\"|'))", "Overall Dimensions", "in"),
    # Length: "Length: 50-1/4 in"
    (r"(?:overall\s+|cut\s+)?length[:\s\-]+([0-9\.\-/]+)\s*(in|inch|mm|cm|ft|\"|')", "Length", "in"),
    # Width: "Width: 23-7/8 in"
    (r"(?:overall\s+)?width[:\s\-]+([0-9\.\-/]+)\s*(in|inch|mm|cm|\"|')", "Width", "in"),
    # Height: "Height: 33-7/16 in"
    (r"(?:overall\s+)?height[:\s\-]+([0-9\.\-/]+)\s*(in|inch|mm|cm|\"|')", "Height", "in"),
    # Depth: "Depth: 22-5/8 in"
    (r"(?:overall\s+|product\s+)?depth[:\s\-]+([0-9\.\-/]+)\s*(in|inch|mm|cm|\"|')", "Depth", "in"),
    # Diameter: "Diameter: 5 in"
    (r"(?:disc\s+|blade\s+|outer\s+)?diameter[:\s\-]+([0-9\.\-/]+)\s*(in|inch|mm|cm|\"|')", "Diameter", "in"),
    # Arbor Size: "Arbor: 7/8 in"
    (r"(?:arbor\s+size|arbor|bore)[:\s\-]+([0-9\.\-/]+)\s*(in|inch|mm|\"|')", "Arbor Size", "in"),
    # Thickness: "Thickness: .045 in"
    (r"(?:blade\s+|disc\s+)?thickness[:\s\-]+([0-9\.\-/]+)\s*(in|inch|mm|\"|')", "Thickness", "in"),
    # Material: "Material: Aluminum Oxide"
    (r"(?:blade\s+|construction\s+|disc\s+)?material[:\s\-]+([a-zA-Z\s\-]+?)(?=[,\.;\n]|$)", "Material", ""),
    # Color / Finish: "Finish: Stainless Steel"
    (r"(?:color|finish)[:\s\-]+([a-zA-Z\s\-]+?)(?=[,\.;\n]|$)", "Color / Finish", ""),
    # Country of origin
    (r"(?:country\s+of\s+origin|made\s+in)[:\s\-]+([a-zA-Z\s]+?)(?=[,\.;\n]|$)", "Country of Origin", ""),
    # Warranty
    (r"(?:warranty|limited\s+warranty)[:\s\-]+([0-9a-zA-Z\s\-]+?)(?=[,\.;\n]|$)", "Warranty", ""),

    # Standalone token patterns (e.g. "120V 15A 47dBA 12250 RPM")
    (r"\b([0-9]+(?:\.[0-9]+)?)\s*(?:V|VAC|VDC|Volts?)\b", "Voltage Rating", "V"),
    (r"\b([0-9]+(?:\.[0-9]+)?)\s*(?:A|Amps?|Amperes?)\b", "Amperage Rating", "A"),
    (r"\b([0-9]+(?:\.[0-9]+)?)\s*(?:dBA|dB)\b", "Sound Level", "dBA"),
    (r"\b([0-9,]+)\s*(?:RPM|rpm)\b", "Maximum Speed", "RPM"),
    (r"\b([0-9]+(?:\.[0-9]+)?)\s*(?:PSI|psi|bar)\b", "Operating Pressure", "PSI"),
]


class RuleBasedExtractor:
    """
    Tier-1 and Tier-2 rule-based extractor executing before AI fallback.
    """

    @classmethod
    def extract_from_json_ld(cls, json_ld: Dict[str, Any], mpn: str = "") -> Dict[str, Any]:
        """
        Parses Schema.org / JSON-LD structured Product metadata.
        Returns standardized descriptions, brand, identifiers, and property values.
        """
        if not json_ld:
            return {}

        results: Dict[str, Any] = {
            "attributes": [],
            "features": [],
            "approvals": [],
            "tier": "JSON_LD",
        }

        # Navigate nested @graph or single Product object
        nodes = []
        if isinstance(json_ld, list):
            nodes.extend(json_ld)
        elif isinstance(json_ld, dict):
            if "@graph" in json_ld and isinstance(json_ld["@graph"], list):
                nodes.extend(json_ld["@graph"])
            else:
                nodes.append(json_ld)

        product_node = None
        for n in nodes:
            if isinstance(n, dict) and n.get("@type") in ("Product", "IndividualProduct", "ProductModel"):
                product_node = n
                break
        if not product_node and nodes:
            product_node = nodes[0]

        if not product_node or not isinstance(product_node, dict):
            return {}

        # Brand extraction
        brand_val = product_node.get("brand")
        if isinstance(brand_val, dict):
            results["brand_name"] = brand_val.get("name", "")
        elif isinstance(brand_val, str):
            results["brand_name"] = brand_val

        # Product Title & Descriptions
        name = product_node.get("name", "")
        desc = product_node.get("description", "")
        if name:
            results["short_desc"] = name
            results["invoice_desc"] = re.sub(r"[^A-Z0-9\s]", "", name.upper())[:40].strip()
            results["mobile_desc"] = name[:80].strip()
        if desc:
            results["long_desc"] = desc
            results["retail_desc"] = desc[:150]
            results["marketing_desc"] = desc

        # Category / Classpath
        cat = product_node.get("category")
        if cat:
            results["classpath"] = str(cat).replace("/", " > ")

        # Identifiers (GTIN, MPN, SKU)
        for id_key in ("mpn", "sku", "gtin13", "gtin12", "gtin8", "gtin"):
            if product_node.get(id_key):
                results[id_key] = str(product_node[id_key]).strip()

        # AdditionalProperty key-values
        add_props = product_node.get("additionalProperty") or product_node.get("properties") or []
        if isinstance(add_props, list):
            for p in add_props:
                if isinstance(p, dict):
                    prop_name = str(p.get("name") or p.get("propertyID") or "").strip()
                    prop_val = str(p.get("value") or "").strip()
                    prop_uom = str(p.get("unitCode") or p.get("unitText") or "").strip()
                    if prop_name and prop_val:
                        norm = UnitNormalizer.normalize_attribute(prop_name, prop_val, prop_uom)
                        results["attributes"].append({
                            "label": prop_name,
                            "value": prop_val,
                            "uom": prop_uom or norm.get("normalized_uom", ""),
                            "norm_val": norm.get("normalized_value", prop_val),
                            "norm_uom": norm.get("normalized_uom", ""),
                            "confidence": 0.99,
                            "status": "VERIFIED",
                            "source_tier": "JSON_LD",
                            "evidence": f'JSON-LD property "{prop_name}": "{prop_val}"'
                        })

        return results

    @classmethod
    def extract_from_patterns_and_tables(
        cls,
        page_text: str,
        html_raw: Optional[str] = None,
        mpn: str = "",
        brand: str = ""
    ) -> Dict[str, Any]:
        """
        Deterministic regex & HTML table spec extractor.
        Extracts labeled key-value spec pairs, bullet features, and physical attributes.
        """
        results: Dict[str, Any] = {
            "attributes": [],
            "features": [],
            "approvals": [],
            "tier": "RULE_PATTERN",
        }
        seen_labels = set()

        # 1. HTML <table> and <dl> parsing if HTML provided
        if html_raw:
            try:
                soup = BeautifulSoup(html_raw, "html.parser")
                # Parse all spec tables
                for table in soup.find_all("table"):
                    for row in table.find_all("tr"):
                        cells = row.find_all(["th", "td"])
                        if len(cells) == 2:
                            lbl = cells[0].get_text(strip=True)
                            val = cells[1].get_text(strip=True)
                            if lbl and val and len(lbl) < 40 and len(val) < 80:
                                norm = UnitNormalizer.normalize_attribute(lbl, val, "")
                                if lbl.lower() not in seen_labels:
                                    seen_labels.add(lbl.lower())
                                    results["attributes"].append({
                                        "label": lbl,
                                        "value": val,
                                        "uom": norm.get("normalized_uom", ""),
                                        "norm_val": norm.get("normalized_value", val),
                                        "norm_uom": norm.get("normalized_uom", ""),
                                        "confidence": 0.96,
                                        "status": "VERIFIED",
                                        "source_tier": "RULE_TABLE",
                                        "evidence": f'HTML Spec Table: {lbl} -> {val}'
                                    })
                # Parse definition lists
                for dl in soup.find_all("dl"):
                    dts = dl.find_all("dt")
                    dds = dl.find_all("dd")
                    for dt, dd in zip(dts, dds):
                        lbl = dt.get_text(strip=True)
                        val = dd.get_text(strip=True)
                        if lbl and val and len(lbl) < 40 and len(val) < 80 and lbl.lower() not in seen_labels:
                            seen_labels.add(lbl.lower())
                            norm = UnitNormalizer.normalize_attribute(lbl, val, "")
                            results["attributes"].append({
                                "label": lbl,
                                "value": val,
                                "uom": norm.get("normalized_uom", ""),
                                "norm_val": norm.get("normalized_value", val),
                                "norm_uom": norm.get("normalized_uom", ""),
                                "confidence": 0.95,
                                "status": "VERIFIED",
                                "source_tier": "RULE_DL",
                                "evidence": f'HTML Spec Definition: {lbl} -> {val}'
                            })
            except Exception as e:
                logger.debug("HTML table extraction error: %s", e)

        # 2. Regex Pattern Matching across raw/scraped page text
        text_clean = page_text or ""
        for pattern, label, default_uom in SPEC_PATTERNS:
            if label.lower() in seen_labels:
                continue
            m = re.search(pattern, text_clean, re.IGNORECASE)
            if m:
                val = m.group(1).strip()
                uom = (m.group(2) if len(m.groups()) >= 2 and m.group(2) else default_uom).strip()
                if val:
                    seen_labels.add(label.lower())
                    norm = UnitNormalizer.normalize_attribute(label, val, uom)
                    results["attributes"].append({
                        "label": label,
                        "value": val,
                        "uom": uom or norm.get("normalized_uom", ""),
                        "norm_val": norm.get("normalized_value", val),
                        "norm_uom": norm.get("normalized_uom", ""),
                        "confidence": 0.95,
                        "status": "VERIFIED",
                        "source_tier": "RULE_PATTERN",
                        "evidence": f'Verbatim Pattern Match: "{m.group(0).strip()}"'
                    })

        # 3. Extract standard safety / regulatory approvals
        for approval in ["UL Listed", "cUL Listed", "CSA Certified", "NSF Certified", "ENERGY STAR", "ASSE 1006", "ISO 9001", "RoHS", "CE"]:
            if re.search(r"\b" + re.escape(approval) + r"\b", text_clean, re.IGNORECASE):
                results["approvals"].append(approval)

        return results
