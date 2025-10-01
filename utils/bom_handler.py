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

# Header ignore words per manufacturer
HEADER_IGNORE = {
    "liebherr": {"remark", "item", "part no.", "quantity", "description", "price"},
    "viking": {"item", "part no.", "name", "qty", "uom", "note"},
}


def _process_page_with_extracttable(pdf_path: str, page_num: int, et_sess, tmp_dir: str = "tmp"):
    """
    Render a PDF page to image and run ExtractTable.
    Returns list of DataFrames or [] if failed.
    """
    try:
        with fitz.open(pdf_path) as pdf_doc:
            page_doc = pdf_doc[page_num - 1]  # 1-based -> 0-based
            pix = page_doc.get_pixmap(matrix=fitz.Matrix(300/72, 300/72))  # 300 DPI
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            img_bytes_io = io.BytesIO()
            img.save(img_bytes_io, format="JPEG")
            img_bytes = img_bytes_io.getvalue()

            os.makedirs(tmp_dir, exist_ok=True)
            temp_img_path = os.path.join(tmp_dir, f"page_{page_num}.jpg")
            with open(temp_img_path, "wb") as f:
                f.write(img_bytes)

            # Process with ExtractTable
            tables = et_sess.process_file(filepath=temp_img_path, output_format="df")

            os.remove(temp_img_path)  # cleanup
            return tables or []

    except Exception as e:
        print(f"Failed to process page {page_num}: {e}")
        return []


def _should_ignore_row(ref: str, pn: str, desc: str, manufacturer: str) -> bool:
    """
    Check if the row looks like a header (to be ignored).
    """
    ignore_words = HEADER_IGNORE.get(manufacturer.lower(), set())
    row_text = f"{ref} {pn} {desc}".lower()
    return any(word in row_text for word in ignore_words)


def extract_bom_liebherr(pdf_path: str, table_pages: List[int], tmp_dir: str = "tmp") -> pd.DataFrame:
    """
    Extract BOM for Liebherr PDFs.
    Columns: REF=col1, PART_NUMBER=col2, DESCRIPTION=col4
    """
    all_rows = []
    api_key = os.getenv("EXTRACTTABLE_API_KEY")
    et_sess = ExtractTable(api_key=api_key)
    print("Liebherr usage check:", et_sess.check_usage())

    for page_num in table_pages:
        tables = _process_page_with_extracttable(pdf_path, page_num, et_sess, tmp_dir)
        for table_df in tables:
            if not table_df.empty and len(table_df.columns) >= 5:
                table_df.columns = table_df.columns.str.strip()
                print(f"[Liebherr] Page {page_num} columns: {table_df.columns.tolist()}")
                ref_col, pn_col, desc_col = table_df.columns[1], table_df.columns[2], table_df.columns[4]

                for _, row in table_df.iterrows():
                    ref = str(row[ref_col]).strip()
                    pn = str(row[pn_col]).strip()
                    desc = str(row[desc_col]).strip()

                    if not ref or not pn:
                        continue
                    if _should_ignore_row(ref, pn, desc, "liebherr"):
                        continue

                    all_rows.append({
                        "REF": ref,
                        "PART_NUMBER": pn,
                        "DESCRIPTION": desc,
                        "PAGE": page_num
                    })

    return pd.DataFrame(all_rows)


def extract_bom_viking(pdf_path: str, table_pages: List[int], tmp_dir: str = "tmp") -> pd.DataFrame:
    """
    Extract BOM for Viking PDFs.
    Columns: REF=col0, PART_NUMBER=col1, DESCRIPTION=col2
    """
    all_rows = []
    api_key = os.getenv("EXTRACTTABLE_API_KEY")
    et_sess = ExtractTable(api_key=api_key)
    print("Viking usage check:", et_sess.check_usage())

    for page_num in table_pages:
        tables = _process_page_with_extracttable(pdf_path, page_num, et_sess, tmp_dir)
        for table_df in tables:
            if not table_df.empty and len(table_df.columns) >= 3:
                table_df.columns = table_df.columns.str.strip()
                print(f"[Viking] Page {page_num} columns: {table_df.columns.tolist()}")
                ref_col, pn_col, desc_col = table_df.columns[0], table_df.columns[1], table_df.columns[2]

                for _, row in table_df.iterrows():
                    ref = str(row[ref_col]).strip()
                    pn = str(row[pn_col]).strip()
                    desc = str(row[desc_col]).strip()

                    if not ref or not pn:
                        continue
                    if _should_ignore_row(ref, pn, desc, "viking"):
                        continue

                    all_rows.append({
                        "REF": ref,
                        "PART_NUMBER": pn,
                        "DESCRIPTION": desc,
                        "PAGE": page_num
                    })

    return pd.DataFrame(all_rows)


def extract_bom_from_pdf(pdf_path: str, table_pages: List[int], manufacturer: str, tmp_dir: str = "tmp") -> pd.DataFrame:
    """
    Dispatcher: call manufacturer-specific BOM extractor.
    """
    manufacturer = manufacturer.lower()
    if manufacturer == "liebherr":
        return extract_bom_liebherr(pdf_path, table_pages, tmp_dir)
    elif manufacturer == "viking":
        return extract_bom_viking(pdf_path, table_pages, tmp_dir)
    else:
        raise ValueError(f"Unsupported manufacturer: {manufacturer}. Please implement extractor.")
