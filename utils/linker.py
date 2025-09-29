import pandas as pd
from typing import Dict, List, Set

def link_parts_by_page(
    detected_refs_by_page: Dict[int, List[Dict]],  # now expects list of box dicts
    bom_df: pd.DataFrame
) -> Dict[int, pd.DataFrame]:
    """
    For each diagram page, return a DataFrame of linked BOM rows for detected part refs + bounding box coordinates.
    detected_refs_by_page: {page_num: list of box dicts with {"token","x","y","w","h","color"}}
    bom_df: DataFrame with columns ["REF", "PART_NUMBER", "DESCRIPTION"]
    Returns: {page_num: DataFrame of linked BOM rows + coordinates}
    """
    linked = {}
    for page_num, boxes in detected_refs_by_page.items():
        page_rows = []
        for box in boxes:
            ref_upper = str(box["token"]).upper()
            match = bom_df[bom_df["REF"].astype(str).str.upper() == ref_upper]
            if not match.empty:
                row = match.iloc[0][["REF", "PART_NUMBER", "DESCRIPTION"]].to_dict()
                row.update({
                    "X": box["x"],
                    "Y": box["y"],
                    "W": box["w"],
                    "H": box["h"],
                    "Color": box.get("color", "")
                })
                page_rows.append(row)
        linked[page_num] = pd.DataFrame(page_rows)
    return linked


def find_anomalies(
    detected_refs_by_page: Dict[int, Set[str]],
    bom_df: pd.DataFrame
) -> pd.DataFrame:
    """
    Returns a DataFrame of anomalies:
    - Not in Diagram: BOM refs not found in any diagram
    - Not in BOM: Diagram refs not found in BOM
    """
    bom_refs = set(bom_df["REF"].astype(str).str.upper())
    all_detected = set()
    for refs in detected_refs_by_page.values():
        all_detected.update(str(r).upper() for r in refs)

    # Not in Diagram
    not_in_diagram = bom_refs - all_detected
    not_in_diagram_rows = []
    for ref in not_in_diagram:
        match = bom_df[bom_df["REF"].astype(str).str.upper() == ref]
        if not match.empty:
            row = match.iloc[0]
            not_in_diagram_rows.append({
                "Type": "Not in Diagram",
                "REF": row["REF"],
                "PART_NUMBER": row["PART_NUMBER"],
                "DESCRIPTION": row["DESCRIPTION"]
            })

    # Not in BOM
    not_in_bom = all_detected - bom_refs
    not_in_bom_rows = []
    for ref in not_in_bom:
        not_in_bom_rows.append({
            "Type": "Not in BOM",
            "REF": ref,
            "PART_NUMBER": "",
            "DESCRIPTION": ""
        })

    return pd.DataFrame(not_in_diagram_rows + not_in_bom_rows)
