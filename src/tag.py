import json
from src.schema import Fact, SourceRef


def load_json(path: str) -> dict | list:
    with open(path) as f:
        return json.load(f)


def tag_datasheet_facts(datasheet_json_path: str) -> list[Fact]:
    raw_facts = load_json(datasheet_json_path)
    tagged = []

    for item in raw_facts:
        if item["field_name"] == "model_not_found":
            continue  # no real data to tag — the report layer already shows the mismatch warning

        confidence = "missing" if item["value"] == "UNCLEAR" else "confirmed_written"
        tagged.append(
            Fact(
                field_name=item["field_name"],
                value=item["value"],
                source=SourceRef(document="datasheet", detail=item["row_label"]),
                confidence=confidence,
            )
        )
    return tagged

def tag_buyer_form_facts(buyer_form_path: str) -> list[Fact]:
    """
    Wraps buyer form fields into tagged Fact objects.
    These are what SunBridge itself declared on the form — confirmed_written
    (it's a written form), but not manufacturer-verified.
    """
    form = load_json(buyer_form_path)
    tagged = []

    field_map = {
        "item": "model",
        "buyer_stated_power": "rated_output_power",
        "maker": "manufacturer_name",
        "destination": "destination_country",
    }

    for form_key, field_name in field_map.items():
        if form.get(form_key):
            tagged.append(
                Fact(
                    field_name=field_name,
                    value=form[form_key],
                    source=SourceRef(document="buyer_form", detail=f"field: {form_key}"),
                    confidence="confirmed_written",
                )
            )
    return tagged


def tag_call_notes_facts(call_notes_path: str) -> list[Fact]:
    """
    Wraps call notes claims into tagged Fact objects.
    These are all verbal/unconfirmed by definition — nothing here is in writing from the factory.
    """
    notes = load_json(call_notes_path)
    claims = notes.get("claims", {})
    tagged = []

    field_map = {
        "model": "model",
        "power": "rated_output_power",
        "manufacturer": "manufacturer_name",
        "ip_rating": "ingress_protection",
        "weight_kg": "weight_kg",
        "test_evidence_mentioned": "test_evidence",
        "efficiency_mentioned": "max_efficiency",
        "label_photo": "label_photo",
    }

    for claim_key, field_name in field_map.items():
        if claims.get(claim_key):
            tagged.append(
                Fact(
                    field_name=field_name,
                    value=claims[claim_key],
                    source=SourceRef(document="call_notes", detail=f"claim: {claim_key}"),
                    confidence="verbal_unconfirmed",
                    notes=f"From phone call, {notes.get('date', 'undated')}, not in writing.",
                )
            )
    return tagged


def build_all_facts(datasheet_json_path: str = "data/raw/datasheet_extracted.json") -> list[Fact]:
    """Combines facts from all three sources into one flat list."""
    facts = []
    facts += tag_datasheet_facts(datasheet_json_path)
    facts += tag_buyer_form_facts("data/sources/buyer_form.json")
    facts += tag_call_notes_facts("data/sources/call_notes.json")
    return facts


if __name__ == "__main__":
    all_facts = build_all_facts()
    print(f"[tag] Total tagged facts: {len(all_facts)}")

    for f in all_facts:
        print(f"  [{f.confidence:20}] {f.field_name:25} = {f.value!r:40} (from {f.source.document})")