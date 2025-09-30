import pandas as pd
import fitz  # PyMuPDF
from typing import List
import os
import io
from PIL import Image
from dotenv import load_dotenv
from ExtractTable import ExtractTable

# Load environment variables from .env file
load_dotenv()

def extract_bom_from_pdf(pdf_path: str, table_pages: List[int], tmp_dir: str = "tmp") -> pd.DataFrame:
    """
    Extract BOM from table pages in a PDF by converting pages to images using PyMuPDF and
    processing with the ExtractTable.com API.

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

    for page_num in table_pages:
        image_based = True
        try:
            with fitz.open(pdf_path) as pdf_doc:
                page_doc = pdf_doc[page_num - 1]  # 0-based index
                pix = page_doc.get_pixmap(matrix=fitz.Matrix(300/72, 300/72))  # 300 DPI
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                img_bytes_io = io.BytesIO()
                img.save(img_bytes_io, format='JPEG')
                img_bytes = img_bytes_io.getvalue()

                os.makedirs(tmp_dir, exist_ok=True)
                temp_img_path = os.path.join(tmp_dir, f"page_{page_num}.jpg")
                with open(temp_img_path, "wb") as f:
                    f.write(img_bytes)

                # Process with ExtractTable
                tables = et_sess.process_file(filepath=temp_img_path, output_format="df")
                os.remove(temp_img_path)  # Cleanup

                if tables:
                    for table_df in tables:
                        if not table_df.empty:
                            table_df.columns = table_df.columns.str.strip()
                            print(f"Columns for page {page_num} (image-based): {table_df.columns.tolist()}")
                            if len(table_df.columns) >= 4:
                                ref_col, pn_col, desc_col = table_df.columns[1], table_df.columns[2], table_df.columns[4]
                                for _, row in table_df.iterrows():
                                    ref = str(row[ref_col]).strip()
                                    pn = str(row[pn_col]).strip()
                                    desc = str(row[desc_col]).strip()
                                    if pn.isdigit() and ref.isdigit():
                                        all_rows.append({
                                            'REF': ref,
                                            'PART_NUMBER': pn,
                                            'DESCRIPTION': desc,
                                            'PAGE': page_num
                                        })
        except Exception as e:
            print(f"Failed to process page {page_num} as image: {e}")
            continue

    return pd.DataFrame(all_rows)