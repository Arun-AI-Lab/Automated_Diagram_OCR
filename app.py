import streamlit as st
import os
import fitz  # PyMuPDF
import pandas as pd
from utils.bom_handler import extract_bom_from_pdf
from utils.pdf_to_tiff import convert_pdf_to_tiffs
from utils.ocr_client import detect_text_with_boxes
from utils.postprocess import extract_part_boxes
from utils.linker import link_parts_by_page, find_anomalies
from PIL import Image, ImageDraw

# Set up Streamlit page
st.set_page_config(page_title="Exploded View OCR", layout="wide")
st.title("Exploded View OCR")

os.makedirs("tmp", exist_ok=True)

# Cached function
@st.cache_data(show_spinner="Extracting BOM from PDF...")
def extract_bom_cached(pdf_path: str, table_pages: list, manufacturer: str):
    return extract_bom_from_pdf(pdf_path, table_pages, manufacturer)

# Step 0: Manufacturer selection
st.subheader("Step 0: Select Manufacturer")
manufacturer = st.selectbox("Manufacturer", ["Liebherr", "Viking"])

# Step 1: PDF upload
uploaded_pdf = st.file_uploader("Upload Exploded View PDF", type=["pdf"])
if uploaded_pdf:
    pdf_path = os.path.join("tmp", uploaded_pdf.name)
    with open(pdf_path, "wb") as f:
        f.write(uploaded_pdf.getbuffer())
    st.success(f"PDF uploaded: {uploaded_pdf.name}")

    # Extract page count
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    doc.close()
    st.info(f"Total pages in PDF: {total_pages}")

    # Step 2: Page selection
    st.subheader("Step 2: Select Pages")
    diagram_pages = st.text_input("Enter diagram pages (e.g., 1,3,5-7):")
    table_pages = st.text_input("Enter table pages (e.g., 2,4,8):")

    def parse_page_range(input_str, total_pages):
        pages = set()
        if not input_str:
            return []
        for p in input_str.split(","):
            p = p.strip()
            if "-" in p:
                try:
                    start, end = map(int, p.split("-"))
                    for i in range(start, end + 1):
                        if 1 <= i <= total_pages:
                            pages.add(i)
                except ValueError:
                    continue
            elif p.isdigit():
                i = int(p)
                if 1 <= i <= total_pages:
                    pages.add(i)
        return sorted(pages)

    diagram_pages_list = parse_page_range(diagram_pages, total_pages)
    table_pages_list = parse_page_range(table_pages, total_pages)

    # Step 3: BOM extraction
    extracted_bom_df = pd.DataFrame()
    if table_pages_list:
        st.subheader("Step 3: Extract BOM from PDF")
        if st.button("Extract BOM Table"):
            extracted_bom_df = extract_bom_cached(pdf_path, tuple(table_pages_list), manufacturer)
            if not extracted_bom_df.empty:
                st.success("Extracted BOM from PDF:")
                st.dataframe(extracted_bom_df)
            else:
                st.warning("No valid BOM data extracted.")

    # Step 4: OCR and Linking
    if diagram_pages_list and not extracted_bom_df.empty:
        st.subheader("Step 4: Run OCR and Link Parts")
        if st.button("Run OCR and Link"):
            tiff_files = convert_pdf_to_tiffs(pdf_path, diagram_pages_list)
            bom_refs = set(extracted_bom_df["REF"].astype(str).str.upper())
            detected_refs_by_page = {}
            annotated_images = {}
            # ... (rest of Step 4 unchanged, as per your code)
            for page_num, tiff_path in zip(diagram_pages_list, tiff_files):
                full_text, words = detect_text_with_boxes(tiff_path)
                part_boxes = extract_part_boxes(words, bom_refs)
                detected_refs_by_page[page_num] = part_boxes
                detected_tokens = {box["token"] for box in part_boxes}
                st.write(f"Page {page_num} detected tokens: {detected_tokens}")
                st.write(f"BOM refs: {bom_refs}")
                img = Image.open(tiff_path).convert("RGB")
                draw = ImageDraw.Draw(img)
                for box in part_boxes:
                    x, y, w, h = box["x"], box["y"], box["w"], box["h"]
                    x0, y0 = x - w / 2, y - h / 2
                    x1, y1 = x + w / 2, y + h / 2
                    color = "green" if box["color"] == "green" else "red"
                    draw.rectangle([x0, y0, x1, y1], outline=color, width=3)
                annotated_path = os.path.join("tmp", f"annotated_diagram_{page_num}.png")
                img.save(annotated_path)
                annotated_images[page_num] = annotated_path
            linked_tables = link_parts_by_page(detected_refs_by_page, extracted_bom_df)
            anomalies_table = find_anomalies(
                {p: {b["token"] for b in boxes} for p, boxes in detected_refs_by_page.items()},
                extracted_bom_df
            )
            st.subheader("Linked BOM Tables (per diagram page)")
            for page_num in diagram_pages_list:
                st.markdown(f"**Diagram Page {page_num}**")
                st.image(annotated_images[page_num], caption=f"Diagram {page_num}", use_container_width=True)
                st.dataframe(linked_tables.get(page_num, pd.DataFrame()))
            st.subheader("Anomalies Table")
            st.dataframe(anomalies_table)