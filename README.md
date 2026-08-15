# SunBridge Trading — Import Compliance Agent

An AI agent that fetches a manufacturer datasheet from a live URL, reconciles it against
a buyer order form and call notes, and produces a source-attributed compliance draft for
SunBridge Trading's import agent — showing what's confirmed, what conflicts across
sources, and what's still pending from the factory.

Built for the Cantordust AI Engineer assessment — **Task 2 (China → Bangladesh)**.

---

## Quick start

```bash
git clone <your-repo-url>
cd sunbridge-import-agent

brew install poppler                 # macOS — required for PDF-to-image conversion
# apt-get install poppler-utils      # Linux equivalent

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file in the project root with a free Gemini key
(get one at https://aistudio.google.com/apikey):

```
GEMINI_API_KEY=your_key_here
```

Run it:

```bash
python main.py                       # command line, one-shot run
python -m streamlit run app.py       # interactive UI (recommended)
```

The UI lets you paste any datasheet PDF URL, watch the pipeline run stage by stage,
and view the report, conflicts, and raw JSON in-browser. Both entry points write the
same two files to `outputs/`:

| File | Contents |
|---|---|
| `structured_data.json` | Machine-readable facts, tagged by source and confidence |
| `sunbridge_draft_report.md` | The human-readable draft for the import agent |

---

## Why vision, not text extraction

The datasheet's "Technical Data" table has merged cells and multiple models sharing a
row, which tends to jumble column alignment under plain text extraction. Instead, each
PDF page is rendered to an image (`pdf2image` + poppler) and read by Gemini's vision
model (`gemini-3.6-flash`) — the same way a person would actually read the table.

The target model **is not hardcoded**. It's read at runtime from `buyer_form.json`'s
`item` field and inserted into the extraction prompt, so the pipeline looks for whatever
model the order actually specifies. If a datasheet has no matching column at all — tested
against an unrelated Growatt inverter datasheet — Gemini returns an explicit
`model_not_found` marker instead of guessing, and the final report surfaces this as a
clear warning rather than silently showing wrong data. Any single value it can't read
clearly is marked `UNCLEAR` rather than guessed.

---

## Pipeline structure

A 5-stage LangGraph agent (`src/graph.py`), built from independently testable functions:

| Stage | File | What it does |
|---|---|---|
| 1. Fetch | `fetch.py` | Downloads the datasheet PDF from a live URL; cached by filename |
| 2. Extract | `extract.py` | Converts PDF pages to images, reads the target model's column via Gemini vision; cached per PDF |
| 3. Tag | `tag.py` | Wraps every fact into a common shape (`schema.py`) with source + confidence: `confirmed_written` (datasheet, buyer form) or `verbal_unconfirmed` (call notes) |
| 4. Reconcile | `reconcile.py` | Groups facts by field, classifies each as `agreement`, `conflict`, `naming_variant`, `single_source`, or `missing`; normalizes units so equivalent values (e.g. 5000 W vs 5 kW) don't false-flag as conflicts |
| 5. Generate | `generate.py` | Writes the structured JSON and the Markdown report — header, conflicts, pending items, and factory questions are all generated dynamically from the reconciliation results, not fixed text |

Each stage runs and was tested standalone (`python -m src.<stage>`) before being wired
into the graph — this made two real bugs (a PDF-fetch 403 from missing browser headers,
and a deprecated Gemini model name) easy to isolate.

`app.py` (Streamlit) is a thin UI layer over the same `build_graph()` pipeline — no
logic is duplicated. It exists to make the pipeline easy to demo against datasheets
beyond the one in the brief.

---

## Assumptions

- The target model comes from `data/sources/buyer_form.json`, treated as a fixed input
  per the brief — not fetched or editable through the UI.
- If a fetched PDF has multiple pages, page 2 is assumed to hold the Technical Data
  table. Not auto-detected.
- The buyer form and call notes are hardcoded JSON in `data/sources/`, since the brief
  supplied them as text rather than external links.
- "Confirmed" means *written by some party* (datasheet or buyer form), not
  manufacturer-certified — verbal claims (e.g. SGS test evidence) stay marked unverified
  until the factory provides them in writing.
- Naming differences (shortened model numbers, shorthand company names) are kept
  separate from factual conflicts (weight, efficiency), so real discrepancies aren't
  buried under formatting noise.

## What I'd do with more time

- Auto-detect which PDF page holds the relevant table instead of assuming page 2.
- Add retry/self-correction when Gemini returns malformed JSON, instead of returning an
  empty list.
- Extend unit normalization beyond power (kW/W) to other unit types.
- Add a conditional LangGraph edge that retries extraction with a stricter prompt when
  too many fields come back `UNCLEAR`.
- Let the buyer form and call notes be swapped via the UI too, not just the datasheet.
- Add pytest coverage for `reconcile.py`'s classification logic — the most
  judgment-heavy part of the pipeline.

## Known limitation

Extraction targets exactly one model string from the buyer form. It correctly detects
when that model is absent from a given datasheet (verified against an unrelated Growatt
datasheet, which returned `model_not_found` rather than incorrect data), but it does not
attempt to identify a plausibly-related model if the exact string doesn't match.