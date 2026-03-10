"""
Run the PDF extraction process for all Dallas ISD check registers.
This script executes the logic from notebook 01_data_extraction.ipynb
"""

import pandas as pd
import numpy as np
from pathlib import Path
import pdfplumber
from datetime import datetime
import json
import warnings
warnings.filterwarnings('ignore')

# Set display options
pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', 100)
pd.set_option('display.width', None)

print("="*80)
print("Dallas ISD Check Register Data Extraction")
print("="*80)
print()

# Set up paths
DATA_DIR = Path('../data')
RAW_DIR = DATA_DIR / 'raw'
EXTRACTED_DIR = DATA_DIR / 'extracted'
EXTRACTED_DIR.mkdir(exist_ok=True)

# Get list of all PDF files
pdf_files = sorted(list(RAW_DIR.glob('*.pdf')))
print(f"✓ Found {len(pdf_files)} PDF files")
print(f"✓ Date range: {pdf_files[0].stem} to {pdf_files[-1].stem}")
print()

# Step 1: Examine sample PDF structure
print("STEP 1: Examining PDF structure...")
print("-" * 80)

sample_pdf = pdf_files[0]
print(f"Sample file: {sample_pdf.name}")

with pdfplumber.open(sample_pdf) as pdf:
    print(f"  Total pages: {len(pdf.pages)}")
    print(f"  Page dimensions: {pdf.pages[0].width} x {pdf.pages[0].height}")

    # Extract first page to see structure
    first_page = pdf.pages[0]
    tables = first_page.extract_tables()
    print(f"  Tables on first page: {len(tables)}")

    if tables:
        print(f"  First table: {len(tables[0])} rows x {len(tables[0][0])} columns")
        print(f"  Header row: {tables[0][0]}")
        print(f"  First data row: {tables[0][1]}")

print()

# Check format consistency across time periods
print("Checking format consistency...")
middle_pdf = [f for f in pdf_files if '2023-06' in f.name][0]
recent_pdf = [f for f in pdf_files if '2025-06' in f.name][0]

for pdf_file in [sample_pdf, middle_pdf, recent_pdf]:
    with pdfplumber.open(pdf_file) as pdf:
        first_page = pdf.pages[0]
        tables = first_page.extract_tables()

        print(f"  {pdf_file.name}: {len(pdf.pages)} pages, {len(tables)} tables on page 1")
        if tables:
            print(f"    Columns: {len(tables[0][0])}")

print()

# Step 2: Build extraction function
print("STEP 2: Building extraction function...")
print("-" * 80)

def extract_transactions_from_pdf(pdf_path, debug=False):
    """
    Extract transaction data from a Dallas ISD check register PDF.

    Args:
        pdf_path: Path to the PDF file
        debug: If True, print debug information

    Returns:
        DataFrame with extracted transactions
    """
    all_rows = []
    header = None

    with pdfplumber.open(pdf_path) as pdf:
        if debug:
            print(f"Processing {pdf_path.name}: {len(pdf.pages)} pages")

        for page_num, page in enumerate(pdf.pages, 1):
            # Extract tables from page
            tables = page.extract_tables()

            for table_idx, table in enumerate(tables):
                if not table or len(table) < 2:  # Skip empty tables
                    continue

                # Get header from first table if we don't have it yet
                if header is None and table[0]:
                    header = table[0]

                # Process data rows (skip header row)
                for row_idx, row in enumerate(table[1:]):
                    if row and any(cell and str(cell).strip() for cell in row if cell):  # Skip empty rows
                        all_rows.append(row)

    if not all_rows:
        if debug:
            print(f"  Warning: No data extracted from {pdf_path.name}")
        return pd.DataFrame()

    # Create DataFrame
    if header:
        df = pd.DataFrame(all_rows, columns=header)
    else:
        df = pd.DataFrame(all_rows)

    # Add source file info
    df['source_file'] = pdf_path.name
    df['extraction_date'] = datetime.now()

    if debug:
        print(f"  Extracted {len(df)} transactions")

    return df

print("✓ Extraction function created")
print()

# Step 3: Test extraction on sample PDFs
print("STEP 3: Testing extraction on sample files...")
print("-" * 80)

test_df = extract_transactions_from_pdf(pdf_files[0], debug=True)
print(f"\nTest results:")
print(f"  Shape: {test_df.shape}")
print(f"  Columns: {list(test_df.columns)}")
print(f"\nFirst 5 rows:")
print(test_df.head())
print()

# Test on files across time range
print("Testing consistency across date range...")
test_files = [pdf_files[0], pdf_files[len(pdf_files)//2], pdf_files[-1]]

for pdf_file in test_files:
    df = extract_transactions_from_pdf(pdf_file, debug=True)
    print(f"  Shape: {df.shape}, Columns: {len(df.columns)}")

print()

# Step 4: Extract all PDFs
print("STEP 4: Extracting all 48 PDFs...")
print("-" * 80)

all_transactions = []
failed_files = []

for i, pdf_file in enumerate(pdf_files, 1):
    try:
        print(f"[{i}/{len(pdf_files)}] {pdf_file.name}...", end=' ')
        df = extract_transactions_from_pdf(pdf_file)

        if len(df) > 0:
            all_transactions.append(df)
            print(f"✓ {len(df):,} transactions")
        else:
            print("✗ No data")
            failed_files.append(pdf_file.name)

    except Exception as e:
        print(f"✗ Error: {e}")
        failed_files.append(pdf_file.name)

print()
print("=" * 80)
print(f"Extraction complete: {len(all_transactions)}/{len(pdf_files)} files successful")
if failed_files:
    print(f"Failed files: {failed_files}")
print()

# Step 5: Combine and analyze
print("STEP 5: Combining and analyzing data...")
print("-" * 80)

combined_df = pd.concat(all_transactions, ignore_index=True)

print(f"✓ Total transactions: {len(combined_df):,}")
print(f"✓ Columns: {list(combined_df.columns)}")
print(f"✓ Date range: {combined_df['source_file'].min()} to {combined_df['source_file'].max()}")
print(f"✓ Shape: {combined_df.shape}")
print()

# Data quality checks
print("Data quality checks:")
print(f"  Missing values by column:")
missing = combined_df.isnull().sum()
for col, count in missing.items():
    if count > 0:
        pct = (count / len(combined_df) * 100)
        print(f"    {col}: {count:,} ({pct:.1f}%)")

print()
print("Transactions per month:")
monthly_counts = combined_df.groupby('source_file').size().sort_index()
print(monthly_counts.to_string())

print()

# Step 6: Save extracted data
print("STEP 6: Saving extracted data...")
print("-" * 80)

# Save to CSV
output_file = EXTRACTED_DIR / 'all_transactions_raw.csv'
combined_df.to_csv(output_file, index=False)
print(f"✓ Saved CSV: {output_file} ({len(combined_df):,} transactions)")

# Save as pickle
pickle_file = EXTRACTED_DIR / 'all_transactions_raw.pkl'
combined_df.to_pickle(pickle_file)
print(f"✓ Saved pickle: {pickle_file}")

# Save metadata
metadata = {
    'extraction_date': datetime.now().isoformat(),
    'total_pdfs': len(pdf_files),
    'successful_extractions': len(all_transactions),
    'failed_files': failed_files,
    'total_transactions': len(combined_df),
    'columns': list(combined_df.columns),
    'date_range': f"{pdf_files[0].name} to {pdf_files[-1].name}"
}

metadata_file = EXTRACTED_DIR / 'extraction_metadata.json'
with open(metadata_file, 'w') as f:
    json.dump(metadata, f, indent=2)
print(f"✓ Saved metadata: {metadata_file}")

print()
print("=" * 80)
print("EXTRACTION COMPLETE!")
print("=" * 80)
print()
print("Summary:")
print(f"  Total transactions extracted: {len(combined_df):,}")
print(f"  Files processed: {len(all_transactions)}/{len(pdf_files)}")
print(f"  Output files:")
print(f"    - {output_file}")
print(f"    - {pickle_file}")
print(f"    - {metadata_file}")
print()
print("Next step: Move to Phase 2 - Vendor Categorization")
