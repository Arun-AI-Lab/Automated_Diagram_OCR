import os
import base64
import requests
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("VISION_API_KEY")
ENDPOINT_URL = f"https://vision.googleapis.com/v1/images:annotate?key={API_KEY}"

def detect_text_with_boxes(image_path: str):
    """
    Returns (full_text, words)
    words = list of dicts: {'text': str, 'x': float, 'y': float, 'w': int, 'h': int}
    """
    with open(image_path, "rb") as f:
        content = base64.b64encode(f.read()).decode("utf-8")

    body = {
        "requests": [{
            "image": {"content": content},
            "features": [{"type": "DOCUMENT_TEXT_DETECTION"}],
        }]
    }

    resp = requests.post(ENDPOINT_URL, json=body)
    data = resp.json()

    try:
        r = data["responses"][0]
    except (KeyError, IndexError):
        return "NO TEXT FOUND", []

    full_text = r.get("fullTextAnnotation", {}).get("text", "") or "NO TEXT FOUND"

    words = []
    ann = r.get("textAnnotations", [])
    for item in ann[1:]:
        txt = item.get("description", "")
        poly = item.get("boundingPoly", {}).get("vertices", [])
        if len(poly) >= 4:
            xs = [v.get("x", 0) for v in poly]
            ys = [v.get("y", 0) for v in poly]
            x_min, x_max = min(xs), max(xs)
            y_min, y_max = min(ys), max(ys)

            words.append({
                "text": txt.strip(),
                "x": (x_min + x_max) / 2,
                "y": (y_min + y_max) / 2,
                "w": x_max - x_min,
                "h": y_max - y_min
            })

    return full_text, words