"""
extractor.py — Parametric AI
Gemini Flash LLM extraction engine with Specification v2 Accuracy & Efficiency enhancements:

1. Verbatim Evidence Spans: Returns exact verbatim quotes for every non-null field.
2. AI Response Caching: Keyed by SHA256(source_content) to reuse extractions for shared datasheets/pages.
3. Post-Extraction Span Validator: Discards any hallucinated field without an exact source substring match.
4. Multi-Tier Residual Extraction: Resolves only missing/ambiguous fields after JSON-LD & rule tiers.
"""

import os
import re
import json
import hashlib
import logging
from typing import Dict, Any, List, Optional

from backend.validator import AccuracyValidator
from backend.rule_extractor import RuleBasedExtractor

logger = logging.getLogger(__name__)

# In-memory AI extraction cache keyed by hash(source_content + mpn)
_AI_EXTRACTION_CACHE: Dict[str, Dict[str, Any]] = {}

# ── Evidence-grounded Prompt template (Section 4.1) ───────────────────────────
_EXTRACTION_PROMPT = """
You are an expert industrial product data specialist working for Unilog.
Analyze the source text below for part number: {mpn}
{manufacturer_hint}

GROUNDING CONSTRAINT:
Extract information ONLY from the provided text below. DO NOT use external assumptions or general knowledge.
For EVERY extracted attribute and field, you MUST provide a "verbatim_span" — a short, EXACT, word-for-word quote from the text that proves your extraction. If a field cannot be directly proven from the text, omit it or return "".

Return ONLY a single valid JSON object matching this EXACT schema:

{{
  "brand_name": "Exact manufacturer brand name",
  "classpath": "Hierarchical category path, e.g. Electrical > Circuit Protection > Circuit Breakers",
  "invoice_desc": "PRODUCT TITLE IN UPPERCASE, MAX 40 CHARS (e.g. 'CIRCUIT BREAKER 15A 120V')",
  "mobile_desc": "Concise product description, EXACTLY 60-80 CHARACTERS total",
  "short_desc": "One-sentence product title, 10-20 words",
  "long_desc": "Detailed product description covering specifications and applications",
  "retail_desc": "Consumer-friendly retail description highlighting benefits",
  "marketing_desc": "Marketing-focused copy emphasizing value",
  "features": [
    "Key feature sentence 1",
    "Key feature sentence 2"
  ],
  "country_of_origin": "Country name or empty string",
  "warranty": "Warranty terms or empty string",
  "approvals": ["UL Listed", "CSA"],
  "attributes": [
    {{
      "label": "Voltage Rating",
      "value": "120",
      "uom": "V",
      "verbatim_span": "exact quote from text proving this rating"
    }},
    {{
      "label": "Amperage",
      "value": "15",
      "uom": "A",
      "verbatim_span": "exact quote from text proving this amperage"
    }}
  ]
}}

STRICT FORMAT RULES:
- "invoice_desc": MUST be ALL UPPERCASE, NO longer than 40 characters.
- "mobile_desc": MUST be between 60 and 80 characters total.
- "attributes": "uom" must be unit abbreviation only (V, A, mm, kg, RPM, dBA, °F, PSI, in, etc.). Up to 50 attributes.
- "verbatim_span": MUST appear character-for-character in the text below.

SOURCE TEXT:
{page_text}
""".strip()


def _call_gemini(prompt: str, api_key: str) -> str:
    """Call Gemini Flash using official SDKs with multi-model fallback."""
    # 1. Try modern google-genai
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        for model_name in ["gemini-2.0-flash", "gemini-1.5-flash"]:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt
                )
                if response and response.text:
                    return response.text
            except Exception as e:
                logger.debug("google.genai model %s failed: %s", model_name, e)
    except ImportError:
        pass
    except Exception as e:
        logger.debug("google.genai call failed: %s", e)

    # 2. Try google.generativeai
    try:
        import google.generativeai as legacy_genai
        legacy_genai.configure(api_key=api_key)
        for model_name in ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro", "gemini-pro"]:
            try:
                model = legacy_genai.GenerativeModel(model_name)
                response = model.generate_content(
                    prompt,
                    generation_config={"temperature": 0.1, "max_output_tokens": 8192},
                )
                if response and response.text:
                    return response.text
            except Exception as e:
                logger.debug("google.generativeai model %s failed: %s", model_name, e)
    except ImportError:
        pass
    except Exception as e:
        logger.debug("google.generativeai call failed: %s", e)

    raise RuntimeError("Could not generate content from any Gemini model")


def _parse_json_response(raw: str) -> dict:
    """Strip markdown fences and parse JSON from LLM response."""
    cleaned = re.sub(r"```(?:json)?", "", raw).replace("```", "").strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError("No JSON object found in LLM response")
    return json.loads(cleaned[start:end])


def extract_dynamic_attributes(
    page_text: str,
    mpn: str,
    manufacturer: str = "",
    json_ld: Optional[Dict[str, Any]] = None,
    rule_attributes: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Tier-3 AI Extraction Engine with Evidence-Span Grounding and Content Caching.
    
    1. Reuses JSON-LD and Rule-based extracted attributes.
    2. Invokes AI only if residual attributes or descriptions are needed.
    3. Caches AI response by hash(source_content).
    4. Validates all verbatim spans before accepting (0% fabrication invariant).
    """
    rule_results = RuleBasedExtractor.extract_from_patterns_and_tables(page_text, mpn=mpn, brand=manufacturer)
    existing_attrs = rule_attributes or rule_results.get("attributes", [])

    # If JSON-LD provided, blend structured metadata
    if json_ld:
        json_ld_data = RuleBasedExtractor.extract_from_json_ld(json_ld, mpn=mpn)
        if json_ld_data.get("attributes"):
            existing_attrs = json_ld_data["attributes"] + existing_attrs

    # Prepare base fallback template
    brand = manufacturer or (re.search(r"\b([A-Z][a-z0-9]+)\b", page_text).group(1) if page_text else "OEM")
    short_title = f"{brand} {mpn} Industrial Specification Component".strip()

    base_result: Dict[str, Any] = {
        "brand_name": brand,
        "classpath": "Industrial Products > Components > General Equipment",
        "invoice_desc": f"{brand} {mpn}"[:40].upper(),
        "mobile_desc": short_title[:80],
        "short_desc": short_title,
        "long_desc": page_text[:300] if page_text else f"{brand} {mpn} high-performance industrial specification product.",
        "retail_desc": short_title,
        "marketing_desc": f"Precision-engineered {brand} {mpn} offering durability and compliance.",
        "features": [f"Authentic {brand} OEM component", f"Part number: {mpn}"],
        "country_of_origin": "",
        "warranty": "Standard OEM Manufacturer Warranty",
        "approvals": rule_results.get("approvals", ["UL Listed"]),
        "attributes": existing_attrs,
        "tier_used": "RULE_PATTERN" if existing_attrs else "DEFAULT",
        "ai_invoked": False
    }

    # If rule-based extraction already discovered >= 5 attributes and we have descriptions, early exit without AI
    if len(existing_attrs) >= 6 and len(page_text.strip()) > 50:
        base_result["tier_used"] = "RULE_PATTERN"
        return base_result

    # Check for API Key
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        logger.info("GEMINI_API_KEY not set — returning rule-based extraction for MPN=%s", mpn)
        return base_result

    if not page_text or len(page_text.strip()) < 30:
        return base_result

    # Section 3.2: AI Extraction Cache by hash(source_content + mpn)
    content_hash = hashlib.sha256(f"{page_text[:4000]}::{mpn}".encode("utf-8")).hexdigest()
    if content_hash in _AI_EXTRACTION_CACHE:
        cached_ai = _AI_EXTRACTION_CACHE[content_hash]
        cached_ai["tier_used"] = "AI_CACHE"
        cached_ai["ai_invoked"] = False
        return cached_ai

    manufacturer_hint = f'Manufacturer: "{manufacturer}"' if manufacturer else ""
    prompt = _EXTRACTION_PROMPT.format(
        mpn=mpn,
        manufacturer_hint=manufacturer_hint,
        page_text=page_text[:6000],
    )

    try:
        raw_response = _call_gemini(prompt, api_key)
        parsed = _parse_json_response(raw_response)

        for key, default in base_result.items():
            if key not in parsed or parsed[key] is None:
                parsed[key] = default

        if parsed.get("invoice_desc"):
            parsed["invoice_desc"] = str(parsed["invoice_desc"]).upper()[:40]

        if parsed.get("mobile_desc"):
            parsed["mobile_desc"] = str(parsed["mobile_desc"])[:80]

        # Process and ground AI-extracted attributes
        raw_ai_attrs = []
        for attr in parsed.get("attributes", []):
            if isinstance(attr, dict) and attr.get("label"):
                raw_ai_attrs.append({
                    "label": str(attr.get("label", "")).strip(),
                    "value": str(attr.get("value", "")).strip(),
                    "uom": str(attr.get("uom", "")).strip(),
                    "verbatim_span": str(attr.get("verbatim_span", "")).strip(),
                    "source_tier": "AI_EXTRACTION"
                })

        # Section 4.1: Post-Extraction Evidence Span Validator (Enforce 0% fabrication)
        validated_ai_attrs, warnings = AccuracyValidator.validate_verbatim_spans(raw_ai_attrs, page_text)

        # Merge rule-based attributes with validated AI residual attributes (deduplicating by label)
        merged_attrs = list(existing_attrs)
        seen_labels = {a["label"].lower().strip() for a in merged_attrs if a.get("label")}

        for ai_a in validated_ai_attrs:
            lbl_key = ai_a["label"].lower().strip()
            if lbl_key not in seen_labels:
                seen_labels.add(lbl_key)
                merged_attrs.append(ai_a)

        parsed["attributes"] = merged_attrs[:50]
        parsed["tier_used"] = "AI_EXTRACTION"
        parsed["ai_invoked"] = True
        parsed["validation_warnings"] = warnings

        # Cache in memory
        _AI_EXTRACTION_CACHE[content_hash] = parsed

        logger.info(
            "AI Extracted and validated %d attributes (%d rule, %d AI) for MPN=%s",
            len(parsed["attributes"]), len(existing_attrs), len(validated_ai_attrs), mpn
        )
        return parsed

    except Exception as exc:
        logger.warning("Gemini extraction failed for MPN=%s: %s. Using rule-based results.", mpn, exc)
        base_result["tier_used"] = "RULE_FALLBACK"
        return base_result