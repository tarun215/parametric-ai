"""
search_scraper.py — Parametric AI
Autonomous web sourcing: DuckDuckGo search + HTML scraper.
Safe, robust discovery using strict SafeSearch, OEM Domain Locking, and standard TLD validation.
"""

import logging
import re
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS

logger = logging.getLogger(__name__)

# ── 1. Marketplaces, Social Media, and News Sites to Exclude ───────────────
NON_INDUSTRIAL_DOMAINS = [
    "amazon.", "ebay.", "walmart.", "target.", "bestbuy.", "flipkart.",
    "homedepot.", "lowes.", "grainger.", "zoro.", "globalindustrial.",
    "alibaba.", "aliexpress.", "etsy.", "overstock.", "costco.",
    "uline.", "mcmaster.", "fastenal.", "webstaurantstore.",
    "youtube.", "instagram.", "facebook.", "twitter.", "tiktok.", "pinterest.",
    "bbc.", "cnn.", "wikipedia.", "yahoo.", "news.", "reddit."
]

# ── 2. Trusted Standard TLDs (Blocks generic/spam internet extensions) ───────
ALLOWED_TLDS = {".com", ".org", ".net", ".io", ".co", ".us", ".ca", ".de", ".uk", ".in", ".edu", ".gov"}

_SCRAPE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

_SCRAPE_TIMEOUT = 10
_MAX_PAGE_TEXT_CHARS = 7000
_MAX_DDG_RESULTS = 10


def _extract_core_brand(manufacturer: str, mpn: str) -> str:
    """Intelligently cleans strings like 'Freud Inc (2435)' -> 'freud'"""
    mfr = manufacturer or ""
    # Remove parentheses and corporate suffixes
    clean = re.sub(r"\(.*?\)", "", mfr).lower()
    clean = re.sub(r"\b(inc|llc|corp|company)\b", "", clean).strip()
    slug = re.sub(r"[^a-z0-9]", "", clean)
    
    # Check for prefix brands in MPN like "3MABR-1234" -> "3m"
    if "-" in mpn:
        prefix = mpn.split("-")[0].lower()
        if prefix.startswith("3m"):
            return "3m"
            
    return slug if len(slug) > 2 else "industrial-supply"


def _is_safe_industrial_source(url: str, brand_slug: str) -> bool:
    """
    Validates that a URL is a legitimate resource:
    1. Excludes consumer marketplaces and social media.
    2. Must end in a standard trusted TLD.
    3. The domain MUST contain the brand name.
    """
    if not url or not url.startswith("http"):
        return False

    try:
        parsed = urlparse(url)
        netloc = parsed.netloc.lower()
        
        # Block marketplaces, social media, and irrelevant sites
        if any(bad_site in netloc for bad_site in NON_INDUSTRIAL_DOMAINS):
            return False

        # Ensure root domain ends with a standard institutional/commercial TLD
        if not any(netloc.endswith(tld) for tld in ALLOWED_TLDS):
            return False

        # THE OEM LOCK: Force the domain to actually contain the brand name
        if brand_slug and brand_slug != "industrial-supply":
            if brand_slug not in netloc:
                return False

        return True
    except Exception:
        return False


def _resolve_pdf_url(href: str, base_url: str) -> str:
    """Converts relative PDF paths to fully qualified URLs."""
    href = href.strip()
    if href.startswith("http://") or href.startswith("https://"):
        return href
    m = re.match(r"(https?://[^/]+)", base_url)
    origin = m.group(1) if m else ""
    if href.startswith("/"):
        return origin + href
    base_dir = base_url.rsplit("/", 1)[0]
    return base_dir.rstrip("/") + "/" + href


def _scrape_url(url: str, brand_slug: str) -> dict:
    """Fetches and parses technical text and engineering PDFs from a target URL."""
    result = {"page_text": "", "pdfs": [], "images": []}
    
    if not _is_safe_industrial_source(url, brand_slug):
        return result

    try:
        resp = requests.get(url, headers=_SCRAPE_HEADERS, timeout=_SCRAPE_TIMEOUT)
        resp.raise_for_status()

        if not _is_safe_industrial_source(resp.url, brand_slug):
            return result

        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
            tag.decompose()

        result["page_text"] = " ".join(soup.stripped_strings)[:_MAX_PAGE_TEXT_CHARS]

        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.lower().endswith(".pdf") and _is_safe_industrial_source(href, brand_slug):
                abs_pdf = _resolve_pdf_url(href, resp.url)
                if abs_pdf and abs_pdf not in result["pdfs"]:
                    result["pdfs"].append(abs_pdf)

        for img in soup.find_all("img", src=True):
            src = img["src"].strip()
            if any(src.lower().endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".webp")):
                if src.startswith("http") and src not in result["images"]:
                    result["images"].append(src)

    except Exception as exc:
        logger.debug("Scrape skipped for %s: %s", url, exc)

    return result


def search_product_sources(manufacturer: str, mpn: str) -> dict:
    """
    Autonomous discovery using Strict DuckDuckGo Filtering and OEM domain fallbacks.
    """
    output = {
        "mfr_url": "",
        "ref_urls": [],
        "page_text": "",
        "pdfs": [],
        "images": [],
    }

    # Extract clean brand slug (e.g., "freud", "3m", "whirlpool")
    brand_slug = _extract_core_brand(manufacturer, mpn)

    # Broadened search queries to ensure real results are returned
    queries = [
        f'"{brand_slug}" "{mpn}" product support OR specifications',
        f'"{brand_slug}" "{mpn}" technical specifications',
        f'"{mpn}" specification sheet filetype:pdf'
    ]

    valid_urls = []

    for query in queries:
        if len(valid_urls) >= _MAX_DDG_RESULTS:
            break
        try:
            with DDGS() as ddgs:
                # Enforce Strict SafeSearch at the search engine level
                results = ddgs.text(query, max_results=_MAX_DDG_RESULTS, safesearch="strict")
                
                for r in (results or []):
                    href = r.get("href", "")
                    # Apply the OEM Domain Lock
                    if href and _is_safe_industrial_source(href, brand_slug) and href not in valid_urls:
                        valid_urls.append(href)
        except Exception as exc:
            logger.warning("Discovery query error: %s", exc)

    # Smart OEM Fallback if search engine fails entirely
    if not valid_urls:
        valid_urls = [
            f"https://www.{brand_slug}.com/products/{mpn}",
            f"https://www.{brand_slug}.com/specs/{mpn}-datasheet.pdf",
            f"https://www.{brand_slug}.com/catalog/{mpn}",
            f"https://www.{brand_slug}.com/support/{mpn}",
            f"https://www.{brand_slug}.com/documentation/{mpn}"
        ]

    output["mfr_url"] = valid_urls[0]
    output["ref_urls"] = valid_urls[1:6]

    # Pass the brand_slug into the scraper to ensure redirects stay locked
    scraped = _scrape_url(valid_urls[0], brand_slug)
    output["page_text"] = scraped["page_text"]
    output["pdfs"] = scraped["pdfs"]
    output["images"] = scraped["images"]

    if not output["page_text"].strip() and len(valid_urls) > 1:
        scraped2 = _scrape_url(valid_urls[1], brand_slug)
        output["page_text"] = scraped2["page_text"]
        output["pdfs"] = output["pdfs"] or scraped2["pdfs"]
        output["images"] = output["images"] or scraped2["images"]

    return output