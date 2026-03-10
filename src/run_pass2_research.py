"""
Run Pass 2 detailed AI research on EdTech vendors.

This script uses the Claude API to research top EdTech vendors and assess
their replaceability for in-house development.

Usage:
    export ANTHROPIC_API_KEY="your-api-key"
    python3 src/run_pass2_research.py
"""

import pandas as pd
import os
import sys
from vendor_research import research_edtech_vendors_pass2

def main():
    # Check for API key
    api_key = os.environ.get('ANTHROPIC_API_KEY')

    if not api_key:
        print("=" * 80)
        print("ERROR: ANTHROPIC_API_KEY environment variable not set")
        print("=" * 80)
        print()
        print("To run Pass 2 AI research, you need to provide your Anthropic API key.")
        print()
        print("Steps:")
        print("1. Get your API key from: https://console.anthropic.com/")
        print("2. Set the environment variable:")
        print("   export ANTHROPIC_API_KEY='your-api-key-here'")
        print("3. Run this script again")
        print()
        sys.exit(1)

    # Load EdTech vendors for research
    edtech_df = pd.read_csv('data/vendors/edtech_vendors_for_research.csv')

    print("=" * 80)
    print("PASS 2: AI-POWERED EDTECH VENDOR RESEARCH")
    print("=" * 80)
    print()
    print("This will research the top EdTech vendors using Claude AI to assess:")
    print("  - Primary products and services")
    print("  - Target use cases in schools")
    print("  - Replaceability (high/medium/low/none)")
    print("  - Detailed rationale")
    print()

    high_priority = edtech_df[edtech_df['research_priority'] == 'high']
    print(f"High priority vendors: {len(high_priority)}")
    print(f"Total spending: ${high_priority['total_spending'].sum():,.2f}")
    print()

    # Ask for confirmation
    response = input("Proceed with AI research? This will make API calls (costs ~$0.01-0.02 per vendor). [y/N]: ")

    if response.lower() != 'y':
        print("Cancelled.")
        sys.exit(0)

    # Run research
    print()
    results_df = research_edtech_vendors_pass2(
        edtech_df,
        priority='high',
        api_key=api_key
    )

    # Print summary
    print()
    print("=" * 80)
    print("RESEARCH SUMMARY")
    print("=" * 80)
    print()

    if len(results_df) > 0 and 'replaceability' in results_df.columns:
        print("Replaceability Distribution:")
        replace_counts = results_df['replaceability'].value_counts()
        for level, count in replace_counts.items():
            total_spending = results_df[results_df['replaceability'] == level]['total_spending'].sum()
            print(f"  {level.upper():6s}: {count:2d} vendors, ${total_spending:>12,.2f}")

        print()
        print("High Replaceability Vendors:")
        high_replace = results_df[results_df['replaceability'] == 'high'].sort_values('total_spending', ascending=False)
        for idx, row in high_replace.iterrows():
            print(f"  - {row['vendor_name']:50s} ${row['total_spending']:>12,.2f}")
            print(f"    {row.get('product_descriptions', 'N/A')[:100]}")

    print()
    print("✓ Research complete!")
    print("✓ Results saved to: data/vendors/edtech_research_pass2_high.json")


if __name__ == "__main__":
    main()
