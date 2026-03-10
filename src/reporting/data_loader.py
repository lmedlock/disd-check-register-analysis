"""
Data loader for EdTech spending report.

Loads and prepares data from various sources for report generation.
Supports both legacy (4-level) and v2 (5-dimension) research formats.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pandas as pd


# Dimension weights for composite score calculation
DIMENSION_WEIGHTS = {
    'technical_buildability': 0.25,
    'content_ip': 0.25,
    'switching_cost': 0.20,
    'market_alternatives': 0.15,
    'data_portability': 0.15,
}

# Replaceability levels with score ranges
REPLACEABILITY_LEVELS = ['high', 'medium', 'low', 'very_low', 'none', 'unknown']


@dataclass
class DimensionMetrics:
    """Aggregate metrics for each scoring dimension."""
    average_scores: dict[str, float] = field(default_factory=dict)
    score_distributions: dict[str, dict[int, int]] = field(default_factory=dict)


@dataclass
class ReportData:
    """Container for all report data."""

    # Researched vendors with replaceability ratings
    researched_vendors: list[dict]

    # All EdTech vendors with spending and priority
    edtech_vendors_df: pd.DataFrame

    # All vendors with categories
    all_vendors_df: pd.DataFrame

    # Raw transactions for time series
    transactions_df: pd.DataFrame

    # Computed metrics
    total_edtech_spending: float
    total_vendor_count: int
    top_25_spending: float
    top_25_concentration: float

    # Replaceability metrics (legacy format support)
    replaceability_spending: dict[str, float]
    replaceability_counts: dict[str, int]

    # V2 format: dimension-level metrics
    dimension_metrics: Optional[DimensionMetrics] = None

    # V2 format: classification breakdown
    classification_counts: dict[str, int] = field(default_factory=dict)
    classification_spending: dict[str, float] = field(default_factory=dict)

    # V2 format: criticality breakdown
    criticality_counts: dict[str, int] = field(default_factory=dict)
    criticality_spending: dict[str, float] = field(default_factory=dict)

    # Format version flag
    is_v2_format: bool = False


def _detect_v2_format(vendors: list[dict]) -> bool:
    """Check if vendor data is in v2 multi-dimensional format."""
    if not vendors:
        return False
    first_vendor = vendors[0]
    return 'scores' in first_vendor and 'composite_score' in first_vendor


def _calculate_dimension_metrics(vendors: list[dict]) -> DimensionMetrics:
    """Calculate aggregate metrics for each scoring dimension."""
    dimensions = ['technical_buildability', 'content_ip', 'switching_cost',
                  'market_alternatives', 'data_portability']

    average_scores = {}
    score_distributions = {}

    for dim in dimensions:
        scores = []
        distribution = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0}

        for vendor in vendors:
            vendor_scores = vendor.get('scores', {})
            score = vendor_scores.get(dim, 0)
            if score > 0:  # Only include non-zero scores in average
                scores.append(score)
            distribution[score] = distribution.get(score, 0) + 1

        average_scores[dim] = sum(scores) / len(scores) if scores else 0
        score_distributions[dim] = distribution

    return DimensionMetrics(
        average_scores=average_scores,
        score_distributions=score_distributions
    )


def load_report_data(data_dir: Optional[Path] = None, use_v2: bool = True) -> ReportData:
    """
    Load all data sources for the report.

    Args:
        data_dir: Base data directory. Defaults to 'data/' relative to project root.
        use_v2: If True, prefer v2 format file if available.

    Returns:
        ReportData containing all loaded and computed data.
    """
    if data_dir is None:
        # Find project root by looking for 'data' directory with expected structure
        current = Path(__file__).resolve().parent
        while current.parent != current:
            potential_data = current / 'data'
            if potential_data.exists() and (potential_data / 'vendors').exists():
                data_dir = potential_data
                break
            current = current.parent
        else:
            raise FileNotFoundError("Could not find data directory with vendors subdirectory")

    data_dir = Path(data_dir)

    # Determine which research file to load.
    # Prefer the enriched file (has fund_breakdown, matched_awards, etc.)
    # over the bare research file.
    enriched_path = data_dir / 'vendors' / 'edtech_award_spend_v1.json'
    v2_path = data_dir / 'vendors' / 'edtech_research_v2.json'
    legacy_path = data_dir / 'vendors' / 'edtech_research_pass2_high.json'

    if use_v2 and enriched_path.exists():
        research_path = enriched_path
    elif use_v2 and v2_path.exists():
        research_path = v2_path
    else:
        research_path = legacy_path

    with open(research_path, 'r') as f:
        researched_vendors = json.load(f)

    is_v2_format = _detect_v2_format(researched_vendors)

    # Load EdTech vendors CSV
    edtech_path = data_dir / 'vendors' / 'edtech_vendors_for_research.csv'
    edtech_vendors_df = pd.read_csv(edtech_path)

    # Load all vendors categorization
    all_vendors_path = data_dir / 'vendors' / 'vendor_categorization_pass1.csv'
    all_vendors_df = pd.read_csv(all_vendors_path)

    # Load raw transactions
    transactions_path = data_dir / 'extracted' / 'all_transactions_raw.csv'
    transactions_df = pd.read_csv(transactions_path)
    transactions_df['date'] = pd.to_datetime(transactions_df['date'])

    # Compute metrics
    total_edtech_spending = edtech_vendors_df['total_spending'].sum()
    total_vendor_count = len(edtech_vendors_df)

    # Top 25 concentration (from researched vendors)
    top_25_spending = sum(v['total_spending'] for v in researched_vendors)
    top_25_concentration = (top_25_spending / total_edtech_spending) * 100 if total_edtech_spending > 0 else 0

    # Replaceability metrics from researched vendors
    # Support both legacy 'replaceability' and v2 'replaceability_level' fields
    replaceability_spending = {level: 0.0 for level in REPLACEABILITY_LEVELS}
    replaceability_counts = {level: 0 for level in REPLACEABILITY_LEVELS}

    # V2 format additional metrics
    classification_counts = {}
    classification_spending = {}
    criticality_counts = {}
    criticality_spending = {}

    for vendor in researched_vendors:
        # Handle both legacy and v2 format
        if is_v2_format:
            level = vendor.get('replaceability_level', 'unknown').lower()
        else:
            level = vendor.get('replaceability', 'none').lower()

        if level not in replaceability_spending:
            level = 'unknown' if is_v2_format else 'none'

        spending = vendor.get('total_spending', 0)
        replaceability_spending[level] += spending
        replaceability_counts[level] += 1

        # V2 format: track classification and criticality
        if is_v2_format:
            classification = vendor.get('classification', 'unknown')
            classification_counts[classification] = classification_counts.get(classification, 0) + 1
            classification_spending[classification] = classification_spending.get(classification, 0) + spending

            criticality = vendor.get('criticality', 'supplementary')
            criticality_counts[criticality] = criticality_counts.get(criticality, 0) + 1
            criticality_spending[criticality] = criticality_spending.get(criticality, 0) + spending

    # Calculate dimension metrics for v2 format
    dimension_metrics = None
    if is_v2_format:
        dimension_metrics = _calculate_dimension_metrics(researched_vendors)

    return ReportData(
        researched_vendors=researched_vendors,
        edtech_vendors_df=edtech_vendors_df,
        all_vendors_df=all_vendors_df,
        transactions_df=transactions_df,
        total_edtech_spending=total_edtech_spending,
        total_vendor_count=total_vendor_count,
        top_25_spending=top_25_spending,
        top_25_concentration=top_25_concentration,
        replaceability_spending=replaceability_spending,
        replaceability_counts=replaceability_counts,
        dimension_metrics=dimension_metrics,
        classification_counts=classification_counts,
        classification_spending=classification_spending,
        criticality_counts=criticality_counts,
        criticality_spending=criticality_spending,
        is_v2_format=is_v2_format,
    )


def get_edtech_monthly_spending(data: ReportData) -> pd.DataFrame:
    """
    Calculate monthly EdTech spending from transactions.

    Args:
        data: ReportData containing transactions and EdTech vendor list.

    Returns:
        DataFrame with monthly spending aggregated.
    """
    # Get list of EdTech vendors
    edtech_vendors = set(data.edtech_vendors_df['vendor'].str.upper())

    # Filter transactions to EdTech vendors
    edtech_transactions = data.transactions_df[
        data.transactions_df['vendor'].str.upper().isin(edtech_vendors)
    ].copy()

    # Aggregate by month
    edtech_transactions['month'] = edtech_transactions['date'].dt.to_period('M')
    monthly = edtech_transactions.groupby('month')['amount'].sum().reset_index()
    monthly['month'] = monthly['month'].dt.to_timestamp()
    monthly = monthly.sort_values('month')

    return monthly


def get_top_n_vendors(data: ReportData, n: int = 10) -> list[dict]:
    """
    Get top N vendors by spending with replaceability info.

    Args:
        data: ReportData containing vendor information.
        n: Number of top vendors to return.

    Returns:
        List of vendor dictionaries with spending and replaceability.
    """
    # Create lookup for replaceability from researched vendors
    # Support both legacy 'replaceability' and v2 'replaceability_level'
    if data.is_v2_format:
        replaceability_lookup = {
            v['vendor_name'].upper(): v.get('replaceability_level', 'unknown')
            for v in data.researched_vendors
        }
        scores_lookup = {
            v['vendor_name'].upper(): v.get('composite_score', 0)
            for v in data.researched_vendors
        }
        classification_lookup = {
            v['vendor_name'].upper(): v.get('classification', 'unknown')
            for v in data.researched_vendors
        }
    else:
        replaceability_lookup = {
            v['vendor_name'].upper(): v.get('replaceability', 'unknown')
            for v in data.researched_vendors
        }
        scores_lookup = {}
        classification_lookup = {}

    # Get top N from EdTech vendors
    top_vendors = data.edtech_vendors_df.nlargest(n, 'total_spending')

    result = []
    for _, row in top_vendors.iterrows():
        vendor_name = row['vendor']
        vendor_data = {
            'vendor_name': vendor_name,
            'total_spending': row['total_spending'],
            'replaceability': replaceability_lookup.get(vendor_name.upper(), 'unknown'),
        }

        if data.is_v2_format:
            vendor_data['composite_score'] = scores_lookup.get(vendor_name.upper(), 0)
            vendor_data['classification'] = classification_lookup.get(vendor_name.upper(), 'unknown')

        result.append(vendor_data)

    return result


def get_vendor_dimension_scores(data: ReportData, vendor_name: str) -> dict:
    """
    Get dimension scores for a specific vendor.

    Args:
        data: ReportData containing vendor information.
        vendor_name: Name of vendor to look up.

    Returns:
        Dictionary with dimension scores, or empty dict if not found/not v2 format.
    """
    if not data.is_v2_format:
        return {}

    for vendor in data.researched_vendors:
        if vendor['vendor_name'].upper() == vendor_name.upper():
            return vendor.get('scores', {})

    return {}


def get_vendors_by_classification(data: ReportData, classification: str) -> list[dict]:
    """
    Get all vendors of a specific classification type.

    Args:
        data: ReportData containing vendor information.
        classification: Classification type to filter by.

    Returns:
        List of vendor dictionaries matching the classification.
    """
    if not data.is_v2_format:
        return []

    return [
        v for v in data.researched_vendors
        if v.get('classification', '').lower() == classification.lower()
    ]
