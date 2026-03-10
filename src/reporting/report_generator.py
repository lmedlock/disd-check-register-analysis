"""
Report generator for EdTech spending analysis.

Orchestrates data loading, chart generation, and report rendering.
Supports both legacy (4-level) and v2 (5-dimension) replaceability formats.
"""

from datetime import datetime
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader

from .data_loader import load_report_data, ReportData, REPLACEABILITY_LEVELS
from .visualizations import (
    create_key_metrics_cards,
    create_top_vendors_chart,
    create_replaceability_donut,
    create_spending_treemap,
    create_time_series_chart,
    create_pareto_chart,
    create_vendor_cards_html,
    create_dimension_heatmap,
    create_classification_chart,
)


def _format_currency(value: float) -> str:
    """Format a number as currency."""
    if value >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    elif value >= 1_000:
        return f"${value / 1_000:.0f}K"
    else:
        return f"${value:.0f}"


def generate_report(
    output_dir: Optional[Path] = None,
    data_dir: Optional[Path] = None,
    formats: list[str] = None,
) -> dict[str, Path]:
    """
    Generate the EdTech spending report.

    Args:
        output_dir: Directory for output files. Defaults to 'reports/'.
        data_dir: Directory containing source data. Defaults to 'data/'.
        formats: List of output formats ('html', 'pdf', or both). Defaults to ['html'].

    Returns:
        Dictionary mapping format names to output file paths.
    """
    if formats is None:
        formats = ['html']

    # Determine project root by finding 'data' directory with expected structure
    current = Path(__file__).resolve().parent
    while current.parent != current:
        potential_data = current / 'data'
        if potential_data.exists() and (potential_data / 'vendors').exists():
            project_root = current
            break
        current = current.parent
    else:
        raise FileNotFoundError("Could not find project root with data/vendors directory")

    if output_dir is None:
        output_dir = project_root / 'reports'
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create charts directory
    charts_dir = output_dir / 'assets' / 'charts'
    charts_dir.mkdir(parents=True, exist_ok=True)

    print("Loading data...")
    data = load_report_data(data_dir)

    print("Generating visualizations...")
    print(f"  Data format: {'v2 (5-dimension)' if data.is_v2_format else 'legacy (4-level)'}")

    # Generate all charts
    metrics_cards = create_key_metrics_cards(data)
    top_vendors_chart = create_top_vendors_chart(
        data, n=10, save_path=charts_dir / 'top_vendors.png'
    )
    replaceability_donut = create_replaceability_donut(
        data, save_path=charts_dir / 'replaceability_donut.png'
    )
    spending_treemap = create_spending_treemap(
        data, save_path=charts_dir / 'spending_treemap.html'
    )
    time_series_chart = create_time_series_chart(
        data, save_path=charts_dir / 'time_series.png'
    )
    pareto_chart = create_pareto_chart(
        data, save_path=charts_dir / 'pareto.png'
    )
    vendor_cards = create_vendor_cards_html(data)

    # V2 format additional charts
    dimension_heatmap = ''
    classification_chart = ''
    if data.is_v2_format:
        print("  Generating v2 dimension charts...")
        dimension_heatmap = create_dimension_heatmap(
            data, save_path=charts_dir / 'dimension_heatmap.png'
        )
        classification_chart = create_classification_chart(
            data, save_path=charts_dir / 'classification_chart.png'
        )

    print("Rendering template...")

    # Load template
    template_dir = Path(__file__).parent / 'templates'
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template('report_template.html')

    # Load CSS
    with open(template_dir / 'styles.css', 'r') as f:
        css_content = f.read()

    # Calculate summary statistics
    top_vendor = data.researched_vendors[0] if data.researched_vendors else {}
    top_vendor_name = top_vendor.get('vendor_name', 'Unknown')
    top_vendor_spending = top_vendor.get('total_spending', 0)
    top_vendor_pct = (top_vendor_spending / data.total_edtech_spending * 100
                     if data.total_edtech_spending > 0 else 0)

    # Build template context
    template_context = {
        'title': "Dallas ISD EdTech Spending Analysis",
        'subtitle': "Comprehensive analysis of educational technology vendor spending",
        'generation_date': datetime.now().strftime("%B %d, %Y"),
        'css_content': css_content,
        'metrics_cards': metrics_cards,
        'top_vendors_chart': top_vendors_chart,
        'replaceability_donut': replaceability_donut,
        'spending_treemap': spending_treemap,
        'time_series_chart': time_series_chart,
        'pareto_chart': pareto_chart,
        'vendor_cards': vendor_cards,
        # Summary statistics
        'top_25_concentration': f"{data.top_25_concentration:.1f}",
        'top_vendor_name': top_vendor_name,
        'top_vendor_pct': f"{top_vendor_pct:.1f}",
        'total_vendor_count': data.total_vendor_count,
        # Replaceability counts and spending
        'high_repl_count': data.replaceability_counts.get('high', 0),
        'high_repl_spending': _format_currency(data.replaceability_spending.get('high', 0)),
        'medium_repl_count': data.replaceability_counts.get('medium', 0),
        'medium_repl_spending': _format_currency(data.replaceability_spending.get('medium', 0)),
        'low_repl_count': data.replaceability_counts.get('low', 0),
        'low_repl_spending': _format_currency(data.replaceability_spending.get('low', 0)),
        'none_repl_count': data.replaceability_counts.get('none', 0),
        'none_repl_spending': _format_currency(data.replaceability_spending.get('none', 0)),
        # V2 format flag and additional data
        'is_v2_format': data.is_v2_format,
    }

    # Add v2-specific template variables
    if data.is_v2_format:
        template_context.update({
            'dimension_heatmap': dimension_heatmap,
            'classification_chart': classification_chart,
            'very_low_repl_count': data.replaceability_counts.get('very_low', 0),
            'very_low_repl_spending': _format_currency(data.replaceability_spending.get('very_low', 0)),
            'unknown_repl_count': data.replaceability_counts.get('unknown', 0),
            'unknown_repl_spending': _format_currency(data.replaceability_spending.get('unknown', 0)),
            # Classification breakdown
            'platform_count': data.classification_counts.get('platform', 0),
            'platform_spending': _format_currency(data.classification_spending.get('platform', 0)),
            'curriculum_platform_count': data.classification_counts.get('curriculum_platform', 0),
            'curriculum_platform_spending': _format_currency(data.classification_spending.get('curriculum_platform', 0)),
            'services_count': data.classification_counts.get('services', 0),
            'services_spending': _format_currency(data.classification_spending.get('services', 0)),
            'physical_count': data.classification_counts.get('physical', 0),
            'physical_spending': _format_currency(data.classification_spending.get('physical', 0)),
            'hybrid_count': data.classification_counts.get('hybrid', 0),
            'hybrid_spending': _format_currency(data.classification_spending.get('hybrid', 0)),
            # Criticality breakdown
            'core_count': data.criticality_counts.get('core', 0),
            'core_spending': _format_currency(data.criticality_spending.get('core', 0)),
            'important_count': data.criticality_counts.get('important', 0),
            'important_spending': _format_currency(data.criticality_spending.get('important', 0)),
            'supplementary_count': data.criticality_counts.get('supplementary', 0),
            'supplementary_spending': _format_currency(data.criticality_spending.get('supplementary', 0)),
            # Dimension averages
            'avg_technical': f"{data.dimension_metrics.average_scores.get('technical_buildability', 0):.1f}" if data.dimension_metrics else "N/A",
            'avg_content': f"{data.dimension_metrics.average_scores.get('content_ip', 0):.1f}" if data.dimension_metrics else "N/A",
            'avg_switching': f"{data.dimension_metrics.average_scores.get('switching_cost', 0):.1f}" if data.dimension_metrics else "N/A",
            'avg_alternatives': f"{data.dimension_metrics.average_scores.get('market_alternatives', 0):.1f}" if data.dimension_metrics else "N/A",
            'avg_portability': f"{data.dimension_metrics.average_scores.get('data_portability', 0):.1f}" if data.dimension_metrics else "N/A",
        })

    # Render template
    html_content = template.render(**template_context)

    output_files = {}

    # Write HTML
    if 'html' in formats:
        html_path = output_dir / 'edtech_spending_report.html'
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        output_files['html'] = html_path
        print(f"HTML report saved to: {html_path}")

    # Generate PDF if requested
    if 'pdf' in formats:
        try:
            from weasyprint import HTML, CSS
            from weasyprint.text.fonts import FontConfiguration

            pdf_path = output_dir / 'edtech_spending_report.pdf'

            print("Generating PDF (this may take a moment)...")

            font_config = FontConfiguration()
            html_doc = HTML(string=html_content)

            # Additional CSS for PDF
            pdf_css = CSS(string='''
                @page {
                    margin: 0.5in;
                    size: letter;
                }
                body {
                    font-size: 10pt;
                }
                .treemap-container {
                    display: none;
                }
                .treemap-container::after {
                    content: "[Interactive treemap - view HTML version]";
                    display: block;
                    padding: 20px;
                    background: #f5f7fa;
                    text-align: center;
                    color: #666;
                }
            ''', font_config=font_config)

            html_doc.write_pdf(
                pdf_path,
                stylesheets=[pdf_css],
                font_config=font_config,
            )

            output_files['pdf'] = pdf_path
            print(f"PDF report saved to: {pdf_path}")

        except ImportError:
            print("Warning: weasyprint not installed. Skipping PDF generation.")
            print("Install with: pip install weasyprint")
        except Exception as e:
            print(f"Warning: PDF generation failed: {e}")
            print("HTML report was generated successfully.")

    return output_files


def main():
    """Run report generation from command line."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate EdTech Spending Analysis Report"
    )
    parser.add_argument(
        '--format', '-f',
        choices=['html', 'pdf', 'both'],
        default='html',
        help="Output format (default: html)"
    )
    parser.add_argument(
        '--output-dir', '-o',
        type=Path,
        help="Output directory (default: reports/)"
    )
    parser.add_argument(
        '--data-dir', '-d',
        type=Path,
        help="Data directory (default: data/)"
    )

    args = parser.parse_args()

    if args.format == 'both':
        formats = ['html', 'pdf']
    else:
        formats = [args.format]

    output_files = generate_report(
        output_dir=args.output_dir,
        data_dir=args.data_dir,
        formats=formats,
    )

    print("\nReport generation complete!")
    for fmt, path in output_files.items():
        print(f"  {fmt.upper()}: {path}")


if __name__ == '__main__':
    main()
