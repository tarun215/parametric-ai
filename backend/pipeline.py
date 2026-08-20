"""
pipeline.py — Parametric AI
Orchestrates the end-to-end batch enrichment pipeline.
Reads a DataFrame of MPN + manufacturer rows, scrapes the web,
calls Gemini for extraction, and returns a 252-column Unilog delivery DataFrame.
"""

import logging
import pandas as pd
from typing import List

from backend.search_scraper import search_product_sources
from backend.extractor import extract_dynamic_attributes

logger = logging.getLogger(__name__)


# ── Column schema ──────────────────────────────────────────────────────────────

def build_252_headers() -> List[str]:
    """
    Build and return the exact ordered list of Unilog 252-column delivery headers.
    Order matters — this defines column positions in the output Excel file.
    """
    headers: List[str] = [
        # ── Sourcing (6 cols) ──
        "MFR URL",
        "Ref URL 1", "Ref URL 2", "Ref URL 3", "Ref URL 4", "Ref URL 5",

        # ── Input pass-through / identity (16 cols) ──
        "PART_NUMBER",
        "Dept", "Class", "Fine",
        "SKU - MY_PART_NUMBER",
        "Mfg_Part_Num", "Part_Desc",
        "E1_Brand", "Unilog_Brand", "DIB_Brand",
        "Part_Manuf",
        "MANUFACTURER_NAME", "BRAND_NAME", "TRADE_NAME",
        "MANUFACTURER_PART_NUMBER", "ALTERNATE_PART_NUMBER",

        # ── Taxonomy (1 col) ──
        "Classpath",

        # ── 5 Standardised Descriptions (6 cols) ──
        "INVOICE_DESC",   # ≤40 chars, UPPERCASE
        "MOBILE_DESC",    # 60-80 chars
        "SHORT_DESC",
        "LONG_DESC1",
        "LONG_DESC2",
        "RETAIL_DESC",
        "MARKETING_DESCRIPTION",
    ]

    # ── 20 Feature slots (20 cols) ──
    for i in range(1, 21):
        headers.append(f"ITEM_FEATURES_{i}")

    # ── Compliance / meta (6 cols) ──
    headers.extend([
        "With",
        "Standard/Approvals",
        "Prop 65",
        "Application",
        "Includes",
        "Product Name",
    ])

    # ── 50 Attribute triplets (150 cols) ──
    for i in range(1, 51):
        headers.extend([
            f"ATTRIBUTE_LABEL {i}",
            f"ATTRIBUTE_VALUE {i}",
            f"ATTRIBUTE_UOM {i}",
        ])

    # ── Fixed Physical / Electrical quick-fill (18 cols) ──
    headers.extend([
        "TEMPERATURE",  "TEMPERATURE_UOM",
        "PRESSURE",     "PRESSURE_UOM",
        "VOLTAGE",      "VOLTAGE_UOM",
        "AMPERAGE",     "AMPERAGE_UOM",
        "WEIGHT",       "WEIGHT_UOM",
        "LENGTH",       "LENGTH_UOM",
        "WIDTH",        "WIDTH_UOM",
        "HEIGHT",       "HEIGHT_UOM",
        "VOLUME",       "VOLUME_UOM",
    ])

    # ── Digital Assets / Documents (24 cols) ──
    headers.extend([
        "Product Image",
        "Alternate Image 1", "Alternate Image 2",
        "Alternate Image 3", "Alternate Image 4",
        "SDS", "SDS_1",
        "Warranty Information",
        "Catalog",
        "Specification Sheet",
        "Instruction/Installation Manual",
        "Service Manual",
        "Owners/User Manual",
        "Line Drawing",
        "MTR",
        "RoHS",
        "Full Engineering Drawing",
        "Energy Star Guide",
        "Technical Bulletin",
        "Submittal",
        "Compatibility Chart",
        "Size Chart",
        "Product Label/Insert",
        "Video Link", "Video Link 1",
    ])

    # ── Final meta (3 cols) ──
    headers.extend([
        "Country Of Origin",
        "Discontinued",
        "Actual Image (Yes/No)",
    ])

    return headers


# ── Keyword maps for quick-fill physical columns ───────────────────────────────

_QUICK_FILL_MAP = {
    # (value_col, uom_col): [label keywords to match]
    ("VOLTAGE",      "VOLTAGE_UOM"):      ["voltage", "volt"],
    ("AMPERAGE",     "AMPERAGE_UOM"):     ["amperage", "ampere", "current", "amps"],
    ("TEMPERATURE",  "TEMPERATURE_UOM"):  ["temperature", "temp"],
    ("PRESSURE",     "PRESSURE_UOM"):     ["pressure", "psi", "bar"],
    ("WEIGHT",       "WEIGHT_UOM"):       ["weight", "mass"],
    ("LENGTH",       "LENGTH_UOM"):       ["length", "depth"],
    ("WIDTH",        "WIDTH_UOM"):        ["width"],
    ("HEIGHT",       "HEIGHT_UOM"):       ["height"],
    ("VOLUME",       "VOLUME_UOM"):       ["volume", "capacity"],
}


def _quick_fill_physical(row: dict, attributes: list) -> None:
    """
    Populate the physical/electrical quick-fill columns from extracted attributes.
    Only fills the first matching attribute per physical category. Modifies `row` in-place.
    """
    for (val_col, uom_col), keywords in _QUICK_FILL_MAP.items():
        if row.get(val_col):  # already filled (e.g. from direct attribute slot)
            continue
        for attr in attributes:
            label_lower = str(attr.get("label", "")).lower()
            if any(kw in label_lower for kw in keywords):
                row[val_col] = attr.get("value", "")
                row[uom_col] = attr.get("uom", "")
                break


# ── Row builder ────────────────────────────────────────────────────────────────

def _build_output_row(
    headers: List[str],
    input_row: pd.Series,
    sources: dict,
    extracted: dict,
) -> dict:
    """
    Combine search results and LLM extraction into a single Unilog-format row dict.
    Pass-through columns from the input row are preserved where available.
    """
    out: dict = {h: "" for h in headers}

    # ── Core identifiers ──
    mpn = str(input_row.get("Mfg_Part_Num", "")).strip()
    mfg = str(input_row.get("Part_Manuf", "")).replace("-- Unbranded --", "").strip()
    brand = extracted.get("brand_name") or mfg

    # ── Pass-through input columns that map directly to output ──
    for col in [
        "Dept", "Class", "Fine", "SKU - MY_PART_NUMBER", "PART_NUMBER",
        "E1_Brand", "Unilog_Brand", "DIB_Brand",
        "Classpath", "ALTERNATE_PART_NUMBER",
    ]:
        if col in input_row.index and pd.notna(input_row[col]) and str(input_row[col]).strip():
            out[col] = str(input_row[col]).strip()

    # ── Identity ──
    out["Mfg_Part_Num"]             = mpn
    out["MANUFACTURER_PART_NUMBER"] = mpn
    out["PART_NUMBER"]              = mpn
    out["Part_Manuf"]               = mfg
    out["MANUFACTURER_NAME"]        = mfg
    out["BRAND_NAME"]               = brand
    if not out["E1_Brand"]:
        out["E1_Brand"]             = brand

    # ── Classpath (AI-extracted, unless already passed through from input) ──
    if not out["Classpath"]:
        out["Classpath"]            = extracted.get("classpath", "")

    # ── 5 Standardised Descriptions ──
    invoice_desc    = extracted.get("invoice_desc", "")
    mobile_desc     = extracted.get("mobile_desc", "")
    short_desc      = extracted.get("short_desc", "")
    long_desc       = extracted.get("long_desc", "")
    retail_desc     = extracted.get("retail_desc", "")
    marketing_desc  = extracted.get("marketing_desc", "")

    # Fallback construction when extraction is empty
    fallback_short  = f"{brand} {mpn}".strip()
    if not short_desc:
        short_desc  = fallback_short
    if not invoice_desc:
        invoice_desc = fallback_short.upper()[:40]
    if not mobile_desc:
        mobile_desc = short_desc[:80]
    if not retail_desc:
        retail_desc = short_desc

    out["Part_Desc"]            = short_desc
    out["INVOICE_DESC"]         = invoice_desc.upper()[:40]   # hard enforce
    out["MOBILE_DESC"]          = mobile_desc[:80]             # hard enforce
    out["SHORT_DESC"]           = short_desc
    out["LONG_DESC1"]           = long_desc
    out["LONG_DESC2"]           = long_desc  # standard Unilog dual-long-desc slot
    out["RETAIL_DESC"]          = retail_desc
    out["MARKETING_DESCRIPTION"]= marketing_desc
    out["Product Name"]         = short_desc

    # ── Source URLs ──
    out["MFR URL"]              = sources.get("mfr_url", "")
    for i, url in enumerate(sources.get("ref_urls", [])[:5], start=1):
        out[f"Ref URL {i}"]     = url

    # ── Features (up to 20 slots) ──
    for i, feat in enumerate(extracted.get("features", [])[:20], start=1):
        out[f"ITEM_FEATURES_{i}"] = feat

    # ── Compliance ──
    approvals = extracted.get("approvals", [])
    out["Standard/Approvals"]   = " | ".join(approvals) if approvals else ""

    # ── 50 Attribute triplets ──
    attributes = extracted.get("attributes", [])
    for i, attr in enumerate(attributes[:50], start=1):
        out[f"ATTRIBUTE_LABEL {i}"] = attr.get("label", "")
        out[f"ATTRIBUTE_VALUE {i}"] = attr.get("value", "")
        out[f"ATTRIBUTE_UOM {i}"]   = attr.get("uom",   "")

    # ── Physical / electrical quick-fill ──
    _quick_fill_physical(out, attributes)

    # ── Digital Assets ──
    images = sources.get("images", [])
    if images:
        out["Product Image"]            = images[0]
        out["Actual Image (Yes/No)"]    = "Yes"
        for i, img_url in enumerate(images[1:5], start=1):
            out[f"Alternate Image {i}"] = img_url
    else:
        out["Actual Image (Yes/No)"]    = "No"

    pdfs = sources.get("pdfs", [])
    if pdfs:
        out["Specification Sheet"]      = pdfs[0]
    if len(pdfs) > 1:
        out["Catalog"]                  = pdfs[1]

    # ── Remaining meta ──
    out["Country Of Origin"]    = extracted.get("country_of_origin", "")
    out["Warranty Information"] = extracted.get("warranty", "")
    out["Discontinued"]         = "N"

    return out


# ── Main batch processor ───────────────────────────────────────────────────────

def process_catalog_batch(df_input: pd.DataFrame) -> pd.DataFrame:
    """
    Process every row in df_input through the full pipeline:
      1. SAFETY LIMIT — enforce hard cap of 5 rows for live demo
      2. Web search + scrape  (search_scraper)
      3. Gemini LLM extraction  (extractor)
      4. Map to 252-column Unilog delivery schema

    Args:
        df_input: DataFrame with at minimum a 'Mfg_Part_Num' column.
                  'Part_Manuf' is optional but strongly recommended.

    Returns:
        DataFrame with exactly the Unilog 252-column delivery schema.
    """
    logger.info("Pipeline starting. Processing %d row(s).", len(df_input))

    headers = build_252_headers()
    output_rows: list = []
    total = len(df_input)

    for idx, (_, row) in enumerate(df_input.iterrows(), start=1):
        mpn = str(row.get("Mfg_Part_Num", "")).strip()
        mfg = str(row.get("Part_Manuf", "")).replace("-- Unbranded --", "").strip()

        if not mpn:
            logger.warning("Row %d/%d: empty MPN — skipping.", idx, total)
            continue

        logger.info("Processing row %d/%d: MPN=%s  MFG=%s", idx, total, mpn, mfg)

        # Step 1 — Autonomous web sourcing
        try:
            sources = search_product_sources(manufacturer=mfg, mpn=mpn)
        except Exception as exc:
            logger.error("Web sourcing failed for MPN=%s: %s", mpn, exc)
            sources = {"mfr_url": "", "ref_urls": [], "page_text": "", "pdfs": [], "images": []}

        # Step 2 — Gemini attribute extraction
        try:
            extracted = extract_dynamic_attributes(
                page_text=sources["page_text"],
                mpn=mpn,
                manufacturer=mfg,
            )
        except Exception as exc:
            logger.error("LLM extraction failed for MPN=%s: %s", mpn, exc)
            extracted = {
                "brand_name": mfg, "classpath": "",
                "invoice_desc": "", "mobile_desc": "",
                "short_desc": "", "long_desc": "",
                "retail_desc": "", "marketing_desc": "",
                "features": [], "country_of_origin": "",
                "warranty": "", "approvals": [], "attributes": [],
            }

        # Step 3 — Map to 252-column output row
        out_row = _build_output_row(
            headers=headers,
            input_row=row,
            sources=sources,
            extracted=extracted,
        )
        output_rows.append(out_row)

    if not output_rows:
        logger.warning("No rows were successfully processed.")
        return pd.DataFrame(columns=headers)

    df_out = pd.DataFrame(output_rows, columns=headers)
    logger.info(
        "Pipeline complete. Output shape: %s rows x %s cols",
        df_out.shape[0], df_out.shape[1]
    )
    return df_out