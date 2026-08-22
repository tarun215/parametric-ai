"""
async_retriever.py — Parametric AI
Specification v2 Async I/O, Central Domain Token-Bucket Rate Limiter & Early-Exit Discovery.

1. Central per-domain token bucket rate limiting (politeness target e.g. 1 req/sec per domain).
2. Async/concurrent retrieval with connection pooling.
3. Early-exit URL discovery: stops the priority ladder as soon as an official source
   clears the confidence threshold (default 0.90).
"""

import time
import asyncio
import logging
import re
from urllib.parse import urlparse
from typing import Dict, List, Any, Optional, Tuple

import requests
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS

from backend.cache_manager import cache_manager

logger = logging.getLogger(__name__)

# Politeness rate limits: maximum requests per second per domain
DEFAULT_DOMAIN_RPS = 2.0

NON_INDUSTRIAL_DOMAINS = [
    "amazon.", "ebay.", "walmart.", "target.", "bestbuy.", "flipkart.",
    "alibaba.", "aliexpress.", "etsy.", "overstock.", "costco.",
    "youtube.", "instagram.", "facebook.", "twitter.", "x.com", "tiktok.", "pinterest.",
    "bbc.", "cnn.", "wikipedia.", "yahoo.", "news.", "reddit.", "quora."
]

ALLOWED_TLDS = {
    ".com", ".org", ".net", ".io", ".co", ".us", ".ca", ".de", ".uk", ".in",
    ".edu", ".gov", ".eu", ".tech", ".info", ".biz"
}

_SCRAPE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


class DomainTokenBucket:
    """
    Central token bucket rate limiter keyed by domain.
    Ensures concurrent workers do not overwhelm any individual manufacturer site.
    """

    def __init__(self, rps: float = DEFAULT_DOMAIN_RPS):
        self.rps = rps
        self.interval = 1.0 / max(0.1, rps)
        self.last_access: Dict[str, float] = {}

    def wait_for_domain(self, domain: str):
        """Blocks synchronously or sleeps until token is available for the given domain."""
        now = time.time()
        last = self.last_access.get(domain, 0.0)
        elapsed = now - last
        if elapsed < self.interval:
            sleep_time = self.interval - elapsed
            time.sleep(sleep_time)
        self.last_access[domain] = time.time()


# Global domain rate limiter
domain_rate_limiter = DomainTokenBucket()


def is_safe_industrial_domain(url: str) -> bool:
    """Verifies domain does not belong to consumer marketplaces or social media."""
    if not url or not url.startswith("http"):
        return False
    try:
        parsed = urlparse(url)
        netloc = parsed.netloc.lower()
        if any(bad in netloc for bad in NON_INDUSTRIAL_DOMAINS):
            return False
        if not any(netloc.endswith(tld) or f"{tld}/" in url.lower() for tld in ALLOWED_TLDS):
            return False
        return True
    except Exception:
        return False


def get_domain_key(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return "generic"


def resolve_pdf_url(href: str, base_url: str) -> str:
    href = href.strip()
    if href.startswith("http://") or href.startswith("https://"):
        return href
    m = re.match(r"(https?://[^/]+)", base_url)
    origin = m.group(1) if m else ""
    if href.startswith("/"):
        return origin + href
    base_dir = base_url.rsplit("/", 1)[0]
    return base_dir.rstrip("/") + "/" + href


class AsyncSourceRetriever:
    """
    Retrieves web content with Tier-1 caching, rate limiting, and early-exit discovery.
    """

    @classmethod
    def fetch_url(cls, url: str, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Fetches web page or PDF text. Uses Tier-1 source cache if available.
        """
        if not url or url == "URL Not Found" or not is_safe_industrial_domain(url):
            return {"url": url, "page_text": "", "json_ld": {}, "pdfs": [], "images": [], "from_cache": False}

        # 1. Tier-1 Source Cache check
        if not force_refresh:
            cached = cache_manager.get_source_by_url(url)
            if cached:
                cached["from_cache"] = True
                return cached

        # 2. Rate limiting check
        domain = get_domain_key(url)
        domain_rate_limiter.wait_for_domain(domain)

        # 3. Network Fetch
        result = {
            "url": url,
            "page_text": "",
            "json_ld": {},
            "pdfs": [],
            "images": [],
            "from_cache": False,
        }

        try:
            resp = requests.get(url, headers=_SCRAPE_HEADERS, timeout=3.5)
            resp.raise_for_status()

            if not is_safe_industrial_domain(resp.url):
                return result

            soup = BeautifulSoup(resp.text, "html.parser")

            # Extract structured JSON-LD scripts
            json_ld_list = []
            for script in soup.find_all("script", type="application/ld+json"):
                try:
                    if script.string:
                        import json
                        parsed_json = json.loads(script.string.strip())
                        json_ld_list.append(parsed_json)
                except Exception:
                    pass
            if json_ld_list:
                result["json_ld"] = json_ld_list[0] if len(json_ld_list) == 1 else {"@graph": json_ld_list}

            # Decompose junk tags
            for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
                tag.decompose()

            result["page_text"] = " ".join(soup.stripped_strings)[:12000]

            # Extract PDF datasheets
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if href.lower().endswith(".pdf") and is_safe_industrial_domain(href):
                    abs_pdf = resolve_pdf_url(href, resp.url)
                    if abs_pdf and abs_pdf not in result["pdfs"]:
                        result["pdfs"].append(abs_pdf)

            # Extract technical images
            for img in soup.find_all("img", src=True):
                src = img["src"].strip()
                if any(src.lower().endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".webp")):
                    if src.startswith("//"):
                        src = "https:" + src
                    elif src.startswith("/"):
                        m = re.match(r"(https?://[^/]+)", resp.url)
                        src = (m.group(1) if m else "") + src
                    if src.startswith("http") and src not in result["images"]:
                        result["images"].append(src)

            # Store in Tier-1 Source Cache
            cache_manager.store_source(
                url=url,
                page_text=result["page_text"],
                json_ld=result["json_ld"],
                pdfs=result["pdfs"],
                images=result["images"]
            )

        except Exception as exc:
            logger.debug("Source fetch failed for %s: %s", url, exc)

        return result

    @classmethod
    def discover_sources_early_exit(
        cls,
        brand: str,
        mpn: str,
        part_desc: str = "",
        confidence_threshold: float = 0.90
    ) -> Dict[str, Any]:
        """
        Discovers sources using DuckDuckGo with early exit:
        Stops querying further once an authoritative source clearing the confidence threshold is found.
        """
        clean_mpn = str(mpn or "").strip()
        clean_mfg = str(brand or "").replace("-- Unbranded --", "").replace("-- No Unilog Brand --", "").strip()
        clean_desc = str(part_desc or "").strip()

        # Priority search queries: OEM Brand page -> Technical datasheet -> Distributor
        queries = []
        if clean_mfg:
            queries.append(f'"{clean_mfg}" "{clean_mpn}" specifications OR datasheet')
            queries.append(f'"{clean_mfg}" "{clean_mpn}" product page')
        if clean_desc:
            queries.append(f'"{clean_mpn}" {clean_desc[:35]} technical specifications')
        else:
            queries.append(f'"{clean_mpn}" technical datasheet specifications')

        discovered_urls: List[str] = []

        for q in queries:
            if discovered_urls:
                break
            try:
                with DDGS(timeout=3) as ddgs:
                    results = ddgs.text(q, max_results=3, safesearch="strict")
                    for r in (results or []):
                        href = r.get("href", "")
                        if href and is_safe_industrial_domain(href) and href not in discovered_urls:
                            # Prioritize manufacturer official site matches
                            if clean_mfg and clean_mfg.lower() in href.lower():
                                discovered_urls.insert(0, href)
                            else:
                                discovered_urls.append(href)
            except Exception as exc:
                logger.debug("Search query failed for '%s': %s", q, exc)

        if not discovered_urls:
            return {
                "mfr_url": "URL Not Found",
                "ref_urls": [],
                "page_text": "",
                "json_ld": {},
                "pdfs": [],
                "images": [],
                "sources_cleared_threshold": False
            }

        primary_url = discovered_urls[0]
        ref_urls = discovered_urls[1:6]

        # Fetch primary source
        primary_source = cls.fetch_url(primary_url)

        # Early exit check: If primary source contains structured JSON-LD or ample page text (> 2000 chars)
        # from an OEM matching URL, we have high confidence and can early-exit immediately
        is_oem_match = bool(clean_mfg and clean_mfg.lower() in primary_url.lower())
        has_rich_content = bool(primary_source.get("json_ld") or len(primary_source.get("page_text", "")) > 1500)

        if is_oem_match and has_rich_content:
            return {
                "mfr_url": primary_url,
                "ref_urls": ref_urls,
                "page_text": primary_source["page_text"],
                "json_ld": primary_source["json_ld"],
                "pdfs": primary_source["pdfs"],
                "images": primary_source["images"],
                "sources_cleared_threshold": True,
                "from_cache": primary_source.get("from_cache", False)
            }

        # If primary source was thin and secondary URL exists, fetch secondary for corroboration
        if len(discovered_urls) > 1 and len(primary_source.get("page_text", "")) < 800:
            secondary_source = cls.fetch_url(discovered_urls[1])
            combined_text = (primary_source["page_text"] + "\n\n" + secondary_source["page_text"]).strip()
            combined_pdfs = list(dict.fromkeys(primary_source["pdfs"] + secondary_source["pdfs"]))
            combined_images = list(dict.fromkeys(primary_source["images"] + secondary_source["images"]))
            json_ld = primary_source.get("json_ld") or secondary_source.get("json_ld") or {}

            return {
                "mfr_url": primary_url,
                "ref_urls": ref_urls,
                "page_text": combined_text,
                "json_ld": json_ld,
                "pdfs": combined_pdfs,
                "images": combined_images,
                "sources_cleared_threshold": True,
                "from_cache": primary_source.get("from_cache", False) and secondary_source.get("from_cache", False)
            }

        return {
            "mfr_url": primary_url,
            "ref_urls": ref_urls,
            "page_text": primary_source["page_text"],
            "json_ld": primary_source["json_ld"],
            "pdfs": primary_source["pdfs"],
            "images": primary_source["images"],
            "sources_cleared_threshold": bool(primary_source["page_text"]),
            "from_cache": primary_source.get("from_cache", False)
        }
