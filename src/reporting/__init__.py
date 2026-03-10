"""
EdTech Spending Visualization Report Module

Generates static HTML/PDF reports visualizing Dallas ISD EdTech spending analysis.
Supports both legacy (4-level) and v2 (5-dimension) replaceability scoring formats.
"""

from .data_loader import (
    load_report_data,
    ReportData,
    DimensionMetrics,
    get_edtech_monthly_spending,
    get_top_n_vendors,
    get_vendor_dimension_scores,
    get_vendors_by_classification,
    DIMENSION_WEIGHTS,
    REPLACEABILITY_LEVELS,
)
from .visualizations import (
    create_key_metrics_cards,
    create_top_vendors_chart,
    create_replaceability_donut,
    create_spending_treemap,
    create_time_series_chart,
    create_pareto_chart,
    create_vendor_cards_html,
    create_radar_chart,
    create_dimension_heatmap,
    create_classification_chart,
    REPLACEABILITY_COLORS,
    CLASSIFICATION_COLORS,
    CRITICALITY_COLORS,
    DIMENSION_LABELS,
)
from .report_generator import generate_report

__all__ = [
    # Data loading
    'load_report_data',
    'ReportData',
    'DimensionMetrics',
    'get_edtech_monthly_spending',
    'get_top_n_vendors',
    'get_vendor_dimension_scores',
    'get_vendors_by_classification',
    'DIMENSION_WEIGHTS',
    'REPLACEABILITY_LEVELS',
    # Visualizations
    'create_key_metrics_cards',
    'create_top_vendors_chart',
    'create_replaceability_donut',
    'create_spending_treemap',
    'create_time_series_chart',
    'create_pareto_chart',
    'create_vendor_cards_html',
    'create_radar_chart',
    'create_dimension_heatmap',
    'create_classification_chart',
    'REPLACEABILITY_COLORS',
    'CLASSIFICATION_COLORS',
    'CRITICALITY_COLORS',
    'DIMENSION_LABELS',
    # Report generation
    'generate_report',
]
