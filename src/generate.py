import json
import os
from datetime import date
from src.schema import FieldComparison
from src.reconcile import reconcile_all


def save_structured_json(comparisons: list[FieldComparison], path: str = "outputs/structured_data.json"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = [c.model_dump() for c in comparisons]
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"[generate] Saved structured data to {path}")


def format_field_line(c: FieldComparison) -> str:
    if c.status == "single_source":
        f = c.facts[0]
        tag = "Confirmed (written)" if f.confidence == "confirmed_written" else "Unverified (verbal)"
        return f"**{humanize(c.field_name)}:** {f.value}  \n*{tag} — source: {f.source.document}*"

    if c.status == "agreement":
        vals = "; ".join(f"{f.value} ({f.source.document})" for f in c.facts)
        return f"**{humanize(c.field_name)}:** {c.facts[0].value}  \n*Confirmed — consistent across sources: {vals}*"

    if c.status == "naming_variant":
        vals = " / ".join(f"\"{f.value}\" ({f.source.document})" for f in c.facts)
        return f"**{humanize(c.field_name)}:** {vals}  \n*Same entity, differing level of detail — not a factual conflict.*"

    if c.status == "conflict":
        lines = [f"**{humanize(c.field_name)}** — sources disagree, needs factory confirmation:"]
        for f in c.facts:
            conf_label = "written" if f.confidence == "confirmed_written" else "verbal, unconfirmed"
            lines.append(f"  - {f.value} ({f.source.document}, {conf_label})")
        return "\n".join(lines)

    if c.status == "missing":
        return f"**{humanize(c.field_name)}:** Not available in any source yet."

    return f"**{humanize(c.field_name)}:** {c.status}"


def humanize(field_name: str) -> str:
    """Turns 'max_dc_input_voltage_v' into 'Max Dc Input Voltage V' for readable headers."""
    return field_name.replace("_", " ").title()


def form_destination(comparisons: list) -> str:
    dest = next((c for c in comparisons if c.field_name == "destination_country"), None)
    return dest.facts[0].value if dest else "Not specified"


def generate_report(comparisons: list[FieldComparison], path: str = "outputs/sunbridge_draft_report.md"):
    os.makedirs(os.path.dirname(path), exist_ok=True)

    by_status = {}
    for c in comparisons:
        by_status.setdefault(c.status, []).append(c)

    conflicts = by_status.get("conflict", [])
    missing = by_status.get("missing", [])
    verbal_only = [
        c for c in by_status.get("single_source", [])
        if c.facts[0].confidence == "verbal_unconfirmed"
    ]
    pending = missing + verbal_only

    datasheet_matched = any(
        f.source.document == "datasheet"
        for c in comparisons
        for f in c.facts
    )

    model_comparison = next((c for c in comparisons if c.field_name == "model"), None)
    model_value = model_comparison.facts[0].value if model_comparison else "Not identified"

    lines = []
    lines.append("# SunBridge Trading — Import Compliance Summary")
    lines.append("")
    lines.append("| | |")
    lines.append("|---|---|")
    lines.append(f"| **Product** | {model_value} |")
    lines.append(f"| **Destination** | {form_destination(comparisons)} |")
    lines.append(f"| **Date generated** | {date.today().isoformat()} |")
    lines.append("| **Sources** | Manufacturer datasheet, buyer order form, call notes (Ramesh, 2024-10-03) |")
    lines.append("")

    if not datasheet_matched:
        lines.append(
            "> **Note:** The supplied datasheet did not contain a column matching the ordered model. "
            "The specifications below reflect only the buyer form and call notes; the manufacturer "
            "datasheet fields are unavailable for this run and should be re-requested."
        )
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 1. Items Requiring Factory Confirmation")
    lines.append("")
    if conflicts:
        lines.append("The following fields have conflicting values across sources and should be resolved before shipping paperwork is finalized.")
        lines.append("")
        for c in conflicts:
            lines.append(format_field_line(c))
            lines.append("")
    else:
        lines.append("No direct conflicts were found between sources.")
        lines.append("")

    lines.append("## 2. Pending From Manufacturer")
    lines.append("")
    if pending:
        lines.append("The following are not yet confirmed in writing by the factory and should be treated as outstanding.")
        lines.append("")
        for c in pending:
            lines.append(format_field_line(c))
            lines.append("")
    else:
        lines.append("No items are currently marked as pending.")
        lines.append("")

    lines.append("## 3. Product Identity and Specifications")
    lines.append("")
    other_fields = sorted(
        by_status.get("single_source", []) if False else [
            c for c in by_status.get("single_source", []) if c.facts[0].confidence != "verbal_unconfirmed"
        ] + by_status.get("agreement", []) + by_status.get("naming_variant", []),
        key=lambda c: c.field_name,
    )
    for c in other_fields:
        lines.append(format_field_line(c))
        lines.append("")

    lines.append("## 4. Questions for the Factory")
    lines.append("")

    questions = []
    for c in conflicts:
        vals = "; ".join(f"{f.value} ({f.source.document})" for f in c.facts)
        questions.append(f"Please confirm the correct {humanize(c.field_name).lower()} — sources disagree: {vals}.")

    for c in pending:
        questions.append(
            f"Please provide written confirmation of {humanize(c.field_name).lower()} — "
            f"currently only {c.facts[0].confidence.replace('_', ' ')} ({c.facts[0].source.document})."
        )

    if not datasheet_matched:
        questions.append(
            "The supplied datasheet did not match the ordered model — please resend the correct "
            "datasheet, or confirm the exact model/variant so it can be re-processed."
        )

    if questions:
        for q in questions:
            lines.append(f"- {q}")
    else:
        lines.append("No outstanding questions — all fields are confirmed and consistent across sources.")

    with open(path, "w") as f:
        f.write("\n".join(lines))
    print(f"[generate] Saved human-readable report to {path}")

if __name__ == "__main__":
    comparisons = reconcile_all()
    save_structured_json(comparisons)
    generate_report(comparisons)