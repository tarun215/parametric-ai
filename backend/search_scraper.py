"""
search_scraper.py — Parametric AI
Autonomous web sourcing: DuckDuckGo search + HTML scraper.
Safe, robust discovery using strict SafeSearch, OEM Domain prioritization, and technical resource validation.
Never fabricates, infers, or guesses URLs. If not found, outputs 'URL Not Found'.
"""

import logging
import re
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS

logger = logging.getLogger(__name__)

# ── 1. Marketplaces, Social Media, and Non-Technical Sites to Exclude ───────────────
NON_INDUSTRIAL_DOMAINS = [
    "amazon.", "ebay.", "walmart.", "target.", "bestbuy.", "flipkart.",
    "alibaba.", "aliexpress.", "etsy.", "overstock.", "costco.",
    "youtube.", "instagram.", "facebook.", "twitter.", "x.com", "tiktok.", "pinterest.",
    "bbc.", "cnn.", "wikipedia.", "yahoo.", "news.", "reddit.", "quora."
]

# ── 2. Trusted Standard TLDs ───────
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

_SCRAPE_TIMEOUT = 10
_MAX_PAGE_TEXT_CHARS = 8000
_MAX_DDG_RESULTS = 10


def _extract_core_brand(manufacturer: str, mpn: str) -> str:
    """Intelligently cleans strings like 'Freud Inc (2435)' -> 'freud'"""
    mfr = manufacturer or ""
    # Remove parentheses and corporate suffixes
    clean = re.sub(r"\(.*?\)", "", mfr).lower()
    clean = re.sub(r"\b(inc|llc|corp|corporation|company|co|gmbh|ltd|limited|holdings)\b", "", clean).strip()
    slug = re.sub(r"[^a-z0-9]", "", clean)

    # Check for prefix brands in MPN like "3MABR-1234" -> "3m"
    if "-" in mpn:
        prefix = mpn.split("-")[0].lower()
        if prefix.startswith("3m") or prefix in ("dewalt", "milw", "bosch"):
            return prefix

    return slug if len(slug) >= 2 else "industrial-supply"


def _is_safe_industrial_source(url: str, brand_slug: str = "") -> bool:
    """
    Validates that a URL is a legitimate product or technical resource:
    1. Excludes consumer marketplaces, social media, and spam.
    2. Ends in a valid standard TLD.
    """
    if not url or not url.startswith("http"):
        return False

    try:
        parsed = urlparse(url)
        netloc = parsed.netloc.lower()

        # Block consumer shopping/social junk
        if any(bad_site in netloc for bad_site in NON_INDUSTRIAL_DOMAINS):
            return False

        # Ensure standard commercial / institutional domain
        if not any(netloc.endswith(tld) or f"{tld}/" in url.lower() for tld in ALLOWED_TLDS):
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


def _scrape_url(url: str, brand_slug: str = "") -> dict:
    """Fetches and parses technical text and engineering PDFs from a target URL."""
    result = {"page_text": "", "pdfs": [], "images": []}

    if not url or not url.startswith("http") or not _is_safe_industrial_source(url, brand_slug):
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
                if src.startswith("//"):
                    src = "https:" + src
                elif src.startswith("/"):
                    m = re.match(r"(https?://[^/]+)", resp.url)
                    src = (m.group(1) if m else "") + src
                if src.startswith("http") and src not in result["images"]:
                    result["images"].append(src)

    except Exception as exc:
        logger.debug("Scrape skipped for %s: %s", url, exc)

    return result


def search_product_sources(manufacturer: str, mpn: str, part_desc: str = "") -> dict:
    """
    Autonomous discovery using DuckDuckGo Search and OEM domain prioritisation for ANY dataset.
    Never fabricates, infers, or guesses URLs. If no URL found, returns 'URL Not Found'.
    """
    output = {
        "mfr_url": "URL Not Found",
        "ref_urls": [],
        "page_text": "",
        "pdfs": [],
        "images": [],
    }

    clean_mpn = str(mpn or "").strip()
    clean_mfg = str(manufacturer or "").replace("-- Unbranded --", "").replace("-- No Unilog Brand --", "").replace("-- No DIB Brand --", "").strip()
    clean_desc = str(part_desc or "").strip()
    brand_slug = _extract_core_brand(clean_mfg, clean_mpn)

    # Multi-strategy search queries
    queries = []
    if clean_mfg and brand_slug != "industrial-supply":
        queries.extend([
            f'"{clean_mfg}" "{clean_mpn}" specifications OR datasheet',
            f'"{clean_mfg}" "{clean_mpn}" product page',
            f'{clean_mfg} {clean_mpn} {clean_desc[:30]} datasheet'
        ])
    elif clean_desc:
        queries.extend([
            f'"{clean_mpn}" {clean_desc[:40]} specifications',
            f'"{clean_mpn}" technical specifications datasheet',
            f'"{clean_mpn}" datasheet filetype:pdf'
        ])
    else:
        queries.extend([
            f'"{clean_mpn}" technical specifications datasheet',
            f'"{clean_mpn}" datasheet filetype:pdf',
            f'{clean_mpn} product support specifications'
        ])

    valid_urls = []

    for query in queries:
        if len(valid_urls) >= _MAX_DDG_RESULTS:
            break
        try:
            with DDGS() as ddgs:
                results = ddgs.text(query, max_results=_MAX_DDG_RESULTS, safesearch="strict")
                for r in (results or []):
                    href = r.get("href", "")
                    if href and _is_safe_industrial_source(href, brand_slug) and href not in valid_urls:
                        # Prioritize OEM/Brand matching URLs at the top
                        if brand_slug != "industrial-supply" and brand_slug in href.lower():
                            valid_urls.insert(0, href)
                        else:
                            valid_urls.append(href)
        except Exception as exc:
            logger.warning("Discovery query error for query '%s': %s", query, exc)

    if not valid_urls:
        output["mfr_url"] = "URL Not Found"
        output["ref_urls"] = []
        return output

    output["mfr_url"] = valid_urls[0]
    output["ref_urls"] = valid_urls[1:6]

    # Scrape primary URL
    scraped = _scrape_url(valid_urls[0], brand_slug)
    output["page_text"] = scraped["page_text"]
    output["pdfs"] = scraped["pdfs"]
    output["images"] = scraped["images"]

    # If page text is thin, scrape second valid URL
    if not output["page_text"].strip() and len(valid_urls) > 1:
        scraped2 = _scrape_url(valid_urls[1], brand_slug)
        if scraped2["page_text"]:
            output["page_text"] = scraped2["page_text"]
        output["pdfs"] = list(dict.fromkeys(output["pdfs"] + scraped2["pdfs"]))
        output["images"] = list(dict.fromkeys(output["images"] + scraped2["images"]))

    return output