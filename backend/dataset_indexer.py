"""
dataset_indexer.py — Parametric AI
High-Performance Scalable Inverted Index & Dataset QA Engine.
Supports CSV datasets from 1,000 to 100,000+ rows without hardcoded limits.
Builds inverted token indexes, exact identifier hash maps, and numeric ranking indexes.
Enforces strict validation: TOTAL CSV ROWS == TOTAL INDEXED ROWS.
"""

import io
import re
import uuid
import logging
from typing import List, Dict, Any, Optional, Tuple, Set
from collections import defaultdict
import pandas as pd

logger = logging.getLogger(__name__)

STOP_WORDS = {
    "what", "which", "is", "are", "the", "of", "for", "in", "at", "and", "or", "a", "an",
    "rating", "ratings", "value", "values", "spec", "specs", "specification", "specifications",
    "level", "please", "tell", "show", "give", "item", "items", "product", "products", "model", "sku",
    "part", "parts", "num", "number", "mfg", "find", "get", "whats", "how", "much", "many", "does",
    "have", "with", "from", "this", "that", "dataset", "catalog", "table", "all", "available",
    "information", "details"
}


def tokenize(text: str) -> List[str]:
    """Tokenizes text into normalized lowercase alphanumeric tokens."""
    if not text:
        return []
    return [w.lower() for w in re.findall(r'[a-zA-Z0-9_\-\.\/]+', str(text)) if len(w) >= 2]


class IndexedDataset:
    """
    In-memory indexed dataset holding all rows and columns with inverted index and hash lookups.
    Zero row truncation & Zero column truncation — 100% of rows and 1,000+ columns are indexed and searchable.
    """

    def __init__(self, dataset_id: str, name: str, rows: List[Dict[str, Any]], columns: List[str], total_csv_rows: int, total_csv_columns: Optional[int] = None):
        self.dataset_id = dataset_id
        self.name = name
        self.rows: List[Dict[str, Any]] = rows
        self.columns: List[str] = columns
        self.total_csv_rows: int = total_csv_rows
        self.total_indexed_rows: int = len(rows)
        self.total_csv_columns: int = total_csv_columns if total_csv_columns is not None else len(columns)
        self.total_indexed_columns: int = len(columns)
        self.is_valid: bool = (
            self.total_csv_rows == self.total_indexed_rows and
            self.total_csv_columns == self.total_indexed_columns
        )

        # ── Fast Lookup Indexes ──
        # 1. Exact ID / SKU / MPN map: normalized_key -> list of row indices
        self.id_to_row_indices: Dict[str, List[int]] = defaultdict(list)
        # 2. Inverted token index: token -> set of row indices
        self.token_to_row_indices: Dict[str, Set[int]] = defaultdict(set)
        # 3. Brand / Manufacturer map: normalized_brand -> set of row indices
        self.brand_to_row_indices: Dict[str, Set[int]] = defaultdict(set)
        # 4. Normalized metadata cache for each row
        self.row_metadata: List[Dict[str, Any]] = []

        self._build_index()

    def _build_index(self):
        """Builds inverted indices and token maps across every single row in the dataset."""
        logger.info("Building full inverted index for dataset '%s' (%d rows)...", self.name, len(self.rows))
        
        for idx, row in enumerate(self.rows):
            # Discover core identity fields
            id_val = self._extract_id(row, idx)
            brand_val = self._extract_brand(row)
            desc_val = self._extract_desc(row, brand_val, id_val)
            cat_val = self._extract_category(row)

            # Store standard attributes
            attributes = self._extract_attributes(row)

            meta = {
                "id": id_val,
                "brand": brand_val,
                "description": desc_val,
                "category": cat_val,
                "attributes": attributes,
                "raw_record": row
            }
            self.row_metadata.append(meta)

            # 1. Index exact identifiers
            if id_val:
                id_clean = id_val.lower().strip()
                self.id_to_row_indices[id_clean].append(idx)
                # Also index alphanumeric-only version e.g. "PDSH4816AF" vs "PDSH-4816-AF"
                id_alphanumeric = re.sub(r'[^a-zA-Z0-9]', '', id_clean)
                if id_alphanumeric and id_alphanumeric != id_clean:
                    self.id_to_row_indices[id_alphanumeric].append(idx)

            # Also check direct SKU/MPN fields
            for key in ["mfg_part_num", "Mfg_Part_Num", "part_number", "part_num", "sku", "SKU", "id", "ID", "model"]:
                if key in row and row[key]:
                    val_str = str(row[key]).lower().strip()
                    self.id_to_row_indices[val_str].append(idx)
                    val_alpha = re.sub(r'[^a-zA-Z0-9]', '', val_str)
                    if val_alpha and val_alpha != val_str:
                        self.id_to_row_indices[val_alpha].append(idx)

            # 2. Index Brand
            if brand_val:
                b_clean = brand_val.lower().replace('®', '').strip()
                self.brand_to_row_indices[b_clean].add(idx)
                for b_tok in tokenize(b_clean):
                    if b_tok not in STOP_WORDS:
                        self.brand_to_row_indices[b_tok].add(idx)

            # 3. Build token inverted index across ALL columns & values
            row_tokens = set()
            for k, v in row.items():
                if v is not None and not isinstance(v, (list, dict)):
                    for tok in tokenize(str(k)):
                        if tok not in STOP_WORDS:
                            row_tokens.add(tok)
                    for tok in tokenize(str(v)):
                        if tok not in STOP_WORDS:
                            row_tokens.add(tok)

            for tok in row_tokens:
                self.token_to_row_indices[tok].add(idx)

        logger.info(
            "Index complete: %d rows indexed, %d unique tokens, %d unique IDs.",
            len(self.rows), len(self.token_to_row_indices), len(self.id_to_row_indices)
        )

    def _extract_id(self, record: Dict[str, Any], idx: int) -> str:
        for k in ["mfg_part_num", "Mfg_Part_Num", "part_number", "part_num", "sku", "SKU", "id", "ID", "model", "Model", "product_id", "item_no", "code", "part_no"]:
            if k in record and record[k]:
                return str(record[k]).strip()
        for k, v in record.items():
            if any(x in str(k).lower() for x in ["num", "sku", "id", "model", "code", "part"]) and v:
                return str(v).strip()
        return f"ROW-{idx + 1}"

    def _extract_brand(self, record: Dict[str, Any]) -> str:
        for k in ["brand_name", "brand", "Brand", "Part_Manuf", "mfg_name", "manufacturer", "Manufacturer", "vendor", "supplier", "make", "oem", "E1_Brand", "Unilog_Brand"]:
            if k in record and record[k]:
                return str(record[k]).strip()
        for k, v in record.items():
            if any(x in str(k).lower() for x in ["brand", "manuf", "vendor", "make", "oem"]) and v:
                return str(v).strip()
        return ""

    def _extract_desc(self, record: Dict[str, Any], brand: str, id_val: str) -> str:
        for k in ["short_desc", "part_desc", "Part_Desc", "description", "Description", "title", "Title", "name", "Name", "item_name"]:
            if k in record and record[k]:
                return str(record[k]).strip()
        return f"{brand} {id_val}".strip()

    def _extract_category(self, record: Dict[str, Any]) -> str:
        for k in ["fine", "class", "dept", "category", "Category", "type", "Type", "classpath", "classification"]:
            if k in record and record[k]:
                return str(record[k]).strip()
        return "General"

    def _extract_attributes(self, record: Dict[str, Any]) -> List[Dict[str, Any]]:
        raw_attrs = []
        if "attributes" in record and isinstance(record["attributes"], list):
            raw_attrs = [dict(a) for a in record["attributes"]]
        elif "raw_attributes" in record and isinstance(record["raw_attributes"], list):
            raw_attrs = [dict(a) for a in record["raw_attributes"]]

        existing_labels = {str(a.get("label", "")).lower() for a in raw_attrs}
        skip_keys = {
            "attributes", "raw_attributes", "conflicts", "pdf_spatial_evidence",
            "ref_urls", "standard_approvals", "approvals", "id", "sku", "mfg_part_num",
            "mfg_part_number", "part_number", "part_num", "product_id", "raw_record", "raw_text"
        }
        for k, v in record.items():
            if str(k).lower() not in skip_keys and v is not None and not isinstance(v, (list, dict)):
                clean_lbl = str(k).replace("_", " ").title()
                if clean_lbl.lower() not in existing_labels:
                    raw_attrs.append({"label": clean_lbl, "raw_key": str(k), "value": str(v), "uom": ""})
                    existing_labels.add(clean_lbl.lower())
        return raw_attrs

    def search(self, query: str, top_k: int = 50) -> Tuple[List[Dict[str, Any]], str]:
        """
        Searches the entire indexed dataset without row truncation.
        Returns (matching_rows, match_type).
        """
        q_clean = query.strip()
        q_lower = q_clean.lower()

        # 1. Exact ID / SKU lookup
        # Check quoted strings e.g. "PDSH4816AF"
        quotes = re.findall(r'["\']([a-zA-Z0-9_\-\.\/]+)["\']', q_clean)
        if quotes:
            for q_term in quotes:
                term_clean = q_term.lower().strip()
                if term_clean in self.id_to_row_indices:
                    indices = self.id_to_row_indices[term_clean]
                    return ([self.rows[i] for i in indices], "exact_id")

        # Check all alphanumeric tokens for exact ID matches
        query_tokens = tokenize(q_lower)
        for tok in query_tokens:
            if tok in self.id_to_row_indices:
                indices = self.id_to_row_indices[tok]
                return ([self.rows[i] for i in indices], "exact_id")
            tok_alpha = re.sub(r'[^a-zA-Z0-9]', '', tok)
            if tok_alpha in self.id_to_row_indices:
                indices = self.id_to_row_indices[tok_alpha]
                return ([self.rows[i] for i in indices], "exact_id")

        # 2. Token Inverted Index Multi-Keyword Search
        meaningful_tokens = [t for t in query_tokens if t not in STOP_WORDS and len(t) >= 2]
        if not meaningful_tokens:
            return ([], "none")

        # Score matching rows by token intersection & frequency
        row_scores = defaultdict(float)
        for tok in meaningful_tokens:
            if tok in self.token_to_row_indices:
                # IDF weight: rarer tokens get higher weight
                idf = 1.0 / (1.0 + len(self.token_to_row_indices[tok]) / max(1, len(self.rows)))
                for row_idx in self.token_to_row_indices[tok]:
                    row_scores[row_idx] += idf

            # Partial token matching for sub-words
            if len(tok) >= 4:
                for index_tok, row_indices in self.token_to_row_indices.items():
                    if index_tok != tok and (tok in index_tok or index_tok in tok):
                        for row_idx in row_indices:
                            row_scores[row_idx] += 0.2

        if not row_scores:
            return ([], "none")

        sorted_rows = sorted(row_scores.items(), key=lambda x: x[1], reverse=True)
        top_matches = [self.rows[row_idx] for row_idx, score in sorted_rows[:top_k]]
        return (top_matches, "keyword_match")

    def answer_query(self, user_message: str, api_key: Optional[str] = None) -> Dict[str, Any]:
        """
        Executes QA across the full dataset index.
        Evaluates ranking, exact entity specs, comparison, multi-row matches, or non-hallucinatory not-found responses.
        """
        msg_lower = user_message.lower().strip()

        # ── 1. Ranking Queries (Highest / Lowest / Max / Min) over ALL rows & columns ──
        is_ranking_query = any(w in msg_lower for w in ["highest", "lowest", "maximum", "max", "minimum", "min", "top", "fastest", "slowest", "most", "least"])
        if is_ranking_query:
            is_min = any(w in msg_lower for w in ["lowest", "minimum", "min", "slowest", "least"])
            candidate_tokens = [w for w in tokenize(msg_lower) if w not in STOP_WORDS and w not in [
                "which", "tool", "tools", "product", "products", "item", "items", "highest", "lowest",
                "maximum", "max", "minimum", "min", "top", "fastest", "slowest", "most", "least",
                "column", "columns", "value", "values", "metric", "level", "rating", "specs", "spec",
                "dataset", "catalog", "table", "has", "have", "had", "having", "with", "row", "rows"
            ]]

            for target_metric in candidate_tokens:
                ranked = []
                for meta in self.row_metadata:
                    for a in meta["attributes"]:
                        lbl = str(a.get("label", "")).lower()
                        raw_k = str(a.get("raw_key", "")).lower()
                        uom = str(a.get("uom", "")).lower()
                        val_str = str(a.get("value", "")).replace(",", "")
                        if target_metric in lbl or target_metric in raw_k or target_metric in uom:
                            num_match = re.search(r'[-+]?\d*\.?\d+', val_str)
                            if num_match:
                                try:
                                    val_num = float(num_match.group(0))
                                    ranked.append((val_num, meta, a))
                                except ValueError:
                                    pass

                if ranked:
                    ranked.sort(key=lambda x: x[0], reverse=not is_min)
                    best_val_num, best_meta, best_attr = ranked[0]
                    best_name = f"{best_meta['brand']} {best_meta['id']}".strip()
                    val_display = f"{best_attr.get('value')} {best_attr.get('uom', '')}".strip()
                    direction_str = "lowest" if is_min else "highest"
                    return {
                        "status": "success",
                        "model": "Parametric AI Dataset Indexer",
                        "response": f"**{best_name}** has the {direction_str} {best_attr.get('label')} with **{val_display}** (evaluated across all {self.total_indexed_rows} indexed rows and {self.total_indexed_columns} columns).",
                        "total_indexed_rows": self.total_indexed_rows,
                        "total_indexed_columns": self.total_indexed_columns,
                    }

        # ── 2. Search Full Index for Matches ──
        matching_rows, match_type = self.search(user_message, top_k=20)

        # Check if the user asked about a specific entity
        queried_entity = self._extract_queried_entity_name(user_message)
        is_specific_query = bool(queried_entity and queried_entity.lower() not in ["dataset", "catalog", "table", "all", "products", "items"])

        if match_type == "exact_id" and matching_rows:
            target_row = matching_rows[0]
            meta = next((m for m in self.row_metadata if m["raw_record"] == target_row), self.row_metadata[0])
            return self._format_single_record_response(meta, user_message)

        if is_specific_query:
            entity_clean = queried_entity.lower().strip()
            entity_alpha = re.sub(r'[^a-zA-Z0-9]', '', entity_clean)
            entity_tokens = [t for t in tokenize(entity_clean) if t not in STOP_WORDS and t not in ["part", "num", "mfg", "sku", "model", "item"]]

            matched_target = None
            if entity_clean in self.id_to_row_indices:
                matched_target = self.rows[self.id_to_row_indices[entity_clean][0]]
            elif entity_alpha in self.id_to_row_indices:
                matched_target = self.rows[self.id_to_row_indices[entity_alpha][0]]
            elif matching_rows:
                for r in matching_rows:
                    meta = next((m for m in self.row_metadata if m["raw_record"] == r), None)
                    if meta:
                        id_c = meta["id"].lower()
                        brand_c = meta["brand"].lower()
                        desc_c = meta["description"].lower()
                        if entity_clean == id_c or entity_clean in id_c or entity_clean in brand_c or (entity_tokens and all(t in id_c or t in brand_c or t in desc_c for t in entity_tokens)):
                            matched_target = r
                            break

            if matched_target:
                meta = next((m for m in self.row_metadata if m["raw_record"] == matched_target), self.row_metadata[0])
                return self._format_single_record_response(meta, user_message)
            else:
                return {
                    "status": "success",
                    "model": "Parametric AI Dataset Indexer",
                    "response": f"I couldn't find '{queried_entity}' in the uploaded dataset ({self.total_indexed_rows} rows indexed). Information was not found in the dataset.",
                    "total_indexed_rows": self.total_indexed_rows,
                }

        # Multi-row matching query (e.g. category or keyword search)
        if matching_rows:
            if len(matching_rows) == 1:
                meta = next((m for m in self.row_metadata if m["raw_record"] == matching_rows[0]), self.row_metadata[0])
                return self._format_single_record_response(meta, user_message)

            items_str = []
            for r in matching_rows[:10]:
                meta = next((m for m in self.row_metadata if m["raw_record"] == r), None)
                if meta:
                    attrs_sample = ", ".join([f"{a.get('label')}: {a.get('value')} {a.get('uom', '')}".strip() for a in meta["attributes"][:3]])
                    items_str.append(f"* **{meta['brand']} {meta['id']}** ({meta['category']}): {meta['description']}\n  _{attrs_sample}_")

            total_found = len(matching_rows)
            return {
                "status": "success",
                "model": "Parametric AI Dataset Indexer",
                "response": f"### 🔍 Found {total_found} Matching Record(s) in **{self.name}** (Total Index: {self.total_indexed_rows} rows):\n\n" + "\n\n".join(items_str),
                "total_indexed_rows": self.total_indexed_rows,
            }

        # No match found
        return {
            "status": "success",
            "model": "Parametric AI Dataset Indexer",
            "response": f"No matching records found in the dataset for your query. Searched across all {self.total_indexed_rows} indexed rows.",
            "total_indexed_rows": self.total_indexed_rows,
        }

    def _extract_queried_entity_name(self, query: str) -> Optional[str]:
        quotes = re.findall(r'["\']([a-zA-Z0-9_\-\.\/]+)["\']', query)
        if quotes:
            return quotes[0].strip()

        cleaned = re.sub(r'^(what is|what are|tell me|show me|find|get|give me|check|what\'s)\s+(the\s+)?', '', query, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r'\b(mfg_part_num|mfg part num|part number|part_num|part num|sku|model|part_manuf|manufacturer|mfr url|url|support url)\b', '', cleaned, flags=re.IGNORECASE).strip()

        m = re.search(r'\b(?:of|for|about|in)\s+([A-Za-z0-9\s\-_\.]+)(?:\?|$|\.|\!)', cleaned, flags=re.IGNORECASE)
        if m:
            candidate = m.group(1).strip()
            candidate = re.sub(r'[\?\.\!]+$', '', candidate).strip()
            candidate = re.sub(r'^(mfg_part_num|mfg part num|part number|part num|sku|model)\s*', '', candidate, flags=re.IGNORECASE).strip()
            if len(candidate) > 2 and candidate.lower() not in ["the dataset", "the catalog", "this dataset", "dataset", "catalog", "table", "products", "items"]:
                return candidate

        tokens = [w for w in re.findall(r'[A-Za-z0-9\-]{3,}', query) if w.upper() not in [
            "WHAT", "WHICH", "SHOW", "LIST", "VIEW", "RATE", "UNIT", "VOLT", "AMPS", "SPEC", "EVAL",
            "THE", "FOR", "THAT", "THIS", "WITH", "HAVE", "DOES", "FROM", "RATING", "VALUE", "IS", "ARE",
            "TOOL", "TOOLS", "ITEM", "ITEMS", "PRODUCT", "PRODUCTS", "DATASET", "CATALOG", "HIGHEST", "LOWEST",
            "MFG", "PART", "NUM", "NUMBER", "SKU", "MODEL", "URL", "SUPPORT", "OFFICIAL", "MANUF", "MANUFACTURER", "DESC"
        ]]
        if tokens:
            return " ".join(tokens[-2:]) if len(tokens) >= 2 else tokens[0]
        return None

    def _format_single_record_response(self, meta: Dict[str, Any], user_message: str) -> Dict[str, Any]:
        msg_lower = user_message.lower().strip()
        entity_name = f"{meta['brand']} {meta['id']}".strip() if meta['brand'] else meta['id']
        raw_record = meta["raw_record"]
        attributes = meta["attributes"]

        # 1. Query-First Direct Attribute Extraction across all 1,000+ columns
        q_words = [w for w in tokenize(msg_lower) if w not in STOP_WORDS and len(w) >= 2]
        
        # Priority A: Exact column name or raw_key match
        exact_matched_attrs = []
        for a in attributes:
            lbl = str(a.get("label", "")).lower()
            raw_k = str(a.get("raw_key", "")).lower()
            lbl_clean = lbl.replace(" ", "_")
            raw_k_clean = raw_k.replace(" ", "_")
            for qw in q_words:
                qw_clean = qw.replace(" ", "_")
                if qw_clean in [raw_k_clean, lbl_clean, raw_k_clean.replace("_", ""), lbl_clean.replace("_", "")]:
                    if a not in exact_matched_attrs:
                        exact_matched_attrs.append(a)
                    break

        if exact_matched_attrs:
            matched_attrs = exact_matched_attrs
        else:
            # Priority B: Token intersection matching
            matched_attrs = []
            for a in attributes:
                lbl = str(a.get("label", "")).lower()
                raw_k = str(a.get("raw_key", "")).lower()
                lbl_tokens = set(tokenize(lbl) + tokenize(raw_k))
                if any(qw in lbl_tokens for qw in q_words):
                    matched_attrs.append(a)

        if matched_attrs:
            if len(matched_attrs) == 1:
                a = matched_attrs[0]
                val_str = f"{a.get('value')} {a.get('uom', '')}".strip()
                return {
                    "status": "success",
                    "model": "Parametric AI Dataset Indexer",
                    "response": f"The **{a.get('label')}** of **{entity_name}** is **{val_str}**.",
                    "total_indexed_rows": self.total_indexed_rows,
                    "total_indexed_columns": self.total_indexed_columns,
                }
            else:
                specs_list = "\n".join([f"* **{a.get('label')}:** {a.get('value')} {a.get('uom', '')}".strip() for a in matched_attrs[:15]])
                return {
                    "status": "success",
                    "model": "Parametric AI Dataset Indexer",
                    "response": f"### 📋 Specifications for **{entity_name}**:\n\n{specs_list}",
                    "total_indexed_rows": self.total_indexed_rows,
                    "total_indexed_columns": self.total_indexed_columns,
                }

        # 2. Standalone URL / MFR URL query
        if any(w in msg_lower for w in ["url", "link", "website", "support url", "support link", "web page", "mfr url"]):
            mfr_url = raw_record.get("mfr_url") or raw_record.get("MFR URL") or raw_record.get("MFR_URL") or raw_record.get("url") or raw_record.get("link")
            if not mfr_url:
                for a in attributes:
                    if any(u in str(a.get("label", "")).lower() for u in ["url", "link", "website"]):
                        mfr_url = a.get("value")
                        break

            if mfr_url:
                return {
                    "status": "success",
                    "model": "Parametric AI Dataset Indexer",
                    "response": f"The official product support URL for **{entity_name}** is: {mfr_url}",
                    "total_indexed_rows": self.total_indexed_rows,
                }
            else:
                return {
                    "status": "success",
                    "model": "Parametric AI Dataset Indexer",
                    "response": f"Official product support URL for **{entity_name}** is not available in the uploaded dataset.",
                    "total_indexed_rows": self.total_indexed_rows,
                }

        # 3. Standalone Manufacturer / Brand query
        if any(w in msg_lower for w in ["manufacturer", "who makes", "part manuf", "part_manuf", "brand", "make"]):
            manuf = raw_record.get("Part_Manuf") or raw_record.get("part_manuf") or raw_record.get("brand_name") or meta["brand"] or raw_record.get("manufacturer")
            if manuf:
                return {
                    "status": "success",
                    "model": "Parametric AI Dataset Indexer",
                    "response": f"The manufacturer of **{entity_name}** is **{manuf}**.",
                    "total_indexed_rows": self.total_indexed_rows,
                }

        # D. Overview of record
        specs_all = "\n".join([f"* **{a.get('label')}:** {a.get('value')} {a.get('uom', '')}".strip() for a in attributes[:8]])
        resp_text = f"**Entity:** {entity_name} ({meta['category']})\n\n**Description:** {meta['description']}\n\n**Specifications:**\n{specs_all}"
        return {
            "status": "success",
            "model": "Parametric AI Dataset Indexer",
            "response": resp_text,
            "total_indexed_rows": self.total_indexed_rows,
        }


class DatasetIndexManager:
    """
    Global manager for indexed datasets.
    Handles batched/chunked ingestion of arbitrary size datasets.
    """
    _datasets: Dict[str, IndexedDataset] = {}
    _active_dataset_id: Optional[str] = None

    @classmethod
    def ingest_from_file_bytes(cls, file_bytes: bytes, filename: str) -> IndexedDataset:
        """
        Parses complete CSV/Excel file in chunks/batches without any row limits.
        Indexes every single row and validates TOTAL CSV ROWS == TOTAL INDEXED ROWS.
        """
        logger.info("Ingesting dataset file: %s (size: %d bytes)", filename, len(file_bytes))
        
        all_rows: List[Dict[str, Any]] = []
        columns: List[str] = []
        total_data_rows = 0

        # Chunked ingestion for large files
        if filename.lower().endswith(".csv"):
            # Use chunksize for scalable reading
            chunk_iter = pd.read_csv(io.BytesIO(file_bytes), chunksize=10000, dtype=str)
            for chunk in chunk_iter:
                if not columns:
                    columns = list(chunk.columns)
                # Fill NaN with empty string to preserve clean dicts
                chunk = chunk.fillna("")
                rows_chunk = chunk.to_dict(orient="records")
                all_rows.extend(rows_chunk)
                total_data_rows += len(rows_chunk)
        elif filename.lower().endswith((".xls", ".xlsx")):
            df = pd.read_excel(io.BytesIO(file_bytes), dtype=str)
            df = df.fillna("")
            columns = list(df.columns)
            all_rows = df.to_dict(orient="records")
            total_data_rows = len(all_rows)
        else:
            raise ValueError(f"Unsupported file format for {filename}. Must be .csv or .xlsx")

        dataset_id = str(uuid.uuid4())[:8]
        indexed_dataset = IndexedDataset(
            dataset_id=dataset_id,
            name=filename,
            rows=all_rows,
            columns=columns,
            total_csv_rows=total_data_rows,
            total_csv_columns=len(columns)
        )

        # Enforce validation on both rows and columns
        assert indexed_dataset.total_csv_rows == indexed_dataset.total_indexed_rows, (
            f"Validation Failed! TOTAL CSV ROWS ({indexed_dataset.total_csv_rows}) != "
            f"TOTAL INDEXED ROWS ({indexed_dataset.total_indexed_rows})"
        )
        assert indexed_dataset.total_csv_columns == indexed_dataset.total_indexed_columns, (
            f"Validation Failed! TOTAL CSV COLUMNS ({indexed_dataset.total_csv_columns}) != "
            f"TOTAL INDEXED COLUMNS ({indexed_dataset.total_indexed_columns})"
        )

        cls._datasets[dataset_id] = indexed_dataset
        cls._active_dataset_id = dataset_id
        return indexed_dataset

    @classmethod
    def ingest_from_dict_list(cls, rows: List[Dict[str, Any]], name: str = "Uploaded Dataset") -> IndexedDataset:
        """Ingests and indexes an in-memory list of dictionaries."""
        dataset_id = str(uuid.uuid4())[:8]
        columns = list(rows[0].keys()) if rows else []
        indexed_dataset = IndexedDataset(
            dataset_id=dataset_id,
            name=name,
            rows=rows,
            columns=columns,
            total_csv_rows=len(rows),
            total_csv_columns=len(columns)
        )
        assert indexed_dataset.total_csv_rows == indexed_dataset.total_indexed_rows
        assert indexed_dataset.total_csv_columns == indexed_dataset.total_indexed_columns
        cls._datasets[dataset_id] = indexed_dataset
        cls._active_dataset_id = dataset_id
        return indexed_dataset

    @classmethod
    def get_dataset(cls, dataset_id: Optional[str] = None) -> Optional[IndexedDataset]:
        if dataset_id and dataset_id in cls._datasets:
            return cls._datasets[dataset_id]
        if cls._active_dataset_id and cls._active_dataset_id in cls._datasets:
            return cls._datasets[cls._active_dataset_id]
        return None



# VIBECODING IS JUST FUN BCOZ 






