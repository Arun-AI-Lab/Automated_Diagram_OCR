import pandas as pd
import pdfplumber
import re
from typing import List
import requests
import base64
import os
import io
from dotenv import load_dotenv
from ExtractTable import ExtractTable

# Load environment variables from .env file
load_dotenv()

def extract_bom_from_pdf(pdf_path: str, table_pages: List[int], tmp_dir: str = "tmp") -> pd.DataFrame:
    """
    Extract BOM from table pages in a PDF by parsing raw text with regex. Uses EXTRACTTABLE.com API for table extraction.

    Args:
        pdf_path: Path to the PDF file.
        table_pages: List of 1-based page numbers containing tables.

    Returns:
        DataFrame with extracted BOM data (REF, PART_NUMBER, DESCRIPTION, PAGE).
    """
    all_rows = []
    api_key = os.getenv("EXTRACTTABLE_API_KEY")

    et_sess = ExtractTable(api_key=api_key)
    print(et_sess.check_usage())  # Check credits/validity

    with pdfplumber.open(pdf_path) as pdf:
        for page_num in table_pages:
            # Convert page to image for EXTRACTTABLE API
            try:
                from pdf2image import convert_from_path
                images = convert_from_path(pdf_path, first_page=page_num, last_page=page_num, dpi=300)
                if not images:
                    continue
                img_bytes_io = io.BytesIO()
                images[0].save(img_bytes_io, format='JPEG')
                img_bytes = img_bytes_io.getvalue()

                # Save temp image for API
                os.makedirs(tmp_dir, exist_ok=True)
                temp_img_path = os.path.join(tmp_dir, f"page_{page_num}.jpg")
                with open(temp_img_path, "wb") as f:
                    f.write(img_bytes)
            except Exception as e:
                print(f"Failed to convert page {page_num} to image: {e}")
                continue

            # Process with ExtractTable (returns list of DataFrames, one per table)
            tables = et_sess.process_file(filepath=temp_img_path, output_format="df")
            os.remove(temp_img_path)  # Cleanup

            if tables:
                for table_df in tables:
                    if not table_df.empty:
                        # Clean column names and print for debugging
                        table_df.columns = table_df.columns.str.strip()
                        print(f"Columns for page {page_num}: {table_df.columns.tolist()}")

                        if len(table_df.columns) >= 4:  # Ensure at least 4 columns
                            # Map columns based on fixed indices (2nd, 3rd, 4th columns)
                            ref_col = table_df.columns[1]  # "Item" column (2nd)
                            pn_col = table_df.columns[2]   # "Part No." column (3rd)
                            desc_col = table_df.columns[4] # "Description" column (4th)

                            # Directly populate rows from DataFrame, preserving description
                            for _, row in table_df.iterrows():
                                ref = str(row[ref_col]).strip()
                                pn = str(row[pn_col]).strip()
                                desc = str(row[desc_col]).strip()
                                # Only include rows where PART_NUMBER is numeric and REF is a number
                                if pn.isdigit() and ref.isdigit():
                                    all_rows.append({
                                        'REF': ref,
                                        'PART_NUMBER': pn,
                                        'DESCRIPTION': desc,
                                        'PAGE': page_num
                                    })

    return pd.DataFrame(all_rows)