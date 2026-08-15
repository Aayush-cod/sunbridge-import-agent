from typing import TypedDict
from langgraph.graph import StateGraph, END

from src.fetch import fetch_pdf
from src.extract import pdf_to_images, extract_table_from_image
from src.reconcile import reconcile_all
from src.generate import save_structured_json, generate_report

import json
import os


DEFAULT_DATASHEET_URL = "https://www.deyeinverter.com/deyeinverter/2023/10/07/datasheet_sun-4-12k-g06p3-eu-am2-p1_231007_en.pdf"


class PipelineState(TypedDict, total=False):
    datasheet_url: str
    pdf_path: str
    image_paths: list[str]
    datasheet_facts: list[dict]
    extracted_json_path: str
    comparisons: list
    structured_json_path: str
    report_path: str


def node_fetch(state: PipelineState) -> PipelineState:
    print("[graph] Stage 1: fetch")
    url = state.get("datasheet_url") or DEFAULT_DATASHEET_URL
    path = fetch_pdf(url)
    return {"pdf_path": path}


def node_extract(state: PipelineState) -> PipelineState:
    print("[graph] Stage 2: extract")

    with open("data/sources/buyer_form.json") as f:
        buyer_form = json.load(f)
    target_model = buyer_form["item"]  # dynamically read, not hardcoded

    pdf_filename = os.path.basename(state["pdf_path"])
    cache_path = f"data/raw/{pdf_filename}_extracted.json"

    images = pdf_to_images(state["pdf_path"], output_dir=f"data/raw/pages/{pdf_filename}")

    if os.path.exists(cache_path):
        print(f"[extract] Using cached extraction for {pdf_filename} — skipping Gemini call")
        with open(cache_path) as f:
            facts = json.load(f)
    else:
        table_page = images[1] if len(images) > 1 else images[0]
        facts = extract_table_from_image(table_page, target_model=target_model)
        os.makedirs("data/raw", exist_ok=True)
        with open(cache_path, "w") as f:
            json.dump(facts, f, indent=2)

    return {"image_paths": images, "datasheet_facts": facts, "extracted_json_path": cache_path}


def node_tag_and_reconcile(state: PipelineState) -> PipelineState:
    print("[graph] Stage 3+4: tag + reconcile")
    comparisons = reconcile_all(state["extracted_json_path"])
    return {"comparisons": comparisons}


def node_generate(state: PipelineState) -> PipelineState:
    print("[graph] Stage 5: generate outputs")
    save_structured_json(state["comparisons"])
    generate_report(state["comparisons"])
    return {
        "structured_json_path": "outputs/structured_data.json",
        "report_path": "outputs/sunbridge_draft_report.md",
    }


def build_graph():
    graph = StateGraph(PipelineState)

    graph.add_node("fetch", node_fetch)
    graph.add_node("extract", node_extract)
    graph.add_node("tag_and_reconcile", node_tag_and_reconcile)
    graph.add_node("generate", node_generate)

    graph.set_entry_point("fetch")
    graph.add_edge("fetch", "extract")
    graph.add_edge("extract", "tag_and_reconcile")
    graph.add_edge("tag_and_reconcile", "generate")
    graph.add_edge("generate", END)

    return graph.compile()


if __name__ == "__main__":
    app = build_graph()
    final_state = app.invoke({})
    print("\n[graph] Pipeline complete.")
    print("  Structured data:", final_state["structured_json_path"])
    print("  Report:", final_state["report_path"])