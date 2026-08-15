import re
from collections import defaultdict
from src.schema import Fact, FieldComparison
from src.tag import build_all_facts


def normalize_for_comparison(value: str) -> str:
    """
    Normalizes a value for comparison: converts common power units to a
    shared base (watts), strips whitespace/casing, so '5 kW' and '5000 W'
    are recognized as equal instead of falsely flagging as conflicts.
    """
    v = value.lower().strip()

    # Try to catch "<number> kw" or "<number> w" or "<number>" patterns
    match = re.match(r"^([\d.]+)\s*(kw|w)?$", v)
    if match:
        number = float(match.group(1))
        unit = match.group(2)
        if unit == "kw":
            number *= 1000
        # unit == "w" or no unit -> assume already base value in kW context, so also *1000 if bare "5"
        elif unit is None:
            number *= 1000
        return str(number)

    # fallback: just strip common unit words/casing (weight, etc.)
    v = v.replace("kg", "").replace("kw", "").replace("w", "").strip()
    return v


def is_naming_variant(value_a: str, value_b: str) -> bool:
    """
    Detects when one value is a shortened/substring form of the other
    (e.g. model numbers, company names) rather than a genuine factual conflict.
    """
    a = value_a.lower().strip()
    b = value_b.lower().strip()
    a_clean = re.split(r"[,(]", a)[0].strip()  # cut off at first comma/paren
    b_clean = re.split(r"[,(]", b)[0].strip()
    return a_clean in b_clean or b_clean in a_clean


def group_facts_by_field(facts: list[Fact]) -> dict[str, list[Fact]]:
    grouped = defaultdict(list)
    for f in facts:
        grouped[f.field_name].append(f)
    return grouped


def compare_field(field_name: str, facts: list[Fact]) -> FieldComparison:
    if len(facts) == 1:
        status = "missing" if facts[0].confidence == "missing" else "single_source"
        return FieldComparison(field_name=field_name, facts=facts, status=status)

    normalized_values = {normalize_for_comparison(f.value) for f in facts}

    if len(normalized_values) == 1:
        return FieldComparison(
            field_name=field_name,
            facts=facts,
            status="agreement",
            resolution_note="All sources agree (after normalizing units/formatting).",
        )

    # Not an exact match after normalization — check if it's just a naming variant
    if len(facts) == 2 and is_naming_variant(facts[0].value, facts[1].value):
        return FieldComparison(
            field_name=field_name,
            facts=facts,
            status="naming_variant",
            resolution_note="Same underlying entity, different level of detail/shorthand — not a factual conflict.",
        )

    return FieldComparison(
        field_name=field_name,
        facts=facts,
        status="conflict",
        resolution_note="Sources disagree — see individual values and confidence levels.",
    )


def reconcile_all(datasheet_json_path: str = "data/raw/datasheet_extracted.json") -> list[FieldComparison]:
    facts = build_all_facts(datasheet_json_path)
    grouped = group_facts_by_field(facts)
    return [compare_field(name, flist) for name, flist in grouped.items()]


if __name__ == "__main__":
    comparisons = reconcile_all()

    by_status = defaultdict(list)
    for c in comparisons:
        by_status[c.status].append(c)

    print(f"[reconcile] {len(comparisons)} unique fields total")
    for status in ["agreement", "naming_variant", "conflict", "single_source", "missing"]:
        print(f"  {status:15}: {len(by_status[status])}")

    for status in ["conflict", "naming_variant"]:
        print(f"\n--- {status.upper()} ---")
        for c in by_status[status]:
            print(f"\n{c.field_name}:")
            for f in c.facts:
                print(f"  - {f.value!r} (from {f.source.document}, {f.confidence})")