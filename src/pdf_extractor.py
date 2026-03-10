"""
PDF extraction utilities for Dallas ISD check registers.
Parses text-based PDF format to extract transaction data.
"""

import pdfplumber
import pandas as pd
import re
from datetime import datetime
from pathlib import Path


def extract_transactions_from_pdf(pdf_path, debug=False):
    """
    Extract transaction data from a Dallas ISD check register PDF.

    The PDFs have a specific text format with columns:
    Payee, Check #, Date, Check Amount, Description, Fund, Fund Amount, Check Req Amt

    Args:
        pdf_path: Path to the PDF file
        debug: If True, print debug information

    Returns:
        DataFrame with extracted transactions
    """
    transactions = []

    with pdfplumber.open(pdf_path) as pdf:
        if debug:
            print(f"Processing {pdf_path.name}: {len(pdf.pages)} pages")

        for page_num, page in enumerate(pdf.pages, 1):
            text = page.extract_text()
            if not text:
                continue

            # Split into lines
            lines = text.split('\n')

            # Find the data lines (skip header/footer)
            for i, line in enumerate(lines):
                # Skip header lines
                if any(x in line for x in ['Dallas Independent School District',
                                           'List of Detailed Expenditures',
                                           'Sort By:', 'Date Range:',
                                           'Payee Check # Date Check Amount']):
                    continue

                # Skip page numbers
                if re.match(r'Page \d+ of \d+', line):
                    continue

                # Skip empty lines
                if not line.strip():
                    continue

                # Try to parse as a transaction line
                # Look for patterns like: VENDOR_NAME CHECK# MM/DD/YYYY AMOUNT
                # Check numbers are typically 7-10 digits
                # Dates are in MM/DD/YYYY format
                # Amounts have commas and decimals

                # Pattern: vendor name, then check number (digits), then date, then amount
                match = re.search(r'(\d{7,10})\s+(\d{2}/\d{2}/\d{4})\s+([\d,]+\.\d{2})', line)

                if match:
                    check_num = match.group(1)
                    date_str = match.group(2)
                    amount_str = match.group(3)

                    # Extract vendor name (everything before the check number)
                    vendor_start = 0
                    vendor_end = match.start(1)
                    vendor = line[vendor_start:vendor_end].strip()

                    # Extract description and fund info (everything after amount)
                    desc_start = match.end(3)
                    remainder = line[desc_start:].strip()

                    # Parse the remainder to get description and fund
                    parts = remainder.split()
                    description = parts[0] if parts else ""
                    fund = parts[1] if len(parts) > 1 else ""

                    try:
                        # Convert amount to float
                        amount = float(amount_str.replace(',', ''))

                        transactions.append({
                            'vendor': vendor,
                            'check_number': check_num,
                            'date': date_str,
                            'amount': amount,
                            'description': description,
                            'fund': fund,
                            'raw_line': line
                        })
                    except ValueError:
                        # Skip if amount parsing fails
                        if debug:
                            print(f"  Warning: Could not parse amount '{amount_str}' on page {page_num}")
                        continue

    if not transactions:
        if debug:
            print(f"  Warning: No transactions extracted from {pdf_path.name}")
        return pd.DataFrame()

    # Create DataFrame
    df = pd.DataFrame(transactions)

    # Add metadata
    df['source_file'] = pdf_path.name
    df['extraction_date'] = datetime.now()

    # Convert date column to datetime
    df['date'] = pd.to_datetime(df['date'], format='%m/%d/%Y', errors='coerce')

    if debug:
        print(f"  Extracted {len(df)} transactions")

    return df


def extract_all_pdfs(pdf_dir='data/raw', output_dir='data/extracted', debug=False):
    """
    Extract all PDFs in a directory.

    Args:
        pdf_dir: Directory containing PDF files
        output_dir: Directory to save extracted data
        debug: If True, print debug information

    Returns:
        DataFrame with all transactions
    """
    pdf_path = Path(pdf_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    pdf_files = sorted(list(pdf_path.glob('*.pdf')))

    print(f"Found {len(pdf_files)} PDF files")
    print(f"Extracting data...")
    print("=" * 80)

    all_transactions = []
    failed_files = []

    for i, pdf_file in enumerate(pdf_files, 1):
        try:
            print(f"[{i}/{len(pdf_files)}] {pdf_file.name}...", end=' ')
            df = extract_transactions_from_pdf(pdf_file, debug=False)

            if len(df) > 0:
                all_transactions.append(df)
                print(f"✓ {len(df):,} transactions")
            else:
                print("✗ No data")
                failed_files.append(pdf_file.name)

        except Exception as e:
            print(f"✗ Error: {e}")
            failed_files.append(pdf_file.name)

    print("=" * 80)
    print(f"\nExtraction complete: {len(all_transactions)}/{len(pdf_files)} files successful")

    if failed_files:
        print(f"Failed files: {failed_files}")

    # Combine all transactions
    if all_transactions:
        combined_df = pd.concat(all_transactions, ignore_index=True)
        print(f"\nTotal transactions: {len(combined_df):,}")
        return combined_df
    else:
        print("\nNo transactions extracted!")
        return pd.DataFrame()


if __name__ == "__main__":
    df = extract_all_pdfs(debug=False)

    if len(df) > 0:
        # Save to CSV
        output_file = Path('data/extracted/all_transactions_raw.csv')
        df.to_csv(output_file, index=False)
        print(f"\n✓ Saved to {output_file}")

        # Print summary
        print(f"\nSummary:")
        print(f"  Total transactions: {len(df):,}")
        print(f"  Total amount: ${df['amount'].sum():,.2f}")
        print(f"  Date range: {df['date'].min()} to {df['date'].max()}")
        print(f"  Unique vendors: {df['vendor'].nunique():,}")
