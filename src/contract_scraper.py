"""
Dallas ISD Procurement Contract Scraper

Scrapes awarded vendor contract data from:
  https://www2.dallasisd.org/inside_disd/depts/business/support/purchasing/

For each vendor in edtech_research_v2.json:
  1. Autocomplete search to find exact site vendor name
  2. Parse awards table (category code, description, award description)
  3. Follow detail links to get contract effective/end dates

Output: data/vendors/contract_awards_raw.json
  - Results are cached per-vendor; re-runs skip already-scraped vendors
  - Use --force to re-scrape all

Usage:
  python -m src.contract_scraper
  python -m src.contract_scraper --force
"""

import argparse
import difflib
import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout, sync_playwright

# ── Configuration ─────────────────────────────────────────────────────────────

BASE_URL = "https://www2.dallasisd.org/inside_disd/depts/business/support/purchasing"
SEARCH_URL = f"{BASE_URL}/searchbyvendor.cfm"

VENDOR_DELAY_S = 2.5    # pause between vendors
DETAIL_DELAY_S = 0.75   # pause between detail page fetches
AUTOCOMPLETE_TIMEOUT_MS = 3000
PAGE_TIMEOUT_MS = 20_000

DATA_DIR = Path("data/vendors")
CACHE_FILE = DATA_DIR / "contract_awards_raw.json"
EDTECH_FILE = DATA_DIR / "edtech_research_v2.json"

# ── Cache helpers ─────────────────────────────────────────────────────────────


def load_cache() -> dict:
    """Load existing cached results keyed by vendor_name."""
    if not CACHE_FILE.exists():
        return {}
    with open(CACHE_FILE) as f:
        data = json.load(f)
    # Support both list (old) and dict (current) format
    if isinstance(data, list):
        return {entry["vendor_name"]: entry for entry in data}
    return data


def save_cache(cache: dict) -> None:
    """Write cache to disk as a list (one entry per vendor)."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, "w") as f:
        json.dump(list(cache.values()), f, indent=2, default=str)


# ── Matching helpers ──────────────────────────────────────────────────────────


def best_fuzzy_match(query: str, candidates: list[str]) -> Optional[str]:
    """
    Return the best fuzzy match for query among candidates.
    Returns None if the best ratio is below 0.5.
    """
    if not candidates:
        return None
    query_lower = query.lower()
    # Exact match first
    for c in candidates:
        if c.lower() == query_lower:
            return c
    scores = [
        (c, difflib.SequenceMatcher(None, query_lower, c.lower()).ratio())
        for c in candidates
    ]
    best, ratio = max(scores, key=lambda x: x[1])
    return best if ratio >= 0.5 else None


def _autocomplete_prefix(vendor_name: str) -> str:
    """
    Choose a search prefix: first word if >= 4 chars, else first 5 chars.
    For common words like "EDUCATION" that match many vendors, uses more.
    """
    parts = vendor_name.split()
    first_word = parts[0]
    # If first word is very generic and we have a second word, use first two
    generic_first = {"EDUCATION", "EDUCATIONAL", "LEARNING", "ALL", "ENGAGE", "ABOVE"}
    if first_word.upper() in generic_first and len(parts) > 1:
        return f"{first_word} {parts[1][:3]}"
    return first_word if len(first_word) >= 4 else vendor_name[:5]


# ── Page interaction ──────────────────────────────────────────────────────────


def find_site_vendor_name(page: Page, vendor_name: str) -> Optional[str]:
    """
    Type the prefix into the search input, wait for autocomplete, and return
    the best-matching site vendor name. Returns None if nothing found.
    """
    prefix = _autocomplete_prefix(vendor_name)

    try:
        page.goto(SEARCH_URL, wait_until="networkidle", timeout=PAGE_TIMEOUT_MS)
    except PlaywrightTimeout:
        print(f"  [!] Timeout loading search page — server may be unreachable")
        return None

    # Clear and type the prefix slowly to trigger autocomplete
    field = page.locator("#vendorname")
    field.fill("")
    field.type(prefix, delay=80)

    try:
        page.wait_for_selector(
            "ul.ui-autocomplete li.ui-menu-item",
            state="visible",
            timeout=AUTOCOMPLETE_TIMEOUT_MS,
        )
    except PlaywrightTimeout:
        print(f"  [!] No autocomplete results for prefix '{prefix}'")
        return None

    items = [
        el.inner_text().strip()
        for el in page.locator("ul.ui-autocomplete li.ui-menu-item").all()
        if el.inner_text().strip()
    ]
    print(f"  Autocomplete: {len(items)} option(s) for '{prefix}'")

    matched = best_fuzzy_match(vendor_name, items)
    if not matched:
        print(f"  [!] No match (threshold 0.5) among: {items[:5]}")
        return None

    print(f"  Matched site name: '{matched}'")
    return matched


def get_vendor_awards(page: Page, site_vendor_name: str) -> list[dict]:
    """
    Submit the search form with the exact site vendor name and parse the
    resulting awards table.

    Returns list of dicts with keys:
      category_code, category_description, award_description, detail_url
    """
    try:
        page.goto(SEARCH_URL, wait_until="networkidle", timeout=PAGE_TIMEOUT_MS)
    except PlaywrightTimeout:
        print("  [!] Timeout loading search page for form submission")
        return []

    page.locator("#vendorname").fill(site_vendor_name)

    with page.expect_navigation(wait_until="networkidle", timeout=PAGE_TIMEOUT_MS):
        page.locator("input[type='submit']").click()

    awards = []
    tables = page.locator("table").all()

    for table in tables:
        rows = table.locator("tr").all()
        if len(rows) < 2:
            continue

        header_text = rows[0].inner_text().lower()
        if "category" not in header_text and "award" not in header_text:
            continue

        for row in rows[1:]:
            cells = row.locator("td").all()
            if len(cells) < 2:
                continue

            texts = [c.inner_text().strip() for c in cells]

            # Attempt to extract the detail link from the category description cell
            detail_url = None
            link = cells[1].locator("a").first
            if link.count() > 0:
                href = link.get_attribute("href") or ""
                if href:
                    detail_url = (
                        href if href.startswith("http")
                        else f"{BASE_URL}/{href.lstrip('/')}"
                    )

            award = {
                "category_code": texts[0] if len(texts) > 0 else "",
                "category_description": texts[1] if len(texts) > 1 else "",
                "award_description": texts[2] if len(texts) > 2 else "",
                "detail_url": detail_url,
            }
            if any(award[k] for k in ("category_code", "category_description", "award_description")):
                awards.append(award)

        break  # Only parse the first matching table

    print(f"  Found {len(awards)} award(s)")
    return awards


_DATE_LABEL_RE = re.compile(
    r"(effective\s*date|start\s*date|end\s*date|expir\w*)"
    r"[:\s]*"
    r"(\d{1,2}/\d{1,2}/\d{2,4}|\d{4}-\d{2}-\d{2})",
    re.IGNORECASE,
)


def get_award_detail(page: Page, detail_url: str) -> dict:
    """
    Fetch an award detail page and extract effective_date and end_date.
    Returns dict with those keys (values may be None on failure).
    """
    try:
        page.goto(detail_url, wait_until="networkidle", timeout=PAGE_TIMEOUT_MS)
    except PlaywrightTimeout:
        return {"effective_date": None, "end_date": None, "detail_error": "timeout"}

    content = page.inner_text("body")
    dates: dict[str, Optional[str]] = {}

    for m in _DATE_LABEL_RE.finditer(content):
        label, raw_date = m.group(1).lower(), m.group(2)

        key = "effective_date" if any(w in label for w in ("effective", "start")) else "end_date"
        if key in dates:
            continue  # First match wins

        normalized = _normalize_date(raw_date)
        if normalized:
            dates[key] = normalized

    return {
        "effective_date": dates.get("effective_date"),
        "end_date": dates.get("end_date"),
    }


def _normalize_date(raw: str) -> Optional[str]:
    for fmt in ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


# ── Per-vendor orchestration ──────────────────────────────────────────────────


def scrape_vendor(page: Page, vendor_name: str) -> dict:
    """Run the full scrape pipeline for a single vendor. Returns result dict."""
    print(f"\nScraping: {vendor_name}")

    result: dict = {
        "vendor_name": vendor_name,
        "scraped_at": datetime.now().isoformat(),
        "site_vendor_name": None,
        "awards": [],
        "error": None,
    }

    try:
        site_name = find_site_vendor_name(page, vendor_name)
        if not site_name:
            result["error"] = "no_autocomplete_match"
            return result

        result["site_vendor_name"] = site_name

        awards = get_vendor_awards(page, site_name)

        for award in awards:
            time.sleep(DETAIL_DELAY_S)
            if award.get("detail_url"):
                detail = get_award_detail(page, award["detail_url"])
                award.update(detail)
            award.pop("detail_url", None)

        result["awards"] = awards

    except Exception as e:
        result["error"] = str(e)
        print(f"  [ERROR] {e}")

    return result


# ── Main entry point ──────────────────────────────────────────────────────────


def scrape_all_vendors(force_refresh: bool = False) -> None:
    """
    Scrape contract data for all vendors in edtech_research_v2.json.
    Skips vendors already in cache unless force_refresh=True.
    Saves cache after every vendor so progress is never lost.
    """
    with open(EDTECH_FILE) as f:
        vendors = [entry["vendor_name"] for entry in json.load(f)]

    cache = load_cache()
    to_scrape = [v for v in vendors if force_refresh or v not in cache]

    print(f"Vendors to scrape : {len(to_scrape)}")
    print(f"Already cached    : {len(vendors) - len(to_scrape)}")

    if not to_scrape:
        print("All vendors already cached. Use --force to re-scrape.")
        _print_summary(cache, vendors)
        return

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )
        page = context.new_page()

        for i, vendor_name in enumerate(to_scrape):
            result = scrape_vendor(page, vendor_name)
            cache[vendor_name] = result
            save_cache(cache)  # persist after every vendor

            if i < len(to_scrape) - 1:
                print(f"  Waiting {VENDOR_DELAY_S}s before next vendor...")
                time.sleep(VENDOR_DELAY_S)

        browser.close()

    print(f"\nDone. Cache saved to {CACHE_FILE}")
    _print_summary(cache, vendors)


def _print_summary(cache: dict, all_vendors: list[str]) -> None:
    matched = sum(1 for v in all_vendors if cache.get(v, {}).get("site_vendor_name"))
    errored = sum(1 for v in all_vendors if cache.get(v, {}).get("error"))
    total_awards = sum(
        len(cache.get(v, {}).get("awards", [])) for v in all_vendors
    )
    print(f"\nSummary: {matched}/{len(all_vendors)} vendors matched on site | "
          f"{errored} errors | {total_awards} total awards found")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape Dallas ISD contract awards for EdTech vendors")
    parser.add_argument(
        "--force", action="store_true",
        help="Re-scrape all vendors, ignoring cached results"
    )
    args = parser.parse_args()
    scrape_all_vendors(force_refresh=args.force)
