"""
PDF downloader for Dallas ISD check registers.
Handles redirect links and downloads all monthly PDFs from Sept 2021 to Aug 2025.
"""

import requests
import os
from pathlib import Path
import time
from typing import Dict, List, Tuple

# Mapping of month/year to UUID for all 48 check registers
CHECK_REGISTER_URLS = {
    "2021-09": "18f508a1-f021-49e8-bd9b-4e8bf4ca751a",
    "2021-10": "6d8f2c6d-ae1b-4ae7-9350-a0d93e8d0901",
    "2021-11": "c37857f6-792c-419b-9d8d-7676045eb451",
    "2021-12": "94b7b3cb-1744-44d8-bad0-8ee3043a16e7",
    "2022-01": "3aa2f7cd-acf7-4ae0-ac67-f7948596c1fc",
    "2022-02": "b0ea16f4-7938-4655-8145-4d46a763f2da",
    "2022-03": "99611ed5-958f-4621-a6d3-25cd9747d643",
    "2022-04": "17c4106a-bb53-49b5-b9c7-8968f8d25166",
    "2022-05": "3baf2899-bd9e-47c2-a6d0-154ba10c38d1",
    "2022-06": "528cd3e4-553e-4e16-8545-6f4e346ca0c6",
    "2022-07": "d36140d6-40aa-49a1-bf8d-995bfba34ac9",
    "2022-08": "ff93a8ff-70cf-4577-bc1f-3443a0059667",
    "2022-09": "e2fe0699-67b8-4e3c-b4da-77871412a79b",
    "2022-10": "53d9f33f-6185-4832-858f-9d8e3a005638",
    "2022-11": "171e5d46-7898-4379-b00d-535a05dafc30",
    "2022-12": "3c75d223-0fbc-403a-ac1d-97a0a88b8e03",
    "2023-01": "996de7d0-53c3-4ff0-8b14-10143f56aa72",
    "2023-02": "08986108-cf16-464c-bf3e-acdbde92ab13",
    "2023-03": "cc041396-2780-4412-9121-8981ddb423bb",
    "2023-04": "12d2ca68-3a09-4064-8c85-74478865ccd8",
    "2023-05": "cdb22ed6-3b6c-451a-bb36-1188d1b2a8f8",
    "2023-06": "6fd9efab-f3b8-4a75-9dd2-860c7b6ed853",
    "2023-07": "d812ed19-7fec-4b0f-ac11-39e258008e8e",
    "2023-08": "a79ea169-bdac-4518-9d80-99ee098bcf56",
    "2023-09": "3f2e57d3-d667-4502-abcc-bb5bc27370d3",
    "2023-10": "2f42d806-d522-4354-a96c-0f54065e8052",
    "2023-11": "095fdf53-221b-4905-b768-3ae54485c563",
    "2023-12": "7a33d9de-d855-4b6a-bb07-ec518450d2af",
    "2024-01": "1c44c79b-ab6e-4bd6-8fcb-c46c05874da8",
    "2024-02": "5c271fa1-5ae2-4bde-8a7a-ef90eb17eee7",
    "2024-03": "19579962-41ad-418d-9173-8746094c550c",
    "2024-04": "9eabe79b-8a70-48e9-bf0d-7f98057a97ce",
    "2024-05": "248b24a9-eecd-4e85-9de9-3601be07f8fa",
    "2024-06": "3eab951e-72d5-4cdc-ad0e-5dd0f095fbd3",
    "2024-07": "f43cc8ce-38df-44d8-953d-63b5cc87fd05",
    "2024-08": "0f5edc81-558a-4dee-b78e-5c3626f5f864",
    "2024-09": "2d2d4f21-8f1d-4f9d-aca6-7ee04dddad56",
    "2024-10": "5e8ca587-0d6d-4150-bc6e-aa59174a5117",
    "2024-11": "fc4b378f-3bcd-4ade-a258-8e455beece9a",
    "2024-12": "a53783e7-d250-4a21-8740-3a74078a4302",
    "2025-01": "a062b77e-b87e-43af-8b31-5756fbb1c6ab",
    "2025-02": "e264c6ff-6d6a-4fe7-8556-0091d7afa098",
    "2025-03": "aa2ba972-88e0-44d0-a63a-99d94ac141fc",
    "2025-04": "592b3e90-321b-4316-b3f1-3bcc3d991312",
    "2025-05": "dd67a654-3e49-46f1-afcf-a16c906048f7",
    "2025-06": "fd41eb00-fe1b-48b6-ac4d-936e8b274eb8",
    "2025-07": "b02cee6a-1482-4485-864e-2998a88ee94b",
    "2025-08": "c4c84838-8898-4c9e-a47a-e6d7ad154efa",
}


def download_pdf(url: str, output_path: Path, max_retries: int = 3) -> bool:
    """
    Download a PDF from the given URL with retry logic.

    Args:
        url: The URL to download from
        output_path: Path where the PDF should be saved
        max_retries: Maximum number of retry attempts

    Returns:
        True if download successful, False otherwise
    """
    for attempt in range(max_retries):
        try:
            # Use a session to handle redirects properly
            session = requests.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })

            # Make the request with redirect following enabled
            response = session.get(url, allow_redirects=True, timeout=30)
            response.raise_for_status()

            # Check if we got a PDF
            content_type = response.headers.get('Content-Type', '')
            if 'pdf' not in content_type.lower() and len(response.content) < 1000:
                print(f"    Warning: Response may not be a PDF (Content-Type: {content_type})")
                if attempt < max_retries - 1:
                    print(f"    Retrying... (attempt {attempt + 2}/{max_retries})")
                    time.sleep(2)
                    continue

            # Write the PDF content to file
            with open(output_path, 'wb') as f:
                f.write(response.content)

            # Verify the file was written
            file_size = output_path.stat().st_size
            if file_size < 1000:
                print(f"    Warning: File size is suspiciously small ({file_size} bytes)")
                if attempt < max_retries - 1:
                    print(f"    Retrying... (attempt {attempt + 2}/{max_retries})")
                    time.sleep(2)
                    continue

            print(f"    ✓ Downloaded successfully ({file_size:,} bytes)")
            return True

        except requests.exceptions.RequestException as e:
            print(f"    Error on attempt {attempt + 1}/{max_retries}: {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
            else:
                return False

    return False


def download_all_check_registers(output_dir: str = "data/raw",
                                 skip_existing: bool = True) -> Tuple[List[str], List[str]]:
    """
    Download all check register PDFs.

    Args:
        output_dir: Directory to save PDFs (relative to project root)
        skip_existing: If True, skip files that already exist

    Returns:
        Tuple of (successful_downloads, failed_downloads)
    """
    # Create output directory if it doesn't exist
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    successful = []
    failed = []

    print(f"Starting download of {len(CHECK_REGISTER_URLS)} check registers...")
    print(f"Output directory: {output_path.absolute()}\n")

    for month_year, uuid in CHECK_REGISTER_URLS.items():
        filename = f"{month_year}_check_register.pdf"
        file_path = output_path / filename

        # Check if file already exists
        if skip_existing and file_path.exists():
            file_size = file_path.stat().st_size
            if file_size > 1000:  # Only skip if file is reasonably sized
                print(f"[{month_year}] Skipping (already exists, {file_size:,} bytes)")
                successful.append(month_year)
                continue
            else:
                print(f"[{month_year}] Re-downloading (existing file too small)")

        # Construct the URL
        url = f"https://www.dallasisd.org/fs/resource-manager/view/{uuid}"

        print(f"[{month_year}] Downloading from {url}")

        # Download the PDF
        if download_pdf(url, file_path):
            successful.append(month_year)
        else:
            failed.append(month_year)
            print(f"    ✗ Failed to download")

        # Be polite and don't hammer the server
        time.sleep(1)

    # Print summary
    print("\n" + "="*70)
    print(f"Download complete!")
    print(f"Successful: {len(successful)}/{len(CHECK_REGISTER_URLS)}")
    print(f"Failed: {len(failed)}/{len(CHECK_REGISTER_URLS)}")

    if failed:
        print(f"\nFailed downloads: {', '.join(failed)}")

    return successful, failed


if __name__ == "__main__":
    download_all_check_registers()
