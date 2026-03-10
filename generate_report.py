#!/usr/bin/env python3
"""
EdTech Spending Report Generator CLI

Generate static HTML/PDF reports visualizing Dallas ISD EdTech spending analysis.

Usage:
    python generate_report.py --format both --output-dir reports/
    python generate_report.py --format html
    python generate_report.py --format pdf

"""

import argparse
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="Generate EdTech Spending Analysis Report",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python generate_report.py
        Generate HTML report in reports/ directory

    python generate_report.py --format both
        Generate both HTML and PDF reports

    python generate_report.py --format pdf --output-dir /path/to/output
        Generate PDF report in specified directory
        """,
    )

    parser.add_argument(
        '--format', '-f',
        choices=['html', 'pdf', 'both'],
        default='html',
        help="Output format: html, pdf, or both (default: html)"
    )

    parser.add_argument(
        '--output-dir', '-o',
        type=Path,
        default=None,
        help="Output directory for reports (default: reports/)"
    )

    parser.add_argument(
        '--data-dir', '-d',
        type=Path,
        default=None,
        help="Data directory containing source files (default: data/)"
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help="Enable verbose output"
    )

    args = parser.parse_args()

    # Determine formats
    if args.format == 'both':
        formats = ['html', 'pdf']
    else:
        formats = [args.format]

    print("=" * 60)
    print("EdTech Spending Report Generator")
    print("=" * 60)
    print()

    try:
        # Import here to catch import errors with helpful messages
        from src.reporting import generate_report

        output_files = generate_report(
            output_dir=args.output_dir,
            data_dir=args.data_dir,
            formats=formats,
        )

        print()
        print("=" * 60)
        print("Report generation complete!")
        print("=" * 60)
        print()
        print("Output files:")
        for fmt, path in output_files.items():
            print(f"  [{fmt.upper()}] {path}")

        # Provide helpful next steps
        if 'html' in output_files:
            print()
            print("To view the HTML report:")
            print(f"  open {output_files['html']}")

        return 0

    except ImportError as e:
        print(f"Error: Missing required dependency: {e}")
        print()
        print("Please install required packages:")
        print("  pip install jinja2 matplotlib plotly pandas")
        print()
        print("For PDF support, also install:")
        print("  pip install weasyprint")
        return 1

    except FileNotFoundError as e:
        print(f"Error: {e}")
        print()
        print("Please ensure the data files exist in the data/ directory:")
        print("  - data/vendors/edtech_award_spend_v1.json")
        print("  - data/vendors/edtech_vendors_for_research.csv")
        print("  - data/vendors/vendor_categorization_pass1.csv")
        print("  - data/extracted/all_transactions_raw.csv")
        return 1

    except Exception as e:
        print(f"Error generating report: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
