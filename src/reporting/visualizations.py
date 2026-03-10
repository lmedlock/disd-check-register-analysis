"""
Visualization functions for EdTech spending report.

Creates charts and visual elements for the report.
Supports both legacy (4-level) and v2 (5-dimension) replaceability formats.
"""

import base64
from io import BytesIO
from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

from .data_loader import ReportData, get_edtech_monthly_spending, get_top_n_vendors

# Color scheme for replaceability levels (v2 5-level scale)
REPLACEABILITY_COLORS = {
    'high': '#2ecc71',      # Green - viable for in-house
    'medium': '#f1c40f',    # Yellow - possible with investment
    'low': '#e67e22',       # Orange - major barriers
    'very_low': '#e74c3c',  # Red - essentially irreplaceable
    'none': '#95a5a6',      # Gray - not applicable (services/physical)
    'unknown': '#bdc3c7',   # Light gray - needs research
}

# Color scheme for vendor classifications
CLASSIFICATION_COLORS = {
    'platform': '#3498db',           # Blue
    'curriculum_platform': '#9b59b6', # Purple
    'content': '#1abc9c',            # Teal
    'services': '#95a5a6',           # Gray
    'hybrid': '#e67e22',             # Orange
    'physical': '#7f8c8d',           # Dark gray
    'unknown': '#bdc3c7',            # Light gray
}

# Color scheme for criticality levels
CRITICALITY_COLORS = {
    'core': '#e74c3c',        # Red - mission critical
    'important': '#f39c12',   # Orange - significant
    'supplementary': '#3498db', # Blue - nice to have
}

# Dallas ISD brand colors
BRAND_COLORS = {
    'primary': '#003366',    # Navy blue
    'secondary': '#c8102e',  # Red
    'accent': '#00a3e0',     # Light blue
}

# Dimension display names for radar charts
DIMENSION_LABELS = {
    'technical_buildability': 'Technical\nBuildability',
    'content_ip': 'Content/IP\nReplaceability',
    'switching_cost': 'Switching\nCost',
    'market_alternatives': 'Market\nAlternatives',
    'data_portability': 'Data\nPortability',
}


def _fig_to_base64(fig: plt.Figure) -> str:
    """Convert matplotlib figure to base64 string for HTML embedding."""
    buf = BytesIO()
    fig.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='white')
    buf.seek(0)
    img_str = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig)
    return f"data:image/png;base64,{img_str}"


def _format_currency(value: float) -> str:
    """Format a number as currency."""
    if value >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    elif value >= 1_000:
        return f"${value / 1_000:.0f}K"
    else:
        return f"${value:.0f}"


def create_radar_chart(
    scores: dict,
    vendor_name: str = "",
    save_path: Optional[Path] = None,
    show_title: bool = True
) -> str:
    """
    Create a radar chart for a vendor's 5-dimension scores.

    Args:
        scores: Dictionary with dimension scores (1-5 scale).
        vendor_name: Name of vendor for title.
        save_path: Optional path to save the chart.
        show_title: Whether to show the chart title.

    Returns:
        Base64-encoded image string for HTML embedding.
    """
    dimensions = ['technical_buildability', 'content_ip', 'switching_cost',
                  'market_alternatives', 'data_portability']

    # Get scores in order, default to 0 if missing
    values = [scores.get(dim, 0) for dim in dimensions]

    # Complete the loop by repeating the first value
    values += values[:1]

    # Create angles for radar chart
    angles = np.linspace(0, 2 * np.pi, len(dimensions), endpoint=False).tolist()
    angles += angles[:1]

    # Create figure
    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True))

    # Plot the radar chart
    ax.plot(angles, values, 'o-', linewidth=2, color=BRAND_COLORS['primary'])
    ax.fill(angles, values, alpha=0.25, color=BRAND_COLORS['primary'])

    # Set the labels
    labels = [DIMENSION_LABELS.get(dim, dim) for dim in dimensions]
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels, size=9)

    # Set y-axis limits and ticks
    ax.set_ylim(0, 5)
    ax.set_yticks([1, 2, 3, 4, 5])
    ax.set_yticklabels(['1', '2', '3', '4', '5'], size=8)

    # Add grid
    ax.grid(True, linestyle='--', alpha=0.7)

    if show_title and vendor_name:
        ax.set_title(f'{vendor_name[:30]}...\nReplaceability Dimensions' if len(vendor_name) > 30
                     else f'{vendor_name}\nReplaceability Dimensions',
                     size=11, fontweight='bold', pad=20)

    plt.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches='tight', facecolor='white')

    return _fig_to_base64(fig)


def create_dimension_heatmap(data: ReportData, save_path: Optional[Path] = None) -> str:
    """
    Create a heatmap showing vendors x dimensions matrix.

    Args:
        data: ReportData containing researched vendor profiles.
        save_path: Optional path to save the chart.

    Returns:
        Base64-encoded image string for HTML embedding.
    """
    if not data.is_v2_format:
        # Return placeholder for legacy data
        fig, ax = plt.subplots(figsize=(12, 8))
        ax.text(0.5, 0.5, 'Dimension heatmap requires v2 data format',
                ha='center', va='center', fontsize=12)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis('off')
        return _fig_to_base64(fig)

    dimensions = ['technical_buildability', 'content_ip', 'switching_cost',
                  'market_alternatives', 'data_portability']

    # Filter to vendors with actual scores (not services/physical)
    scored_vendors = [
        v for v in data.researched_vendors
        if v.get('classification') not in ['services', 'physical', 'unknown']
        and any(v.get('scores', {}).get(d, 0) > 0 for d in dimensions)
    ]

    if not scored_vendors:
        fig, ax = plt.subplots(figsize=(12, 8))
        ax.text(0.5, 0.5, 'No scored vendors available', ha='center', va='center')
        return _fig_to_base64(fig)

    # Sort by composite score
    scored_vendors.sort(key=lambda v: v.get('composite_score', 0), reverse=True)

    # Limit to top 15 for readability
    scored_vendors = scored_vendors[:15]

    # Build the matrix
    vendor_names = [v['vendor_name'][:25] + '...' if len(v['vendor_name']) > 25
                    else v['vendor_name'] for v in scored_vendors]
    matrix = []
    for vendor in scored_vendors:
        scores = vendor.get('scores', {})
        row = [scores.get(dim, 0) for dim in dimensions]
        matrix.append(row)

    matrix = np.array(matrix)

    # Create figure
    fig, ax = plt.subplots(figsize=(10, max(6, len(vendor_names) * 0.4)))

    # Create heatmap with custom colormap (1-5 scale)
    cmap = plt.cm.RdYlGn  # Red (low) to Green (high)
    im = ax.imshow(matrix, cmap=cmap, aspect='auto', vmin=1, vmax=5)

    # Set labels
    dim_labels = [DIMENSION_LABELS.get(d, d).replace('\n', ' ') for d in dimensions]
    ax.set_xticks(np.arange(len(dimensions)))
    ax.set_yticks(np.arange(len(vendor_names)))
    ax.set_xticklabels(dim_labels, fontsize=9, rotation=45, ha='right')
    ax.set_yticklabels(vendor_names, fontsize=9)

    # Add score text in each cell
    for i in range(len(vendor_names)):
        for j in range(len(dimensions)):
            score = matrix[i, j]
            if score > 0:
                text_color = 'white' if score <= 2 else 'black'
                ax.text(j, i, str(int(score)), ha='center', va='center',
                        color=text_color, fontsize=10, fontweight='bold')

    # Add colorbar
    cbar = ax.figure.colorbar(im, ax=ax, shrink=0.8)
    cbar.set_label('Score (1-5, higher = more replaceable)', fontsize=10)

    ax.set_title('Vendor Replaceability Dimension Scores', fontsize=12, fontweight='bold', pad=15)

    plt.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches='tight', facecolor='white')

    return _fig_to_base64(fig)


def create_classification_chart(data: ReportData, save_path: Optional[Path] = None) -> str:
    """
    Create a chart showing vendor classification distribution.

    Args:
        data: ReportData containing classification counts.
        save_path: Optional path to save the chart.

    Returns:
        Base64-encoded image string for HTML embedding.
    """
    if not data.is_v2_format or not data.classification_counts:
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.text(0.5, 0.5, 'Classification chart requires v2 data format',
                ha='center', va='center', fontsize=12)
        ax.axis('off')
        return _fig_to_base64(fig)

    # Prepare data
    classifications = list(data.classification_counts.keys())
    counts = [data.classification_counts[c] for c in classifications]
    spending = [data.classification_spending.get(c, 0) / 1_000_000 for c in classifications]
    colors = [CLASSIFICATION_COLORS.get(c, '#bdc3c7') for c in classifications]

    # Create figure with two subplots
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    # Vendor count pie chart
    wedges1, texts1, autotexts1 = ax1.pie(
        counts,
        labels=None,
        colors=colors,
        autopct=lambda pct: f'{int(pct/100*sum(counts))}' if pct > 5 else '',
        pctdistance=0.7,
        wedgeprops=dict(width=0.6, edgecolor='white'),
    )
    ax1.set_title('Vendors by Classification', fontsize=11, fontweight='bold')

    # Spending bar chart
    y_pos = np.arange(len(classifications))
    ax2.barh(y_pos, spending, color=colors, edgecolor='white')
    ax2.set_yticks(y_pos)
    ax2.set_yticklabels([c.replace('_', ' ').title() for c in classifications], fontsize=9)
    ax2.set_xlabel('Spending ($ Millions)', fontsize=10)
    ax2.set_title('Spending by Classification', fontsize=11, fontweight='bold')

    # Add value labels
    for i, (s, c) in enumerate(zip(spending, counts)):
        ax2.text(s + 0.5, i, f'${s:.1f}M ({c})', va='center', fontsize=8)

    ax2.spines['top'].set_visible(False)
    ax2.spines['right'].set_visible(False)

    plt.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches='tight', facecolor='white')

    return _fig_to_base64(fig)


def create_key_metrics_cards(data: ReportData) -> str:
    """
    Create HTML for key metrics cards.
    Supports both legacy and v2 data formats.

    Args:
        data: ReportData containing computed metrics.

    Returns:
        HTML string with metrics cards.
    """
    # Calculate replaceable spending (high + medium replaceability)
    replaceable_spending = (
        data.replaceability_spending.get('high', 0) +
        data.replaceability_spending.get('medium', 0)
    )
    replaceable_pct = (replaceable_spending / data.top_25_spending * 100) if data.top_25_spending > 0 else 0

    # For v2 format, also calculate low replaceability (services excluded)
    if data.is_v2_format:
        services_spending = data.classification_spending.get('services', 0) + data.classification_spending.get('physical', 0)
        software_spending = data.top_25_spending - services_spending
        replaceability_subtitle = f"{replaceable_pct:.1f}% of software vendors"
    else:
        replaceability_subtitle = f"{replaceable_pct:.1f}% of top 25 (high/medium)"

    metrics = [
        {
            'title': 'Total EdTech Spending',
            'value': _format_currency(data.total_edtech_spending),
            'subtitle': '4-year total (FY21-FY25)',
            'color': BRAND_COLORS['primary'],
        },
        {
            'title': 'EdTech Vendors',
            'value': str(data.total_vendor_count),
            'subtitle': 'Unique vendors identified',
            'color': BRAND_COLORS['accent'],
        },
        {
            'title': 'Top 25 Concentration',
            'value': f"{data.top_25_concentration:.1f}%",
            'subtitle': f"{_format_currency(data.top_25_spending)} of total",
            'color': BRAND_COLORS['secondary'],
        },
        {
            'title': 'Potentially Replaceable',
            'value': _format_currency(replaceable_spending),
            'subtitle': replaceability_subtitle,
            'color': REPLACEABILITY_COLORS['high'],
        },
    ]

    # Add v2-specific metrics
    if data.is_v2_format:
        # Count by criticality
        core_count = data.criticality_counts.get('core', 0)
        core_spending = data.criticality_spending.get('core', 0)

        metrics.append({
            'title': 'Core Systems',
            'value': str(core_count),
            'subtitle': f"{_format_currency(core_spending)} mission-critical",
            'color': CRITICALITY_COLORS['core'],
        })

        # Unknown/needs research
        unknown_count = data.replaceability_counts.get('unknown', 0)
        unknown_spending = data.replaceability_spending.get('unknown', 0)
        if unknown_count > 0:
            metrics.append({
                'title': 'Needs Research',
                'value': str(unknown_count),
                'subtitle': f"{_format_currency(unknown_spending)} flagged for follow-up",
                'color': REPLACEABILITY_COLORS['unknown'],
            })

    cards_html = '<div class="metrics-grid">\n'
    for metric in metrics:
        cards_html += f'''
        <div class="metric-card" style="border-top: 4px solid {metric['color']};">
            <div class="metric-title">{metric['title']}</div>
            <div class="metric-value">{metric['value']}</div>
            <div class="metric-subtitle">{metric['subtitle']}</div>
        </div>
        '''
    cards_html += '</div>'

    return cards_html


def create_top_vendors_chart(data: ReportData, n: int = 10, save_path: Optional[Path] = None) -> str:
    """
    Create horizontal bar chart of top vendors colored by replaceability.

    Args:
        data: ReportData containing vendor information.
        n: Number of vendors to show.
        save_path: Optional path to save the chart as PNG.

    Returns:
        Base64-encoded image string for HTML embedding.
    """
    top_vendors = get_top_n_vendors(data, n)

    # Prepare data
    vendors = [v['vendor_name'] for v in top_vendors]
    spending = [v['total_spending'] / 1_000_000 for v in top_vendors]  # Convert to millions
    colors = [REPLACEABILITY_COLORS.get(v['replaceability'], REPLACEABILITY_COLORS['unknown'])
              for v in top_vendors]

    # Create figure
    fig, ax = plt.subplots(figsize=(10, 6))

    # Create horizontal bar chart (reverse order for top-to-bottom display)
    y_pos = np.arange(len(vendors))
    bars = ax.barh(y_pos, spending[::-1], color=colors[::-1], edgecolor='white', linewidth=0.5)

    # Customize
    ax.set_yticks(y_pos)
    ax.set_yticklabels([v[:35] + '...' if len(v) > 35 else v for v in vendors[::-1]], fontsize=9)
    ax.set_xlabel('Spending ($ Millions)', fontsize=10)
    ax.set_title(f'Top {n} EdTech Vendors by Spending', fontsize=12, fontweight='bold', pad=15)

    # Add value labels
    for bar, val in zip(bars, spending[::-1]):
        ax.text(bar.get_width() + 0.3, bar.get_y() + bar.get_height()/2,
                f'${val:.1f}M', va='center', fontsize=8)

    # Add legend
    legend_elements = [
        plt.Rectangle((0, 0), 1, 1, facecolor=REPLACEABILITY_COLORS['high'], label='High (Buildable)'),
        plt.Rectangle((0, 0), 1, 1, facecolor=REPLACEABILITY_COLORS['medium'], label='Medium'),
        plt.Rectangle((0, 0), 1, 1, facecolor=REPLACEABILITY_COLORS['low'], label='Low'),
        plt.Rectangle((0, 0), 1, 1, facecolor=REPLACEABILITY_COLORS['none'], label='None (Services)'),
    ]
    ax.legend(handles=legend_elements, loc='lower right', fontsize=8, title='Replaceability')

    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.set_xlim(0, max(spending) * 1.15)

    plt.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches='tight', facecolor='white')

    return _fig_to_base64(fig)


def create_replaceability_donut(data: ReportData, save_path: Optional[Path] = None) -> str:
    """
    Create donut chart showing replaceability distribution.
    Supports both legacy (4-level) and v2 (5-level) formats.

    Args:
        data: ReportData containing replaceability metrics.
        save_path: Optional path to save the chart.

    Returns:
        Base64-encoded image string for HTML embedding.
    """
    # Prepare data - use 5-level scale for v2, 4-level for legacy
    if data.is_v2_format:
        labels = ['High', 'Medium', 'Low', 'Very Low', 'None', 'Unknown']
        keys = ['high', 'medium', 'low', 'very_low', 'none', 'unknown']
    else:
        labels = ['High', 'Medium', 'Low', 'None']
        keys = ['high', 'medium', 'low', 'none']

    spending = [data.replaceability_spending.get(k, 0) / 1_000_000 for k in keys]
    counts = [data.replaceability_counts.get(k, 0) for k in keys]
    colors = [REPLACEABILITY_COLORS[k] for k in keys]

    # Filter out zero values
    non_zero = [(l, s, c, col) for l, s, c, col in zip(labels, spending, counts, colors) if s > 0]
    if not non_zero:
        # Return placeholder if no data
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.text(0.5, 0.5, 'No data available', ha='center', va='center')
        return _fig_to_base64(fig)

    labels, spending, counts, colors = zip(*non_zero)

    # Create figure
    fig, ax = plt.subplots(figsize=(8, 6))

    # Create donut chart
    wedges, texts, autotexts = ax.pie(
        spending,
        labels=None,
        colors=colors,
        autopct=lambda pct: f'${pct/100*sum(spending):.1f}M\n({pct:.1f}%)' if pct > 5 else '',
        pctdistance=0.75,
        wedgeprops=dict(width=0.5, edgecolor='white', linewidth=2),
        textprops={'fontsize': 9},
    )

    # Add center text
    total = sum(spending)
    ax.text(0, 0, f'Total\n${total:.1f}M', ha='center', va='center',
            fontsize=14, fontweight='bold')

    # Add legend with counts
    legend_labels = [f'{l} ({c} vendors)' for l, c in zip(labels, counts)]
    ax.legend(wedges, legend_labels, loc='center left', bbox_to_anchor=(1, 0.5),
              fontsize=9, title='Replaceability Level')

    title = 'Top 25 Vendor Spending by Replaceability'
    if data.is_v2_format:
        title += '\n(5-Dimension Composite Score)'
    ax.set_title(title, fontsize=12, fontweight='bold', pad=15)

    plt.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches='tight', facecolor='white')

    return _fig_to_base64(fig)


def create_spending_treemap(data: ReportData, save_path: Optional[Path] = None) -> str:
    """
    Create interactive Plotly treemap of vendor spending.

    Args:
        data: ReportData containing vendor information.
        save_path: Optional path to save as HTML.

    Returns:
        HTML string containing the interactive chart.
    """
    # Create lookup for replaceability
    replaceability_lookup = {
        v['vendor_name'].upper(): v.get('replaceability', 'unknown')
        for v in data.researched_vendors
    }

    # Prepare data for treemap
    vendors = []
    for _, row in data.edtech_vendors_df.head(50).iterrows():
        vendor_name = row['vendor']
        repl = replaceability_lookup.get(vendor_name.upper(), 'unknown')
        vendors.append({
            'vendor': vendor_name[:30] + '...' if len(vendor_name) > 30 else vendor_name,
            'full_name': vendor_name,
            'spending': row['total_spending'],
            'replaceability': repl.capitalize(),
        })

    df = pd.DataFrame(vendors)

    # Create treemap
    fig = px.treemap(
        df,
        path=['replaceability', 'vendor'],
        values='spending',
        color='replaceability',
        color_discrete_map={
            'High': REPLACEABILITY_COLORS['high'],
            'Medium': REPLACEABILITY_COLORS['medium'],
            'Low': REPLACEABILITY_COLORS['low'],
            'None': REPLACEABILITY_COLORS['none'],
            'Unknown': REPLACEABILITY_COLORS['unknown'],
        },
        title='EdTech Vendor Spending Hierarchy (Top 50)',
        hover_data={'spending': ':$,.0f'},
    )

    fig.update_layout(
        margin=dict(t=50, l=10, r=10, b=10),
        font=dict(size=11),
    )

    fig.update_traces(
        textinfo='label+value',
        texttemplate='%{label}<br>$%{value:,.0f}',
        hovertemplate='<b>%{label}</b><br>Spending: $%{value:,.0f}<extra></extra>',
    )

    if save_path:
        fig.write_html(save_path)

    return fig.to_html(full_html=False, include_plotlyjs='cdn')


def create_time_series_chart(data: ReportData, save_path: Optional[Path] = None) -> str:
    """
    Create monthly spending trend line chart.

    Args:
        data: ReportData containing transaction data.
        save_path: Optional path to save the chart.

    Returns:
        Base64-encoded image string for HTML embedding.
    """
    monthly = get_edtech_monthly_spending(data)

    if monthly.empty:
        fig, ax = plt.subplots(figsize=(12, 5))
        ax.text(0.5, 0.5, 'No transaction data available', ha='center', va='center')
        return _fig_to_base64(fig)

    fig, ax = plt.subplots(figsize=(12, 5))

    # Plot line
    ax.plot(monthly['month'], monthly['amount'] / 1_000_000,
            color=BRAND_COLORS['primary'], linewidth=2, marker='o', markersize=4)

    # Fill area under curve
    ax.fill_between(monthly['month'], monthly['amount'] / 1_000_000,
                    alpha=0.2, color=BRAND_COLORS['primary'])

    # Add trend line
    z = np.polyfit(range(len(monthly)), monthly['amount'] / 1_000_000, 1)
    p = np.poly1d(z)
    ax.plot(monthly['month'], p(range(len(monthly))),
            '--', color=BRAND_COLORS['secondary'], alpha=0.7, label='Trend')

    ax.set_xlabel('Month', fontsize=10)
    ax.set_ylabel('Spending ($ Millions)', fontsize=10)
    ax.set_title('Monthly EdTech Spending Trend', fontsize=12, fontweight='bold', pad=15)

    ax.yaxis.set_major_formatter(mtick.StrMethodFormatter('${x:.1f}M'))
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.legend(loc='upper right')

    # Rotate x-axis labels
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches='tight', facecolor='white')

    return _fig_to_base64(fig)


def create_pareto_chart(data: ReportData, save_path: Optional[Path] = None) -> str:
    """
    Create Pareto chart showing vendor concentration.

    Args:
        data: ReportData containing vendor spending.
        save_path: Optional path to save the chart.

    Returns:
        Base64-encoded image string for HTML embedding.
    """
    # Sort vendors by spending (descending)
    sorted_df = data.edtech_vendors_df.sort_values('total_spending', ascending=False).head(50)

    vendors = range(1, len(sorted_df) + 1)
    spending = sorted_df['total_spending'].values / 1_000_000
    cumulative_pct = sorted_df['total_spending'].cumsum() / data.total_edtech_spending * 100

    fig, ax1 = plt.subplots(figsize=(12, 6))

    # Bar chart
    bars = ax1.bar(vendors, spending, color=BRAND_COLORS['primary'], alpha=0.7, edgecolor='white')
    ax1.set_xlabel('Vendor Rank', fontsize=10)
    ax1.set_ylabel('Spending ($ Millions)', fontsize=10, color=BRAND_COLORS['primary'])
    ax1.tick_params(axis='y', labelcolor=BRAND_COLORS['primary'])

    # Cumulative line on secondary axis
    ax2 = ax1.twinx()
    ax2.plot(vendors, cumulative_pct, color=BRAND_COLORS['secondary'],
             linewidth=2, marker='o', markersize=3)
    ax2.set_ylabel('Cumulative %', fontsize=10, color=BRAND_COLORS['secondary'])
    ax2.tick_params(axis='y', labelcolor=BRAND_COLORS['secondary'])
    ax2.set_ylim(0, 105)
    ax2.yaxis.set_major_formatter(mtick.PercentFormatter())

    # Add reference lines
    ax2.axhline(y=80, color='gray', linestyle='--', alpha=0.5)
    ax2.text(len(vendors) * 0.9, 82, '80%', fontsize=9, color='gray')

    ax1.set_title('Vendor Concentration (Pareto Analysis)', fontsize=12, fontweight='bold', pad=15)
    ax1.spines['top'].set_visible(False)

    plt.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches='tight', facecolor='white')

    return _fig_to_base64(fig)


def create_vendor_cards_html(data: ReportData) -> str:
    """
    Create HTML cards for each researched vendor.
    Supports both legacy and v2 formats with dimension scores.

    Args:
        data: ReportData containing researched vendor profiles.

    Returns:
        HTML string with vendor profile cards.
    """
    cards_html = '<div class="vendor-profiles">\n'

    for vendor in data.researched_vendors:
        # Get replaceability level (v2 or legacy format)
        if data.is_v2_format:
            repl_level = vendor.get('replaceability_level', 'unknown').lower()
            composite_score = vendor.get('composite_score', 0)
            classification = vendor.get('classification', 'unknown')
            confidence = vendor.get('research_confidence', 'unknown')
        else:
            repl_level = vendor.get('replaceability', 'unknown').lower()
            composite_score = 0
            classification = ''
            confidence = ''

        repl_color = REPLACEABILITY_COLORS.get(repl_level, REPLACEABILITY_COLORS['unknown'])
        class_color = CLASSIFICATION_COLORS.get(classification, CLASSIFICATION_COLORS['unknown'])

        # Format products list
        products = vendor.get('primary_products', [])
        products_html = '<ul class="product-list">'
        for product in products[:5]:  # Show up to 5 products
            products_html += f'<li>{product}</li>'
        if len(products) > 5:
            products_html += f'<li><em>... and {len(products) - 5} more</em></li>'
        products_html += '</ul>'

        spending = vendor.get('total_spending', 0)

        # Build dimension scores section for v2 format
        dimension_html = ''
        if data.is_v2_format and classification not in ['services', 'physical']:
            scores = vendor.get('scores', {})
            if any(scores.values()):
                dimension_html = '''
                <div class="vendor-section dimension-scores">
                    <h4>Dimension Scores <span class="score-legend">(1=hard to replace, 5=easy)</span></h4>
                    <div class="score-grid">
                '''
                for dim_key, dim_label in DIMENSION_LABELS.items():
                    score = scores.get(dim_key, 0)
                    if score > 0:
                        # Color based on score
                        score_colors = {1: '#e74c3c', 2: '#e67e22', 3: '#f1c40f', 4: '#27ae60', 5: '#2ecc71'}
                        score_color = score_colors.get(score, '#95a5a6')
                        dimension_html += f'''
                        <div class="score-item">
                            <span class="score-label">{dim_label.replace(chr(10), ' ')}</span>
                            <span class="score-value" style="background-color: {score_color};">{score}</span>
                        </div>
                        '''
                dimension_html += '</div></div>'

        # Build service breakdown for v2 format
        breakdown_html = ''
        if data.is_v2_format:
            breakdown = vendor.get('service_breakdown', {})
            if any(breakdown.values()):
                breakdown_html = '''
                <div class="vendor-section service-breakdown">
                    <h4>Service Breakdown</h4>
                    <div class="breakdown-bar">
                '''
                breakdown_items = [
                    ('software_licensing', 'Software', '#3498db'),
                    ('content_licensing', 'Content', '#9b59b6'),
                    ('professional_development', 'PD', '#2ecc71'),
                    ('hardware_materials', 'Hardware', '#7f8c8d'),
                    ('ongoing_services', 'Services', '#f39c12'),
                ]
                for key, label, color in breakdown_items:
                    pct = breakdown.get(key, 0)
                    if pct > 0:
                        breakdown_html += f'<div class="breakdown-segment" style="width: {pct}%; background-color: {color};" title="{label}: {pct}%"></div>'
                breakdown_html += '</div>'
                breakdown_html += '<div class="breakdown-legend">'
                for key, label, color in breakdown_items:
                    pct = breakdown.get(key, 0)
                    if pct > 0:
                        breakdown_html += f'<span class="legend-item"><span class="legend-color" style="background-color: {color};"></span>{label} {pct}%</span>'
                breakdown_html += '</div></div>'

        # Classification badge for v2
        classification_badge = ''
        if data.is_v2_format and classification:
            classification_badge = f'''
            <div class="classification-badge" style="background-color: {class_color};">
                {classification.replace('_', ' ').title()}
            </div>
            '''

        # Confidence badge for v2
        confidence_badge = ''
        if data.is_v2_format and confidence:
            confidence_colors = {'high': '#2ecc71', 'medium': '#f39c12', 'low': '#e74c3c', 'unknown': '#95a5a6'}
            conf_color = confidence_colors.get(confidence, '#95a5a6')
            confidence_badge = f'<span class="confidence-badge" style="background-color: {conf_color};">Confidence: {confidence.title()}</span>'

        # Composite score display for v2
        score_display = ''
        if data.is_v2_format and composite_score > 0:
            score_display = f'<span class="composite-score">Score: {composite_score:.2f}</span>'

        # Build fund breakdown section
        fund_html = ''
        fund_breakdown = vendor.get('fund_breakdown', {})
        if fund_breakdown:
            rows = ''
            for fund_code, info in list(fund_breakdown.items())[:6]:
                rows += (
                    f'<tr>'
                    f'<td class="fund-code">{fund_code}</td>'
                    f'<td class="fund-name">{info["fund_name"]}</td>'
                    f'<td class="fund-amount">{_format_currency(info["amount"])}</td>'
                    f'<td class="fund-count">{info["tx_count"]} checks</td>'
                    f'</tr>'
                )
            if len(fund_breakdown) > 6:
                rows += f'<tr><td colspan="4"><em>... and {len(fund_breakdown) - 6} more funds</em></td></tr>'
            fund_html = f'''
            <div class="vendor-section fund-breakdown">
                <h4>Spending by Fund</h4>
                <table class="fund-table">
                    <thead><tr><th>Fund</th><th>Name</th><th>Amount</th><th>Checks</th></tr></thead>
                    <tbody>{rows}</tbody>
                </table>
            </div>'''

        # Build matched awards section
        awards_html = ''
        matched_awards = vendor.get('matched_awards', [])
        coverage_note = vendor.get('contract_coverage_note')
        if matched_awards:
            seen_bids = set()
            award_items = ''
            for award in matched_awards:
                bid = award.get('award_description', '')
                cat = award.get('category_description', '')
                key = (bid, cat)
                if key in seen_bids:
                    continue
                seen_bids.add(key)
                status = award.get('overlap_status', 'unknown')
                status_colors = {
                    'ongoing': '#f39c12', 'completed': '#27ae60',
                    'predates_data': '#9b59b6', 'spanning': '#8e44ad',
                    'unknown': '#95a5a6',
                }
                sc = status_colors.get(status, '#95a5a6')
                amt = award.get('matched_spending', 0)
                dates = ''
                if award.get('effective_date') or award.get('end_date'):
                    dates = f" ({award.get('effective_date','?')} – {award.get('end_date','?')})"
                award_items += (
                    f'<div class="award-item">'
                    f'<span class="award-status-dot" style="background:{sc};" title="{status}"></span>'
                    f'<div class="award-detail">'
                    f'<div class="award-bid">{bid}</div>'
                    f'<div class="award-cat">{cat}{dates}</div>'
                    f'<div class="award-spend">{_format_currency(amt)} matched · '
                    f'<span class="award-status-label" style="color:{sc};">{status.replace("_"," ")}</span></div>'
                    f'</div>'
                    f'</div>'
                )
            awards_html = f'''
            <div class="vendor-section matched-awards">
                <h4>Contract Awards</h4>
                {award_items}
            </div>'''
        elif coverage_note:
            awards_html = f'''
            <div class="vendor-section matched-awards">
                <h4>Contract Awards</h4>
                <p class="coverage-note">{coverage_note}</p>
            </div>'''

        # Get rationale (different field names for v2 vs legacy)
        if data.is_v2_format:
            rationales = vendor.get('rationales', {})
            # Combine rationales into a summary
            rationale_parts = []
            for dim, text in rationales.items():
                if text and not text.startswith('N/A') and not text.startswith('Migrated'):
                    rationale_parts.append(f"<strong>{DIMENSION_LABELS.get(dim, dim).replace(chr(10), ' ')}:</strong> {text}")
            rationale_html = '<br>'.join(rationale_parts[:3]) if rationale_parts else vendor.get('additional_notes', 'No rationale provided')
        else:
            rationale_html = vendor.get('replaceability_rationale', 'No rationale provided')

        cards_html += f'''
        <div class="vendor-card">
            <div class="vendor-header" style="border-left: 4px solid {repl_color};">
                <div class="vendor-title-row">
                    <h3>{vendor.get('vendor_name', 'Unknown')}</h3>
                    {classification_badge}
                </div>
                <div class="vendor-meta">
                    <span class="vendor-spending">{_format_currency(spending)}</span>
                    {score_display}
                    {confidence_badge}
                </div>
            </div>
            <div class="vendor-body">
                <div class="vendor-section">
                    <h4>Products</h4>
                    {products_html}
                </div>
                <div class="vendor-section">
                    <h4>Use Case</h4>
                    <p>{vendor.get('target_use_case', 'Not specified')[:300]}{'...' if len(vendor.get('target_use_case', '')) > 300 else ''}</p>
                </div>
                {dimension_html}
                {breakdown_html}
                {fund_html}
                {awards_html}
                <div class="vendor-section replaceability-section">
                    <div class="replaceability-badge" style="background-color: {repl_color};">
                        {repl_level.upper().replace('_', ' ')} Replaceability
                    </div>
                    <div class="replaceability-rationale">{rationale_html}</div>
                </div>
            </div>
        </div>
        '''

    cards_html += '</div>'
    return cards_html


# Need to import pandas for the treemap function
import pandas as pd
