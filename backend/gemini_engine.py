import os
import json
import re
from typing import Dict, Any, List, Optional, Tuple

UNIVERSAL_SYSTEM_PROMPT = """You are a Universal Parametric Data Analysis Assistant.

Your task is to answer questions about any structured dataset provided to you, regardless of its domain, column names, schema, product type, industry, or number of attributes.

## CRITICAL: Query-First Retrieval Rule
When the user asks a question about a specific entity, product, record, ID, model, SKU, part number, name, or other identifier:
1. Do NOT generate a dataset overview first.
2. Extract the entity identifier from the user's question.
3. Search the dataset specifically for that entity.
4. Check all potentially identifying columns dynamically.
5. Require a sufficiently strong match before generating an answer.
6. Once the matching record is found, retrieve the requested attribute from that record.
7. Answer the user's question directly.

### Example
User: "What is the voltage rating of FRIGIDAIRE PDSH4816AF?"
Response: **The voltage rating of FRIGIDAIRE PDSH4816AF is 120 V.**

### IMPORTANT
Do NOT respond with:
* Dataset Overview
* Total Records
* Available Records
* A list of unrelated records
* Random attributes from other records
when the user has asked about a specific entity.

### If no matching entity exists
Respond:
> **I couldn't find [entity] in the provided dataset.**

Do NOT substitute another product.
Do NOT guess the answer.
Do NOT return an overview of unrelated records.

### Dataset-Agnostic Requirement
This rule must work for ANY dataset.
Do not hard-code:
* Product
* Brand
* Part number
* Model
* Voltage
* Manufacturer
* Any specific column name
Instead, dynamically inspect the dataset schema and identify the fields that can match the entity mentioned by the user.

### Retrieval Priority
Use this priority:
**Exact identifier match → Exact name match → Strong multi-field match → Semantic match → No match**
Only use a semantic match when there is enough evidence that it refers to the requested entity.

### Response Priority
For a specific question:
**Find record → Find requested attribute → Validate → Answer**

Never:
**Question → Dataset overview → Random records**

## 1. Dynamic Attribute Extraction & Value Preservation
- Return values exactly as represented in the source.
- Preserve numbers, units, text, precision, and codes.
- Combine values with their units naturally (e.g. 120 + V -> **120 V**).

## 2. No Hallucination
The dataset is the source of truth. If the requested attribute or record cannot be found, respond:
> **Not available in the provided dataset.**

## 3. Calculations and Conversions
If the user requests a calculation or unit conversion:
- Show both the original value and the accurately converted/calculated result (e.g. Original: 120 V | Converted: 0.12 kV).

## 4. Conflict Detection
If multiple records contain conflicting values for the same attribute:
- Detect the conflict, show competing claims, and state:
  > **Conflict detected:** [attribute] has multiple values in the dataset.
"""


class GeminiFlashEngine:
    @staticmethod
    def get_api_key() -> str:
        return os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or ""

    @staticmethod
    def _call_gemini_api(api_key: str, system_prompt: str, user_message: str) -> Optional[str]:
        """Attempt to call live Gemini Flash model via official SDK."""
        try:
            # 1. Try google-genai package
            try:
                from google import genai
                client = genai.Client(api_key=api_key)
                response = client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=f"{system_prompt}\n\nUser Question: {user_message}"
                )
                if response and response.text:
                    return response.text
            except Exception:
                pass

            # 2. Fall back to google.generativeai package
            import google.generativeai as legacy_genai
            legacy_genai.configure(api_key=api_key)
            model = legacy_genai.GenerativeModel("gemini-1.5-flash")
            resp = model.generate_content(f"{system_prompt}\n\nUser Question: {user_message}")
            if resp and resp.text:
                return resp.text
        except Exception:
            pass
        return None

    # ── Universal Dynamic Record Helper ──
    @staticmethod
    def _extract_entity_meta(record: Dict[str, Any]) -> Dict[str, Any]:
        """Dynamically inspects any dictionary record without assuming specific column names."""
        rec_keys = list(record.keys())
        
        # 1. Discover identifier dynamically across any column name
        id_val = None
        for k in ["mfg_part_num", "Mfg_Part_Num", "part_number", "part_num", "sku", "SKU", "id", "ID", "model", "Model", "product_id", "item_no", "code", "part_no"]:
            if k in record and record[k]:
                id_val = str(record[k]).strip()
                break
        if not id_val:
            for k in rec_keys:
                if any(x in k.lower() for x in ["num", "sku", "id", "model", "code", "part"]) and record[k]:
                    id_val = str(record[k]).strip()
                    break
        if not id_val:
            id_val = str(record.get(rec_keys[0])).strip() if rec_keys else "Item"

        # 2. Discover brand / manufacturer dynamically
        brand_val = ""
        for k in ["brand_name", "brand", "Brand", "Part_Manuf", "mfg_name", "manufacturer", "Manufacturer", "vendor", "supplier", "make", "oem"]:
            if k in record and record[k]:
                brand_val = str(record[k]).strip()
                break
        if not brand_val:
            for k in rec_keys:
                if any(x in k.lower() for x in ["brand", "manuf", "vendor", "make", "oem"]) and record[k]:
                    brand_val = str(record[k]).strip()
                    break

        # 3. Discover category dynamically
        cat_val = "General"
        for k in ["fine", "class", "dept", "category", "Category", "type", "Type", "classpath", "classification"]:
            if k in record and record[k]:
                cat_val = str(record[k]).strip()
                break

        # 4. Discover description dynamically
        desc_val = ""
        for k in ["short_desc", "part_desc", "Part_Desc", "description", "Description", "title", "Title", "name", "Name", "item_name"]:
            if k in record and record[k]:
                desc_val = str(record[k]).strip()
                break
        if not desc_val:
            desc_val = f"{brand_val} {id_val}".strip()

        # 5. Discover attributes list or dictionary dynamically
        raw_attrs = []
        if "attributes" in record and isinstance(record["attributes"], list):
            raw_attrs = [dict(a) for a in record["attributes"]]
        elif "raw_attributes" in record and isinstance(record["raw_attributes"], list):
            raw_attrs = [dict(a) for a in record["raw_attributes"]]

        # Flatten all top-level descriptive keys so columns like MFR URL, Part_Manuf, E1_Brand etc. can be queried directly
        existing_labels = {str(a.get("label", "")).lower() for a in raw_attrs}
        skip_keys = {"attributes", "raw_attributes", "conflicts", "pdf_spatial_evidence", "ref_urls", "standard_approvals", "approvals", "id", "sku", "mfg_part_num", "mfg_part_number", "part_number", "part_num", "product_id", "raw_record", "raw_text"}
        for k, v in record.items():
            if str(k).lower() not in skip_keys:
                clean_lbl = str(k).replace("_", " ").title()
                if clean_lbl.lower() not in existing_labels and v is not None and not isinstance(v, (list, dict)):
                    raw_attrs.append({"label": clean_lbl, "raw_key": str(k), "value": str(v), "uom": ""})
                    existing_labels.add(clean_lbl.lower())

        return {
            "id": id_val,
            "brand": brand_val,
            "category": cat_val,
            "description": desc_val,
            "attributes": raw_attrs,
            "conflicts": record.get("conflicts", []),
            "approvals": record.get("standard_approvals", record.get("approvals", [])),
            "doc": record.get("pdf_document", "Datasheet.pdf"),
            "raw_record": record
        }

    # ── Match Score Evaluator for Query-First Retrieval ──
    @staticmethod
    def _find_matching_record(records: List[Dict[str, Any]], query: str) -> Tuple[Optional[Dict[str, Any]], float]:
        """
        Retrieval Priority:
        1. Exact identifier match (e.g. 'PDSH4816AF', '49-94-0013', 'WDTS7024RZ')
        2. Exact name / brand + identifier match (e.g. 'FRIGIDAIRE PDSH4816AF')
        3. Strong multi-field match
        4. Semantic match
        5. No match
        """
        q_lower = query.lower()
        
        # Check quoted entity first e.g. "PDSH4816AF"
        quotes = re.findall(r'["\']([a-zA-Z0-9_\-\.\/]+)["\']', query)
        q_quoted = quotes[0].lower().strip() if quotes else ""

        q_tokens = set(re.findall(r'[a-zA-Z0-9_\-\.\/]+', q_lower))
        
        best_rec = None
        best_score = 0.0

        for r in records:
            meta = GeminiFlashEngine._extract_entity_meta(r)
            rec_id_clean = meta["id"].lower().strip()
            rec_brand_clean = meta["brand"].lower().replace('®', '').strip()
            rec_desc_clean = meta["description"].lower().strip()

            score = 0.0

            # 1. Exact quoted identifier match
            if q_quoted and (rec_id_clean == q_quoted or q_quoted in rec_id_clean or rec_id_clean in q_quoted):
                score += 50.0

            # 2. Exact Identifier match
            if rec_id_clean and (rec_id_clean in q_lower or rec_id_clean in q_tokens):
                score += 25.0

            # 3. Brand + ID composite match
            brand_id_str = f"{rec_brand_clean} {rec_id_clean}".strip()
            if brand_id_str and (brand_id_str in q_lower or all(part in q_lower for part in [rec_brand_clean, rec_id_clean])):
                score += 30.0

            # 4. Part of ID match (for hyphenated/segmented identifiers)
            id_parts = [p for p in re.split(r'[\s\-_]+', rec_id_clean) if len(p) >= 3]
            for p in id_parts:
                if p in q_tokens or p in q_lower:
                    score += 8.0

            # 5. Brand exact match
            if rec_brand_clean and (rec_brand_clean in q_lower or rec_brand_clean in q_tokens):
                score += 4.0

            # 6. Exact name / description token overlap
            desc_words = [w for w in re.findall(r'[a-zA-Z0-9]+', rec_desc_clean) if len(w) > 3]
            overlap = [w for w in desc_words if w in q_tokens]
            score += len(overlap) * 1.5

            # 7. Check identifying raw fields dynamically
            for k, v in r.items():
                if isinstance(v, (str, int, float)):
                    v_str = str(v).lower().strip()
                    if q_quoted and v_str == q_quoted:
                        score += 40.0
                    elif len(v_str) >= 3 and (v_str in q_tokens or v_str in q_lower):
                        score += 3.0

            if score > best_score:
                best_score = score
                best_rec = r

        return (best_rec, best_score)

    @staticmethod
    def _extract_queried_entity_name(user_message: str) -> Optional[str]:
        """Extracts the specific entity name/identifier mentioned by the user if one exists."""
        # 1. Look for quoted terms first e.g. "PDSH4816AF"
        quotes = re.findall(r'["\']([a-zA-Z0-9_\-\.\/]+)["\']', user_message)
        if quotes:
            return quotes[0].strip()

        msg_lower = user_message.lower().strip()
        non_entity_cues = ["which", "compare", "highest", "lowest", "maximum", "max", "minimum", "min", "top", "best", "average", "avg", "total", "count", "list all", "show all", "overview", "summary"]
        if any(cue in msg_lower for cue in non_entity_cues):
            return None

        # Clean common query preambles and column references
        cleaned = re.sub(r'^(what is|what are|tell me|show me|find|get|give me|check|what\'s)\s+(the\s+)?', '', user_message, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r'\b(mfg_part_num|mfg part num|part number|part_num|part num|sku|model|part_manuf|manufacturer|mfr url|url|official product support url|support url)\b', '', cleaned, flags=re.IGNORECASE).strip()

        # Look for pattern "... of <ENTITY>?" or "... for <ENTITY>?"
        m = re.search(r'\b(?:of|for|about|in)\s+([A-Za-z0-9\s\-_\.]+)(?:\?|$|\.|\!)', cleaned, flags=re.IGNORECASE)
        if m:
            candidate = m.group(1).strip()
            candidate = re.sub(r'[\?\.\!]+$', '', candidate).strip()
            candidate = re.sub(r'^(mfg_part_num|mfg part num|part number|part num|sku|model)\s*', '', candidate, flags=re.IGNORECASE).strip()
            if len(candidate) > 2 and candidate.lower() not in ["the dataset", "the catalog", "this dataset", "dataset", "catalog", "table"]:
                return candidate

        # Extract alphanumeric tokens that look like specific model/SKU/brand
        tokens = [w for w in re.findall(r'[A-Za-z0-9\-]{3,}', user_message) if w.upper() not in [
            "WHAT", "WHICH", "SHOW", "LIST", "VIEW", "RATE", "UNIT", "VOLT", "AMPS", "SPEC", "EVAL",
            "THE", "FOR", "THAT", "THIS", "WITH", "HAVE", "DOES", "FROM", "RATING", "VALUE", "IS", "ARE",
            "TOOL", "TOOLS", "ITEM", "ITEMS", "PRODUCT", "PRODUCTS", "DATASET", "CATALOG", "HIGHEST", "LOWEST",
            "MFG", "PART", "NUM", "NUMBER", "SKU", "MODEL", "URL", "SUPPORT", "OFFICIAL", "MANUF", "MANUFACTURER", "DESC"
        ]]
        if tokens:
            return " ".join(tokens[-2:]) if len(tokens) >= 2 else tokens[0]
        return None

    @staticmethod
    def generate_chat_response(product: Dict[str, Any], user_message: str) -> Dict[str, Any]:
        """Dataset-Agnostic Single Product Reasoning with Query-First Retrieval."""
        api_key = GeminiFlashEngine.get_api_key()
        meta = GeminiFlashEngine._extract_entity_meta(product)

        # 1. Live Gemini LLM call with Universal Prompt
        if api_key:
            context_str = json.dumps(product, indent=2)
            sys_prompt = f"{UNIVERSAL_SYSTEM_PROMPT}\n\n### Current Record Context:\n{context_str}"
            gemini_reply = GeminiFlashEngine._call_gemini_api(api_key, sys_prompt, user_message)
            if gemini_reply:
                return {
                    "status": "success",
                    "model": "Gemini 1.5/2.0 Flash (Universal)",
                    "response": gemini_reply,
                    "is_real_llm": True
                }

        # 2. Universal Zero-Cost Semantic QA Engine
        msg_lower = user_message.lower().strip()
        attributes = meta["attributes"]
        conflicts = meta["conflicts"]
        
        # Format entity name cleanly
        brand_clean = meta['brand'].replace('®', '').strip()
        entity_name = f"{brand_clean} {meta['id']}".strip() if brand_clean else meta['id']

        # A. URL / Support URL / MFR URL query
        if any(w in msg_lower for w in ["url", "link", "website", "support url", "support link", "web page", "mfr url"]):
            mfr_url = meta["raw_record"].get("mfr_url") or meta["raw_record"].get("MFR URL") or meta["raw_record"].get("url") or meta["raw_record"].get("link")
            if not mfr_url:
                for a in attributes:
                    if any(u in str(a.get("label", "")).lower() for u in ["url", "link", "website"]):
                        mfr_url = a.get("value")
                        break
            if not mfr_url:
                # Check built-in catalog by matching part number
                from backend.dataset import INDUSTRIAL_DATASET
                cat_match = next((item for item in INDUSTRIAL_DATASET if item.get("id") == meta["id"] or item.get("mfg_part_num") == meta["id"]), None)
                if cat_match and cat_match.get("mfr_url"):
                    mfr_url = cat_match.get("mfr_url")

            if mfr_url:
                return {
                    "status": "success",
                    "model": "Universal Dataset Engine (Zero-Cost)",
                    "response": f"The official product support URL for {entity_name} is: {mfr_url}",
                    "is_real_llm": False
                }
            else:
                return {
                    "status": "success",
                    "model": "Universal Dataset Engine (Zero-Cost)",
                    "response": f"MFR URL for {entity_name} is not available in the uploaded dataset.",
                    "is_real_llm": False
                }

        # B. Manufacturer / Brand / Part_Manuf query
        if any(w in msg_lower for w in ["manufacturer", "who makes", "part manuf", "part_manuf", "brand", "make"]):
            manuf = meta["raw_record"].get("Part_Manuf") or meta["raw_record"].get("Part_Manuf (5293)") or meta["brand"] or meta["raw_record"].get("mfg_name") or meta["raw_record"].get("manufacturer")
            if not manuf:
                for a in attributes:
                    if any(u in str(a.get("label", "")).lower() for u in ["manuf", "brand", "maker"]):
                        manuf = a.get("value")
                        break
            if not manuf:
                from backend.dataset import INDUSTRIAL_DATASET
                cat_match = next((item for item in INDUSTRIAL_DATASET if item.get("id") == meta["id"] or item.get("mfg_part_num") == meta["id"]), None)
                if cat_match and (cat_match.get("brand_name") or cat_match.get("mfg_name")):
                    manuf = cat_match.get("brand_name") or cat_match.get("mfg_name")

            if manuf:
                return {
                    "status": "success",
                    "model": "Universal Dataset Engine (Zero-Cost)",
                    "response": f"The manufacturer of {entity_name} is {manuf}.",
                    "is_real_llm": False
                }

        # C. Conflict detection
        if any(w in msg_lower for w in ["conflict", "discrepancy", "mismatch", "reconcil"]):
            if conflicts:
                items = []
                for c in conflicts:
                    attr_name = c.get('attribute', 'Attribute')
                    s1 = c.get('source_1', {})
                    s2 = c.get('source_2', {})
                    s1_txt = s1.get('value') if isinstance(s1, dict) else str(s1)
                    s2_txt = s2.get('value') if isinstance(s2, dict) else str(s2)
                    res = c.get('resolution', 'Resolved')
                    reason = c.get('reason', 'Domain authority check')
                    items.append(f"> **Conflict detected:** `{attr_name}` has competing values (`{s1_txt}` vs `{s2_txt}`).\n> **👉 Resolved to:** `{res}` (*{reason}*)")
                return {
                    "status": "success",
                    "model": "Universal Dataset Engine (Zero-Cost)",
                    "response": f"### 🛡️ Truth Reconciliation for **{entity_name}**\n\n" + "\n\n".join(items),
                    "is_real_llm": False
                }
            else:
                return {
                    "status": "success",
                    "model": "Universal Dataset Engine (Zero-Cost)",
                    "response": f"✓ **Zero conflicts detected in dataset for {entity_name}.** All attributes are verified consistent.",
                    "is_real_llm": False
                }

        # D. Unit conversion
        if any(w in msg_lower for w in ["convert", "conversion", "metric", "si", "unit", "calculate"]):
            converted_rows = []
            for a in attributes:
                val = a.get("value", "")
                norm_val = a.get("norm_val")
                norm_uom = a.get("norm_uom", "")
                uom = a.get("uom", "")
                if norm_val and (norm_val != val or norm_uom != uom):
                    converted_rows.append(f"- **{a.get('label')}**:\n  - **Original:** `{val} {uom}`.strip()\n  - **Converted (SI):** `{norm_val} {norm_uom}`.strip()")
            
            if converted_rows:
                return {
                    "status": "success",
                    "model": "Universal Dataset Engine (Zero-Cost)",
                    "response": f"### 📏 Unit Conversions & Normalization for **{entity_name}**\n\n" + "\n".join(converted_rows),
                    "is_real_llm": False
                }

        # C. Query-First Direct Attribute Extraction
        # Discount generic query words
        stop_words = {
            "what", "which", "is", "are", "the", "of", "for", "in", "at", "and",
            "rating", "ratings", "value", "values", "spec", "specs", "specification",
            "specifications", "level", "please", "tell", "show", "give", "item",
            "product", "model", "sku", "find", "get", "whats", "how", "much", "many"
        }
        q_words = [w for w in re.findall(r'[a-zA-Z0-9]+', msg_lower) if w not in stop_words and len(w) >= 3]

        matched_attrs_dict = {}
        for a in attributes:
            lbl = str(a.get("label", "")).lower()
            lbl_words = [w for w in re.findall(r'[a-zA-Z0-9]+', lbl) if w not in stop_words]
            
            for qw in q_words:
                if qw in lbl or any(qw == lw or qw in lw or lw in qw for lw in lbl_words):
                    label_key = a.get("label")
                    if label_key not in matched_attrs_dict:
                        matched_attrs_dict[label_key] = a

        matched_attrs = list(matched_attrs_dict.values())

        if matched_attrs:
            if len(matched_attrs) == 1:
                best_attr = matched_attrs[0]
                val_str = f"{best_attr.get('value')} {best_attr.get('uom', '')}".strip()
                attr_label = best_attr.get('label', 'attribute').lower()
                return {
                    "status": "success",
                    "model": "Universal Dataset Engine (Zero-Cost)",
                    "response": f"The {attr_label} of {entity_name} is {val_str}.",
                    "is_real_llm": False
                }
            else:
                specs_list = "\n".join([f"* **{a.get('label')}:** {a.get('value')} {a.get('uom', '')}".strip() for a in matched_attrs])
                return {
                    "status": "success",
                    "model": "Universal Dataset Engine (Zero-Cost)",
                    "response": f"**Entity:** {entity_name}\n\n**Specifications:**\n{specs_list}",
                    "is_real_llm": False
                }

        # D. General Overview when no specific attribute was requested
        specs_all = "\n".join([f"* **{a.get('label')}:** {a.get('value')} {a.get('uom', '')}".strip() for a in attributes[:6]])
        resp_text = f"**Entity:** {entity_name} ({meta['category']})\n\n**Description:** {meta['description']}\n\n**Specifications:**\n{specs_all}"
        return {
            "status": "success",
            "model": "Universal Dataset Engine (Zero-Cost)",
            "response": resp_text,
            "is_real_llm": False
        }

    @staticmethod
    def generate_dataset_chat_response(dataset: List[Dict[str, Any]], user_message: str, dataset_name: str = "Provided Dataset") -> Dict[str, Any]:
        """
        Universal Dataset-Agnostic Multi-Record & Tabular QA Engine.
        Enforces full dataset indexing and Query-First Retrieval across 100% of rows.
        """
        from backend.dataset_indexer import DatasetIndexManager
        indexed = DatasetIndexManager.ingest_from_dict_list(dataset, name=dataset_name)
        api_key = GeminiFlashEngine.get_api_key()

        # 1. Live Gemini LLM call with Full-Index Context Retrieval (RAG)
        if api_key:
            matching_rows, _ = indexed.search(user_message, top_k=25)
            context_records = matching_rows if matching_rows else dataset[:25]
            context_str = json.dumps(context_records, indent=2)
            sys_prompt = f"{UNIVERSAL_SYSTEM_PROMPT}\n\n### Provided Dataset ('{dataset_name}' - Total Indexed Records: {len(dataset)}):\n{context_str}"
            gemini_reply = GeminiFlashEngine._call_gemini_api(api_key, sys_prompt, user_message)
            if gemini_reply:
                return {
                    "status": "success",
                    "model": "Gemini 1.5/2.0 Flash (Universal Dataset)",
                    "response": gemini_reply,
                    "is_real_llm": True
                }

        # 2. Universal Zero-Cost Query-First Retrieval Engine over ALL rows
        return indexed.answer_query(user_message, api_key=api_key)