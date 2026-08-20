"""
extractor.py — Parametric AI
Gemini Flash LLM extraction engine.
Extracts structured attributes, all 5 standardised descriptions, classpath,
marketing copy, and features from scraped web text.
"""

import os
import re
import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

# ── Prompt template ────────────────────────────────────────────────────────────
_EXTRACTION_PROMPT = """
You are an expert industrial product data specialist working for Unilog.
Analyse the product text below for part number: {mpn}
{manufacturer_hint}

Return ONLY a single valid JSON object — no markdown, no extra text — matching this EXACT schema:

{{
  "brand_name": "Exact manufacturer brand name (e.g. Milwaukee, Frigidaire, Bosch)",
  "classpath": "Full hierarchical category path, e.g. 'Electrical > Circuit Protection > Circuit Breakers > Miniature Circuit Breakers'",
  "invoice_desc": "PRODUCT TITLE IN UPPERCASE, MAX 40 CHARACTERS, ABBREVIATED (e.g. 'CIRCUIT BREAKER 15A 120V')",
  "mobile_desc": "Concise product description, BETWEEN 60 AND 80 CHARACTERS, sentence case",
  "short_desc": "One-sentence product title, 10-20 words, sentence case",
  "long_desc": "Detailed product description, 3-5 sentences, covering key specs and applications",
  "retail_desc": "Consumer-friendly retail description, 1-2 sentences highlighting benefits",
  "marketing_desc": "Marketing-focused copy emphasising value and differentiation, 2-3 sentences",
  "features": [
    "Key feature sentence 1",
    "Key feature sentence 2"
  ],
  "country_of_origin": "Country name or empty string",
  "warranty": "Warranty terms or empty string",
  "approvals": ["UL", "CSA"],
  "attributes": [
    {{"label": "Voltage Rating", "value": "120", "uom": "V"}},
    {{"label": "Amperage", "value": "15", "uom": "A"}}
  ]
}}

STRICT RULES:
- "invoice_desc": MUST be ALL UPPERCASE, NO longer than 40 characters. Abbreviate aggressively.
- "mobile_desc": MUST be between 60 and 80 characters total. Adjust wording to fit exactly.
- "classpath": Use 3-5 levels separated by ' > '. Be specific to the product type.
- "attributes": Use separate "label", "value", "uom" fields. Keep "value" numeric when possible. "uom" is unit abbreviation only (V, A, mm, kg, RPM, dBA, °F, PSI, etc.). Extract UP TO 50 attributes. Be exhaustive.
- "features": Extract UP TO 20 distinct feature sentences.
- If a field cannot be determined from the text, use "" or [].
- DO NOT hallucinate — only extract information present in the text.

PRODUCT TEXT:
{page_text}
""".strip()


def _call_gemini(prompt: str, api_key: str) -> str:
    """Call Gemini 1.5 Flash using google-generativeai SDK. Returns raw response text."""
    import google.generativeai as genai  # lazy import
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.5-flash")
    response = model.generate_content(
        prompt,
        generation_config={"temperature": 0.1, "max_output_tokens": 8192},
    )
    return response.text


def _parse_json_response(raw: str) -> dict:
    """Strip markdown fences and parse JSON from LLM response."""
    # Remove ```json ... ``` fences if present
    cleaned = re.sub(r"```(?:json)?", "", raw).replace("```", "").strip()

    # Find the outermost JSON object
    start = cleaned.find("{")
    end = cleaned.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError("No JSON object found in LLM response")

    return json.loads(cleaned[start:end])


def extract_dynamic_attributes(
    page_text: str,
    mpn: str,
    manufacturer: str = "",
) -> Dict[str, Any]:
    """
    Call Gemini Flash to extract structured product data from scraped text.

    Returns a dict with keys:
        brand_name, classpath,
        invoice_desc, mobile_desc, short_desc, long_desc, retail_desc, marketing_desc,
        features (list[str]), country_of_origin (str), warranty (str),
        approvals (list[str]), attributes (list of {label, value, uom})

    On failure or missing API key, returns a safe empty schema with manufacturer fallback.
    """
    empty: Dict[str, Any] = {
        "brand_name": manufacturer,
        "classpath": "",
        "invoice_desc": "",
        "mobile_desc": "",
        "short_desc": "",
        "long_desc": "",
        "retail_desc": "",
        "marketing_desc": "",
        "features": [],
        "country_of_origin": "",
        "warranty": "",
        "approvals": [],
        "attributes": [],
    }

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        logger.warning("GEMINI_API_KEY not set — skipping LLM extraction for MPN=%s", mpn)
        return empty

    if not page_text or len(page_text.strip()) < 50:
        logger.warning("Insufficient page text for MPN=%s — skipping extraction", mpn)
        return empty

    manufacturer_hint = (
        f'Manufacturer: "{manufacturer}"' if manufacturer else ""
    )
    prompt = _EXTRACTION_PROMPT.format(
        mpn=mpn,
        manufacturer_hint=manufacturer_hint,
        page_text=page_text[:6000],  # stay within Gemini token budget
    )

    try:
        raw_response = _call_gemini(prompt, api_key)
        result = _parse_json_response(raw_response)

        # Apply defaults for any missing keys
        for key, default in empty.items():
            result.setdefault(key, default)

        # Post-process invoice_desc: enforce UPPERCASE + 40-char hard limit
        if result.get("invoice_desc"):
            result["invoice_desc"] = result["invoice_desc"].upper()[:40]
        
        # Post-process mobile_desc: trim to 80 chars max if model overshot
        if result.get("mobile_desc"):
            result["mobile_desc"] = result["mobile_desc"][:80]

        # Ensure attributes are well-formed dicts
        cleaned_attrs = []
        for attr in result.get("attributes", []):
            if isinstance(attr, dict) and attr.get("label"):
                cleaned_attrs.append({
                    "label": str(attr.get("label", "")).strip(),
                    "value": str(attr.get("value", "")).strip(),
                    "uom":   str(attr.get("uom",   "")).strip(),
                })
        result["attributes"] = cleaned_attrs[:50]  # hard cap at 50

        # Ensure list fields are actually lists
        for key in ("features", "approvals"):
            if not isinstance(result[key], list):
                result[key] = []
        result["features"] = result["features"][:20]  # hard cap at 20

        logger.info(
            "Extracted %d attributes, %d features for MPN=%s",
            len(result["attributes"]), len(result["features"]), mpn
        )
        return result

    except Exception as exc:
        logger.error("Gemini extraction failed for MPN=%s: %s", mpn, exc)
        return empty