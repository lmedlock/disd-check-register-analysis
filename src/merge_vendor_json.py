"""
Merge per-vendor JSON files downloaded by browser_capture.js (or
browser_capture_retry.js) into contract_awards_raw.json.

Usage:
  python -m src.merge_vendor_json                     # reads from ~/Downloads
  python -m src.merge_vendor_json --source ~/Desktop  # custom directory
"""

import argparse
import json
from pathlib import Path

VENDORS_DIR = Path("data/vendors")
OUTPUT_FILE  = VENDORS_DIR / "contract_awards_raw.json"
EDTECH_FILE  = VENDORS_DIR / "edtech_research_v2.json"


def load_cache() -> dict:
    if not OUTPUT_FILE.exists():
        return {}
    with open(OUTPUT_FILE) as f:
        data = json.load(f)
    if isinstance(data, list):
        return {e["vendor_name"]: e for e in data}
    return data


def is_vendor_capture(data) -> bool:
    return (
        isinstance(data, dict)
        and "vendor_name" in data
        and "awards" in data
        and "scraped_at" in data
    )


def merge(source_dir: Path) -> None:
    json_files = sorted(source_dir.glob("*.json"))
    if not json_files:
        print(f"No .json files found in {source_dir}")
        return

    print(f"Scanning {len(json_files)} JSON file(s) in {source_dir}\n")

    cache = load_cache()
    added = updated = skipped = 0

    for path in json_files:
        try:
            with open(path) as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"  [skip] {path.name}: {e}")
            skipped += 1
            continue

        if not is_vendor_capture(data):
            skipped += 1
            continue

        vendor_name = data["vendor_name"]
        award_count = len(data.get("awards", []))
        error       = data.get("error") or ""

        status = f"{award_count} award(s)" if not error else f"error: {error}"

        if vendor_name in cache:
            print(f"  [update] {vendor_name} — {status}")
            updated += 1
        else:
            print(f"  [add]    {vendor_name} — {status}")
            added += 1

        cache[vendor_name] = data

    VENDORS_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(list(cache.values()), f, indent=2, default=str)

    print(f"\nWrote {len(cache)} vendor(s) → {OUTPUT_FILE}")
    print(f"  Added: {added}  Updated: {updated}  Skipped (non-vendor files): {skipped}")

    _report_coverage(cache)


def _report_coverage(cache: dict) -> None:
    if not EDTECH_FILE.exists():
        return

    with open(EDTECH_FILE) as f:
        all_vendors = [e["vendor_name"] for e in json.load(f)]

    captured    = [v for v in all_vendors if v in cache and not cache[v].get("error")]
    not_in_db   = [v for v in all_vendors if cache.get(v, {}).get("error") == "not_in_procurement_database"]
    still_missing = [v for v in all_vendors if v not in cache]

    print(f"\nCoverage:")
    print(f"  {len(captured):2d} captured with awards")
    print(f"  {len(not_in_db):2d} confirmed not in procurement database")
    print(f"  {len(still_missing):2d} still missing")

    if still_missing:
        print("\nStill missing — run browser_capture_retry.js for these:")
        for v in still_missing:
            print(f"  • {v}")
    else:
        print("\nAll vendors accounted for. Run the enrichment step:")
        print("  python -m src.contract_enrichment")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source", "-s",
        type=Path,
        default=Path.home() / "Downloads",
        help="Directory containing downloaded vendor JSON files (default: ~/Downloads)",
    )
    args = parser.parse_args()

    if not args.source.exists():
        print(f"Source directory not found: {args.source}")
    else:
        merge(args.source)
