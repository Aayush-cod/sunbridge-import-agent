import os
import json
from pdf2image import convert_from_path
from google.genai import types

from src.gemini_client import client


def pdf_to_images(pdf_path: str, output_dir: str = "data/raw/pages") -> list[str]:
    """
    Converts each page of a PDF into a PNG image.
    Returns a list of file paths, one per page.
    """
    os.makedirs(output_dir, exist_ok=True)

    pages = convert_from_path(pdf_path, dpi=200)

    image_paths = []
    for i, page in enumerate(pages):
        image_path = os.path.join(output_dir, f"page_{i+1}.png")
        page.save(image_path, "PNG")
        image_paths.append(image_path)
        print(f"[extract] Saved {image_path}")

    return image_paths


def build_extraction_prompt(target_model: str) -> str:
    return f"""You are reading a manufacturer's technical datasheet table for a solar inverter.

Look at the "Technical Data" table in this image. Find the column whose header matches
or closely matches this model: "{target_model}".

Return a JSON array. Each item must have exactly these keys:
- "field_name": a short snake_case name for the row (e.g. "rated_output_power_kw")
- "value": the value for that model's column, as a string, including units if shown
- "row_label": the exact row label text as it appears in the table (e.g. "Rated Output Power (kW)")

Rules:
- Only include rows that are visible in the image.
- If a value is shared across all models (one merged cell spanning the whole row), still report it.
- If you cannot read a value clearly, set "value" to "UNCLEAR" and still include the row.
- If NO column in this table matches "{target_model}" (different product line, different
  manufacturer, or model not present at all), return exactly this JSON array and nothing else:
  [{{"field_name": "model_not_found", "value": "NO_MATCHING_COLUMN", "row_label": "N/A"}}]
- Do not invent values. Do not guess a "close enough" column if the model genuinely isn't there.
- Return ONLY the JSON array, no other text, no markdown fences.
"""


def extract_table_from_image(image_path: str, target_model: str) -> list[dict]:
    """
    Sends a page image to Gemini vision and asks it to extract the target model's
    table values as structured JSON. Returns a "model_not_found" marker if the
    model isn't present in this datasheet at all.
    """
    with open(image_path, "rb") as f:
        image_bytes = f.read()

    prompt = build_extraction_prompt(target_model)

    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
            prompt,
        ],
    )

    raw_text = response.text.strip()

    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        raw_text = raw_text.replace("json\n", "", 1)

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        print("[extract] WARNING: could not parse Gemini response as JSON. Raw response:")
        print(raw_text)
        return []


if __name__ == "__main__":
    # Quick manual test — target model normally comes from buyer_form.json via graph.py,
    # hardcoded here only for standalone testing of this file.
    facts = extract_table_from_image("data/raw/pages/page_2.png", target_model="SUN-5K-G06P3-EU-AM2-P1")
    print(f"[extract] Got {len(facts)} fields.")

    os.makedirs("data/raw", exist_ok=True)
    with open("data/raw/datasheet_extracted_test.json", "w") as f:
        json.dump(facts, f, indent=2)
    print("[extract] Saved full output to data/raw/datasheet_extracted_test.json")

    unclear = [f for f in facts if f.get("value") == "UNCLEAR"]
    print(f"[extract] {len(unclear)} field(s) marked UNCLEAR:")
    for f in unclear:
        print("  -", f)

    for keyword in ["weight", "rated_output_power"]:
        matches = [f for f in facts if keyword in f["field_name"]]
        for m in matches:
            print(f"[extract] Check — {m['field_name']}: {m['value']}")