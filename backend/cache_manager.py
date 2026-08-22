"""
cache_manager.py — Parametric AI
Specification v2 2-Tier Caching & Database-Backed Checkpointing.

1. Source Cache: Keyed by URL and SHA256(content).
2. Product Cache: Keyed by canonical product key (stores resolved/normalized attributes).
3. Processing Checkpoints: SQLite persistent table keyed by (job_id, canonical_key)
   enabling instantaneous resume-after-crash.
4. Human Review Store: Stores flagged products, reasons, and review actions.
"""

import os
import json
import sqlite3
import hashlib
import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "parametric_cache.db")


class CacheManager:
    """
    Manages Tier-1 Source Cache, Tier-2 Product Cache, Job Checkpoints, and Review Queue in SQLite.
    """

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initializes indexed relational tables for caches, checkpoints, and review items."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Source Cache (Tier 1: URL / Content Hash)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS source_cache (
                    url_hash TEXT PRIMARY KEY,
                    url TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    page_text TEXT,
                    json_ld TEXT,
                    pdfs_json TEXT,
                    images_json TEXT,
                    status_code INTEGER DEFAULT 200,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_source_url ON source_cache(url);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_source_content_hash ON source_cache(content_hash);")

            # 2. Product Cache (Tier 2: Canonical Key)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS product_cache (
                    canonical_key TEXT PRIMARY KEY,
                    brand TEXT,
                    mpn TEXT,
                    resolved_data_json TEXT NOT NULL,
                    confidence_score REAL DEFAULT 1.0,
                    tier_breakdown_json TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_product_brand_mpn ON product_cache(brand, mpn);")

            # 3. Processing Checkpoints (Crash resilience & resume)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS processing_checkpoints (
                    job_id TEXT NOT NULL,
                    canonical_key TEXT NOT NULL,
                    status TEXT NOT NULL, -- 'COMPLETED', 'FAILED', 'FLAGGED_REVIEW'
                    result_json TEXT,
                    error_msg TEXT,
                    tier_used TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (job_id, canonical_key)
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_checkpoint_job ON processing_checkpoints(job_id);")

            # 4. Review Queue (Human-in-the-loop accuracy backstop)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS review_queue (
                    job_id TEXT NOT NULL,
                    canonical_key TEXT NOT NULL,
                    brand TEXT,
                    mpn TEXT,
                    flag_reasons_json TEXT NOT NULL,
                    extracted_data_json TEXT NOT NULL,
                    source_evidence_json TEXT,
                    review_status TEXT DEFAULT 'PENDING', -- 'PENDING', 'ACCEPTED', 'CORRECTED', 'REJECTED'
                    human_corrections_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (job_id, canonical_key)
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_review_job_status ON review_queue(job_id, review_status);")

            conn.commit()

    # ── Tier 1: Source Cache Methods ───────────────────────────────────────────

    def get_source_by_url(self, url: str) -> Optional[Dict[str, Any]]:
        """Lookup cached web text/PDFs/JSON-LD by URL."""
        if not url or url == "URL Not Found":
            return None
        url_hash = hashlib.sha256(url.strip().encode("utf-8")).hexdigest()
        try:
            with self._get_connection() as conn:
                row = conn.execute("SELECT * FROM source_cache WHERE url_hash = ?", (url_hash,)).fetchone()
                if row:
                    return {
                        "url": row["url"],
                        "content_hash": row["content_hash"],
                        "page_text": row["page_text"],
                        "json_ld": json.loads(row["json_ld"]) if row["json_ld"] else {},
                        "pdfs": json.loads(row["pdfs_json"]) if row["pdfs_json"] else [],
                        "images": json.loads(row["images_json"]) if row["images_json"] else [],
                    }
        except Exception as e:
            logger.warning("Source cache lookup error: %s", e)
        return None

    def store_source(
        self,
        url: str,
        page_text: str,
        json_ld: Optional[Dict[str, Any]] = None,
        pdfs: Optional[List[str]] = None,
        images: Optional[List[str]] = None
    ) -> str:
        """Stores scraped source payload into Tier-1 Source Cache."""
        if not url:
            return ""
        url_hash = hashlib.sha256(url.strip().encode("utf-8")).hexdigest()
        content_bytes = (page_text or "").encode("utf-8")
        content_hash = hashlib.sha256(content_bytes).hexdigest()

        try:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT INTO source_cache (url_hash, url, content_hash, page_text, json_ld, pdfs_json, images_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(url_hash) DO UPDATE SET
                        content_hash = excluded.content_hash,
                        page_text = excluded.page_text,
                        json_ld = excluded.json_ld,
                        pdfs_json = excluded.pdfs_json,
                        images_json = excluded.images_json,
                        created_at = CURRENT_TIMESTAMP
                """, (
                    url_hash,
                    url,
                    content_hash,
                    page_text,
                    json.dumps(json_ld or {}),
                    json.dumps(pdfs or []),
                    json.dumps(images or [])
                ))
                conn.commit()
        except Exception as e:
            logger.warning("Error storing source cache for %s: %s", url, e)
        return content_hash

    # ── Tier 2: Product Cache Methods ──────────────────────────────────────────

    def get_product(self, canonical_key: str) -> Optional[Dict[str, Any]]:
        """Fetches fully enriched/normalized product by canonical key."""
        try:
            with self._get_connection() as conn:
                row = conn.execute("SELECT * FROM product_cache WHERE canonical_key = ?", (canonical_key,)).fetchone()
                if row:
                    data = json.loads(row["resolved_data_json"])
                    data["_confidence"] = row["confidence_score"]
                    data["_tier_breakdown"] = json.loads(row["tier_breakdown_json"]) if row["tier_breakdown_json"] else {}
                    data["_from_product_cache"] = True
                    return data
        except Exception as e:
            logger.warning("Product cache lookup error: %s", e)
        return None

    def store_product(
        self,
        canonical_key: str,
        brand: str,
        mpn: str,
        resolved_data: Dict[str, Any],
        confidence_score: float = 1.0,
        tier_breakdown: Optional[Dict[str, Any]] = None
    ):
        """Saves fully enriched/normalized product into Tier-2 Product Cache."""
        try:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT INTO product_cache (canonical_key, brand, mpn, resolved_data_json, confidence_score, tier_breakdown_json)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(canonical_key) DO UPDATE SET
                        resolved_data_json = excluded.resolved_data_json,
                        confidence_score = excluded.confidence_score,
                        tier_breakdown_json = excluded.tier_breakdown_json,
                        updated_at = CURRENT_TIMESTAMP
                """, (
                    canonical_key,
                    brand,
                    mpn,
                    json.dumps(resolved_data),
                    confidence_score,
                    json.dumps(tier_breakdown or {})
                ))
                conn.commit()
        except Exception as e:
            logger.warning("Error storing product cache %s: %s", canonical_key, e)

    # ── Checkpointing Methods ──────────────────────────────────────────────────

    def get_completed_checkpoints(self, job_id: str) -> Dict[str, Dict[str, Any]]:
        """Returns all completed checkpoint entries for a job_id."""
        checkpoints: Dict[str, Dict[str, Any]] = {}
        try:
            with self._get_connection() as conn:
                rows = conn.execute(
                    "SELECT canonical_key, status, result_json, tier_used FROM processing_checkpoints WHERE job_id = ? AND status = 'COMPLETED'",
                    (job_id,)
                ).fetchall()
                for r in rows:
                    checkpoints[r["canonical_key"]] = {
                        "status": r["status"],
                        "result": json.loads(r["result_json"]) if r["result_json"] else {},
                        "tier_used": r["tier_used"]
                    }
        except Exception as e:
            logger.warning("Error fetching checkpoints for job %s: %s", job_id, e)
        return checkpoints

    def save_checkpoint(
        self,
        job_id: str,
        canonical_key: str,
        status: str,
        result: Optional[Dict[str, Any]] = None,
        error_msg: Optional[str] = None,
        tier_used: Optional[str] = "RULE_PATTERN"
    ):
        """Saves or updates a processing checkpoint row."""
        try:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT INTO processing_checkpoints (job_id, canonical_key, status, result_json, error_msg, tier_used)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(job_id, canonical_key) DO UPDATE SET
                        status = excluded.status,
                        result_json = excluded.result_json,
                        error_msg = excluded.error_msg,
                        tier_used = excluded.tier_used,
                        updated_at = CURRENT_TIMESTAMP
                """, (
                    job_id,
                    canonical_key,
                    status,
                    json.dumps(result) if result else None,
                    error_msg,
                    tier_used
                ))
                conn.commit()
        except Exception as e:
            logger.warning("Error saving checkpoint for %s::%s: %s", job_id, canonical_key, e)

    # ── Review Queue Methods ───────────────────────────────────────────────────

    def flag_for_review(
        self,
        job_id: str,
        canonical_key: str,
        brand: str,
        mpn: str,
        flag_reasons: List[str],
        extracted_data: Dict[str, Any],
        source_evidence: Optional[Dict[str, Any]] = None
    ):
        """Enqueues a product requiring human review into the review queue."""
        try:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT INTO review_queue (job_id, canonical_key, brand, mpn, flag_reasons_json, extracted_data_json, source_evidence_json, review_status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'PENDING')
                    ON CONFLICT(job_id, canonical_key) DO UPDATE SET
                        flag_reasons_json = excluded.flag_reasons_json,
                        extracted_data_json = excluded.extracted_data_json,
                        source_evidence_json = excluded.source_evidence_json,
                        created_at = CURRENT_TIMESTAMP
                """, (
                    job_id,
                    canonical_key,
                    brand,
                    mpn,
                    json.dumps(flag_reasons),
                    json.dumps(extracted_data),
                    json.dumps(source_evidence or {})
                ))
                conn.commit()
        except Exception as e:
            logger.warning("Error enqueueing review for %s: %s", canonical_key, e)

    def get_review_items(self, job_id: str, status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieves flagged review items for the frontend review screen."""
        items = []
        try:
            with self._get_connection() as conn:
                if status_filter:
                    rows = conn.execute(
                        "SELECT * FROM review_queue WHERE job_id = ? AND review_status = ? ORDER BY created_at DESC",
                        (job_id, status_filter)
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT * FROM review_queue WHERE job_id = ? ORDER BY created_at DESC",
                        (job_id,)
                    ).fetchall()

                for r in rows:
                    items.append({
                        "job_id": r["job_id"],
                        "canonical_key": r["canonical_key"],
                        "brand": r["brand"],
                        "mpn": r["mpn"],
                        "flag_reasons": json.loads(r["flag_reasons_json"]),
                        "extracted_data": json.loads(r["extracted_data_json"]),
                        "source_evidence": json.loads(r["source_evidence_json"]) if r["source_evidence_json"] else {},
                        "review_status": r["review_status"],
                        "human_corrections": json.loads(r["human_corrections_json"]) if r["human_corrections_json"] else None,
                        "created_at": r["created_at"]
                    })
        except Exception as e:
            logger.warning("Error fetching review items: %s", e)
        return items

    def apply_review_action(
        self,
        job_id: str,
        canonical_key: str,
        action: str,  # 'ACCEPTED', 'CORRECTED', 'REJECTED'
        corrections: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Applies human review decision, updating review queue, checkpoints, and product cache."""
        try:
            with self._get_connection() as conn:
                row = conn.execute(
                    "SELECT extracted_data_json, brand, mpn FROM review_queue WHERE job_id = ? AND canonical_key = ?",
                    (job_id, canonical_key)
                ).fetchone()
                
                if not row:
                    return False

                current_data = json.loads(row["extracted_data_json"])
                brand = row["brand"]
                mpn = row["mpn"]

                if action == "CORRECTED" and corrections:
                    current_data.update(corrections)
                    current_data["_human_verified"] = True

                # Update review queue row
                conn.execute("""
                    UPDATE review_queue
                    SET review_status = ?, human_corrections_json = ?
                    WHERE job_id = ? AND canonical_key = ?
                """, (action, json.dumps(corrections or {}), job_id, canonical_key))

                # Update checkpoint
                conn.execute("""
                    UPDATE processing_checkpoints
                    SET status = 'COMPLETED', result_json = ?, tier_used = 'HUMAN_REVIEW'
                    WHERE job_id = ? AND canonical_key = ?
                """, (json.dumps(current_data), job_id, canonical_key))

                conn.commit()

            # Feed back to Product Cache
            if action in ("ACCEPTED", "CORRECTED"):
                self.store_product(
                    canonical_key=canonical_key,
                    brand=brand,
                    mpn=mpn,
                    resolved_data=current_data,
                    confidence_score=1.0,
                    tier_breakdown={"HUMAN_REVIEW": 100}
                )

            return True
        except Exception as e:
            logger.error("Error applying review action for %s: %s", canonical_key, e)
            return False


# Global singleton instance
cache_manager = CacheManager()
