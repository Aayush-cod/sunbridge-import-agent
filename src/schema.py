from pydantic import BaseModel, Field
from typing import Optional, Literal


class SourceRef(BaseModel):
    """Where a single value came from."""
    document: Literal["datasheet", "buyer_form", "call_notes"]
    detail: Optional[str] = None  # e.g. "page 1, Output Side table" or "line: 'Model SUN-5K-G06P3...'"


class Fact(BaseModel):
    """One extracted piece of information, tagged with its origin and how sure we are."""
    field_name: str                # e.g. "rated_output_power_kw"
    value: str                     # keep as string for simplicity; format later if needed
    source: SourceRef
    confidence: Literal["confirmed_written", "verbal_unconfirmed", "inferred", "missing"]
    notes: Optional[str] = None    # e.g. "installer guessed this over the phone"


class FieldComparison(BaseModel):
    """All facts collected for one field across sources, plus whether they agree."""
    field_name: str
    facts: list[Fact]
    status: Literal["agreement", "conflict", "naming_variant", "single_source", "missing"]
    resolution_note: Optional[str] = None  # e.g. "written datasheet value used as authoritative"