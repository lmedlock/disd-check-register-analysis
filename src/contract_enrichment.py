"""
Contract Award Enrichment

Combines:
  - edtech_research_v2.json      (vendor research / replaceability scores)
  - contract_awards_raw.json     (scraped Dallas ISD procurement data)
  - all_transactions_raw.csv     (check register transactions)

Produces: data/vendors/edtech_award_spend_v1.json

Each vendor entry preserves all edtech_research_v2 fields and adds:
  fund_breakdown      — spending aggregated by fund code
  transactions        — individual check-level records (date, amount, fund) for
                        experienced readers to cross-reference against awards
  matched_awards      — awards whose date ranges overlap the check register window,
                        annotated with overlap_status and matched_spending
  unmatched_awards    — awards entirely outside the check register window (for reference)

Overlap statuses:
  completed       — award dates fully within 2021-09-01 → 2025-08-31
  ongoing         — contract extends past 2025-08-31 (spending shown is partial)
  predates_data   — contract started before 2021-09-01 (earlier spend not captured)
  spanning        — contract both predates start AND extends past end
  no_overlap      — award dates are entirely outside the register window
  unknown         — date information not available from the procurement site

Usage:
  python -m src.contract_enrichment
"""

import json
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import pandas as pd

# ── Path resolution (supports running from project root or src/) ───────────────
_SRC_DIR = Path(__file__).parent
sys.path.insert(0, str(_SRC_DIR))
from fund_analysis import add_fund_codes_to_transactions, get_fund_info

# ── Paths ─────────────────────────────────────────────────────────────────────
DATA_DIR = Path("data")
VENDORS_DIR = DATA_DIR / "vendors"
EDTECH_FILE = VENDORS_DIR / "edtech_research_v2.json"
AWARDS_FILE = VENDORS_DIR / "contract_awards_raw.json"
TRANSACTIONS_FILE = DATA_DIR / "extracted" / "all_transactions_raw.csv"
OUTPUT_FILE = VENDORS_DIR / "edtech_award_spend_v1.json"

# The date span covered by our check register data
REGISTER_START = date(2021, 9, 1)
REGISTER_END = date(2025, 8, 31)


# ── Date utilities ────────────────────────────────────────────────────────────


def _parse_date(ds: Optional[str]) -> Optional[date]:
    if not ds:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(ds, fmt).date()
        except ValueError:
            continue
    return None


# ── Overlap classification ────────────────────────────────────────────────────


def classify_overlap(effective_date: Optional[str], end_date: Optional[str]) -> dict:
    """
    Classify how an award's date range relates to the check register window.

    Returns dict with:
      overlap_status  — one of: completed | ongoing | predates_data | spanning |
                                no_overlap | unknown
      overlap_note    — human-readable explanation
    """
    eff = _parse_date(effective_date)
    end = _parse_date(end_date)

    # Both dates missing — can't classify
    if eff is None and end is None:
        return {
            "overlap_status": "unknown",
            "overlap_note": "Contract dates not available from procurement site.",
        }

    # If we have end date and it's before the register starts → no overlap
    if end is not None and end < REGISTER_START:
        return {
            "overlap_status": "no_overlap",
            "overlap_note": (
                f"Award ended {end_date}, before check register start "
                f"({REGISTER_START}). Excluded from spending analysis."
            ),
        }

    # If we have effective date and it's after the register ends → no overlap
    if eff is not None and eff > REGISTER_END:
        return {
            "overlap_status": "no_overlap",
            "overlap_note": (
                f"Award began {effective_date}, after check register end "
                f"({REGISTER_END}). Excluded from spending analysis."
            ),
        }

    # Award spans our entire window (started before AND ends after)
    if (eff is not None and eff < REGISTER_START) and (end is not None and end > REGISTER_END):
        return {
            "overlap_status": "spanning",
            "overlap_note": (
                f"Contract spans {effective_date}–{end_date}, covering the entire "
                f"check register window ({REGISTER_START}–{REGISTER_END}). "
                f"Spending predating {REGISTER_START} is not captured, and the "
                f"contract extends beyond our data — award is not yet complete."
            ),
        }

    # Contract predates our data (started before, ended within)
    if eff is not None and eff < REGISTER_START:
        return {
            "overlap_status": "predates_data",
            "overlap_note": (
                f"Contract began {effective_date}, before the check register start "
                f"({REGISTER_START}). Spending prior to {REGISTER_START} is not "
                f"captured in this dataset."
            ),
        }

    # Contract extends past our data (started within, ends after)
    if end is None or end > REGISTER_END:
        end_label = end_date if end_date else "unknown"
        return {
            "overlap_status": "ongoing",
            "overlap_note": (
                f"Contract runs to {end_label}, beyond the check register end "
                f"({REGISTER_END}). Spending shown is partial — this award is "
                f"not yet complete."
            ),
        }

    # Award fully within our window
    return {
        "overlap_status": "completed",
        "overlap_note": (
            f"Award dates ({effective_date}–{end_date}) fall fully within the "
            f"check register window. All spending under this award should be captured."
        ),
    }


# ── Transaction helpers ───────────────────────────────────────────────────────


def load_transactions() -> pd.DataFrame:
    df = pd.read_csv(TRANSACTIONS_FILE, parse_dates=["date"])
    df = add_fund_codes_to_transactions(df)
    return df


def build_fund_breakdown(vendor_tx: pd.DataFrame) -> dict:
    """Aggregate spending by fund code, sorted by amount descending."""
    breakdown: dict = {}
    for fund_code, group in vendor_tx.groupby("fund_code"):
        info = get_fund_info(str(fund_code))
        breakdown[str(fund_code)] = {
            "fund_name": info["name"],
            "fund_category": info.get("category", "unknown"),
            "amount": round(float(group["amount"].sum()), 2),
            "tx_count": int(len(group)),
        }
    return dict(
        sorted(breakdown.items(), key=lambda x: x[1]["amount"], reverse=True)
    )


def build_transaction_list(vendor_tx: pd.DataFrame) -> list[dict]:
    """
    Individual check-level records sorted by date.
    Intended for experienced readers to cross-reference specific payments
    against award date ranges. No conclusions about which check funded
    which award are drawn here.
    """
    records = []
    for _, row in vendor_tx.sort_values("date").iterrows():
        fund_code = str(row.get("fund_code", "")) if pd.notna(row.get("fund_code")) else ""
        fund_name = get_fund_info(fund_code)["name"] if fund_code else "Unknown"
        records.append({
            "date": row["date"].strftime("%Y-%m-%d") if pd.notna(row["date"]) else None,
            "amount": round(float(row["amount"]), 2),
            "fund_code": fund_code,
            "fund_name": fund_name,
            "check_number": str(row.get("check_number", "")),
        })
    return records


def matched_spending_for_award(
    vendor_tx: pd.DataFrame,
    effective_date: Optional[str],
    end_date: Optional[str],
) -> tuple[float, int]:
    """
    Sum of transactions whose check dates fall within [effective_date, end_date],
    clamped to the check register window as the outer bound.

    Returns (total_amount, tx_count).
    Note: if multiple awards overlap the same period, their matched_spending
    figures will reflect the same underlying transactions.
    """
    eff_ts = pd.Timestamp(_parse_date(effective_date) or REGISTER_START)
    end_ts = pd.Timestamp(_parse_date(end_date) or REGISTER_END)

    # Clamp to the check register window
    eff_ts = max(eff_ts, pd.Timestamp(REGISTER_START))
    end_ts = min(end_ts, pd.Timestamp(REGISTER_END))

    mask = (vendor_tx["date"] >= eff_ts) & (vendor_tx["date"] <= end_ts)
    subset = vendor_tx[mask]
    return round(float(subset["amount"].sum()), 2), int(len(subset))


# ── Enrichment pipeline ───────────────────────────────────────────────────────


def enrich_vendor(
    vendor_entry: dict,
    awards_lookup: dict,
    vendor_tx: pd.DataFrame,
) -> dict:
    """Build the enriched record for a single vendor."""
    vendor_name = vendor_entry["vendor_name"]
    raw = awards_lookup.get(vendor_name, {})

    fund_breakdown = build_fund_breakdown(vendor_tx) if len(vendor_tx) > 0 else {}
    transactions = build_transaction_list(vendor_tx) if len(vendor_tx) > 0 else []

    matched_awards: list[dict] = []
    unmatched_awards: list[dict] = []

    for award in raw.get("awards", []):
        eff_date = award.get("effective_date")
        end_date = award.get("end_date")
        overlap = classify_overlap(eff_date, end_date)

        enriched_award = {
            "category_code": award.get("category_code", ""),
            "category_description": award.get("category_description", ""),
            "award_description": award.get("award_description", ""),
            "effective_date": eff_date,
            "end_date": end_date,
            **overlap,
        }

        if overlap["overlap_status"] == "no_overlap":
            unmatched_awards.append(enriched_award)
        else:
            amt, cnt = matched_spending_for_award(vendor_tx, eff_date, end_date)
            enriched_award["matched_spending"] = amt
            enriched_award["matched_tx_count"] = cnt
            matched_awards.append(enriched_award)

    # If vendor has multiple overlapping awards, note the attribution ambiguity
    if len(matched_awards) > 1:
        note = (
            f"This vendor has {len(matched_awards)} awards that overlap the "
            f"check register window. Matched spending reflects all checks within "
            f"each award's date range and cannot be attributed exclusively to "
            f"any single award."
        )
        for a in matched_awards:
            a["multi_award_note"] = note

    # Detect vendors with spending but only post-register awards — indicates
    # money was spent under prior contract cycles not in the procurement DB
    contract_coverage_note = None
    total_spend = float(vendor_tx["amount"].sum()) if len(vendor_tx) > 0 else 0.0
    if total_spend > 0 and not matched_awards and unmatched_awards:
        earliest_award = min(
            (a["effective_date"] for a in unmatched_awards if a.get("effective_date")),
            default=None,
        )
        contract_coverage_note = (
            f"Vendor has ${total_spend:,.0f} in spending but all procurement awards "
            f"in the Dallas ISD database post-date the check register "
            f"(earliest award: {earliest_award}). Spending likely occurred under "
            f"prior contract cycles that are no longer listed in the procurement system."
        )

    return {
        **vendor_entry,
        # Recalculate total_spending from actual transaction data
        "total_spending": round(float(vendor_tx["amount"].sum()), 2) if len(vendor_tx) > 0 else 0.0,
        # Contract scrape metadata
        "contract_data_scraped_at": raw.get("scraped_at"),
        "site_vendor_name": raw.get("site_vendor_name"),
        "scrape_error": raw.get("error"),
        # New enrichment fields
        "contract_coverage_note": contract_coverage_note,
        "fund_breakdown": fund_breakdown,
        "transactions": transactions,
        "matched_awards": matched_awards,
        "unmatched_awards": unmatched_awards,
    }


def enrich() -> None:
    """Main pipeline: load all inputs, enrich each vendor, write output."""
    print("Loading edtech vendor research...")
    with open(EDTECH_FILE) as f:
        edtech_data: list[dict] = json.load(f)

    if not AWARDS_FILE.exists():
        print(
            f"ERROR: {AWARDS_FILE} not found.\n"
            "Run the scraper first:\n"
            "  python -m src.contract_scraper"
        )
        sys.exit(1)

    print("Loading contract awards cache...")
    with open(AWARDS_FILE) as f:
        raw_awards = json.load(f)
    awards_lookup = {entry["vendor_name"]: entry for entry in raw_awards}

    print("Loading transaction data...")
    tx_df = load_transactions()

    output: list[dict] = []
    for vendor_entry in edtech_data:
        vendor_name = vendor_entry["vendor_name"]
        print(f"  Enriching: {vendor_name}")
        vendor_tx = tx_df[tx_df["vendor"] == vendor_name].copy()
        record = enrich_vendor(vendor_entry, awards_lookup, vendor_tx)
        output.append(record)

    VENDORS_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2, default=str)

    print(f"\nSaved {len(output)} vendors → {OUTPUT_FILE}")
    _print_summary(output)


def _print_summary(output: list[dict]) -> None:
    with_awards   = sum(1 for v in output if v.get("matched_awards"))
    prior_cycle   = sum(1 for v in output if v.get("contract_coverage_note"))
    not_in_db     = sum(1 for v in output if v.get("scrape_error") == "not_in_procurement_database")
    other_errors  = sum(1 for v in output if v.get("scrape_error") and v.get("scrape_error") != "not_in_procurement_database")

    statuses: dict[str, int] = {}
    for v in output:
        for a in v.get("matched_awards", []):
            s = a.get("overlap_status", "unknown")
            statuses[s] = statuses.get(s, 0) + 1

    print(f"\nEnrichment summary:")
    print(f"  {len(output)} vendors processed")
    print(f"  {with_awards} vendors with matched award data")
    print(f"  {prior_cycle} vendors with spending but only post-register awards (prior contract cycles)")
    print(f"  {not_in_db} vendors not found in procurement database")
    print(f"  {other_errors} other scrape errors")
    print(f"  Award overlap breakdown:")
    for status, count in sorted(statuses.items()):
        print(f"    {status:20s} {count}")


if __name__ == "__main__":
    enrich()
