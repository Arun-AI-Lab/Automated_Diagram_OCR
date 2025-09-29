import os
import fitz  # PyMuPDF
from PIL import Image

def convert_pdf_to_tiffs(pdf_path, page_indices, output_dir="tmp/diagram_tiffs", dpi=300):
    """
    Convert selected PDF pages to TIFFs using PyMuPDF.
    Args:
        pdf_path: path to input PDF
        page_indices: list of 1-based page indices (user input)
        output_dir: folder to store TIFF files
        dpi: rendering resolution
    Returns:
        List of output TIFF file paths
    """
    os.makedirs(output_dir, exist_ok=True)
    doc = fitz.open(pdf_path)

    output_files = []
    zoom = dpi / 72  # scale factor (72 dpi is PDF default)
    mat = fitz.Matrix(zoom, zoom)

    for page_num in page_indices:
        page_index = page_num - 1  # Convert to 0-based index
        if page_index < 0 or page_index >= len(doc):
            continue
        page = doc[page_index]
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        out_file = os.path.join(output_dir, f"diagram_page_{page_num}.tiff")
        img.save(out_file, "TIFF")
        output_files.append(out_file)

    doc.close()
    return output_files