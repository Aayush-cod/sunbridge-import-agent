import streamlit as st
import json
import os
from src.graph import build_graph

st.set_page_config(
    page_title="SunBridge Import Compliance Agent",
    page_icon="📋",
    layout="wide",
)

st.title("📋 SunBridge Trading — Import Compliance Agent")
st.caption("AI agent that fetches a datasheet, reconciles it against buyer form & call notes, and drafts a compliance summary.")

st.divider()

DEFAULT_URL = "https://www.deyeinverter.com/deyeinverter/2023/10/07/datasheet_sun-4-12k-g06p3-eu-am2-p1_231007_en.pdf"

datasheet_url = st.text_input(
    "Datasheet PDF URL",
    value=DEFAULT_URL,
    help="Paste any manufacturer datasheet PDF link to re-run the pipeline against a different source.",
)

if "final_state" not in st.session_state:
    st.session_state.final_state = None

col1, col2 = st.columns([1, 3])
with col1:
    run_clicked = st.button("▶ Run Pipeline", type="primary", use_container_width=True)

if run_clicked:
    with st.status("Running agent pipeline...", expanded=True) as status:
        st.write("Stage 1 — Fetching datasheet PDF")
        st.write("Stage 2 — Extracting table via Gemini vision")
        st.write("Stage 3+4 — Tagging sources & reconciling conflicts")
        st.write("Stage 5 — Generating report")

        app = build_graph()
        final_state = app.invoke({"datasheet_url": datasheet_url})
        st.session_state.final_state = final_state

        status.update(label="Pipeline complete ✅", state="complete", expanded=False)

st.divider()

# ---------- RESULTS SECTION ----------
if st.session_state.final_state:
    report_path = st.session_state.final_state["report_path"]
    json_path = st.session_state.final_state["structured_json_path"]

    with open(json_path) as f:
        comparisons = json.load(f)

    conflicts = [c for c in comparisons if c["status"] == "conflict"]
    naming_variants = [c for c in comparisons if c["status"] == "naming_variant"]
    pending = [
        c for c in comparisons
        if c["status"] == "missing"
        or (c["status"] == "single_source" and c["facts"][0]["confidence"] == "verbal_unconfirmed")
    ]

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total fields", len(comparisons))
    m2.metric("🚩 Conflicts", len(conflicts))
    m3.metric("⚠️ Naming variants", len(naming_variants))
    m4.metric("❌ Pending from factory", len(pending))

    st.divider()

    tab1, tab2, tab3 = st.tabs(["📄 Draft Report", "🚩 Conflicts", "🔧 Raw JSON"])

    with tab1:
        with open(report_path) as f:
            st.markdown(f.read())
        st.download_button("Download report (.md)", data=open(report_path).read(), file_name="sunbridge_draft_report.md")

    with tab2:
        if not conflicts:
            st.info("No conflicts detected.")
        for c in conflicts:
            st.markdown(f"#### {c['field_name']}")
            cols = st.columns(len(c["facts"]))
            for col, fact in zip(cols, c["facts"]):
                with col:
                    badge = "🟢 written" if fact["confidence"] == "confirmed_written" else "🟡 verbal"
                    st.markdown(f"**{fact['source']['document']}** · {badge}")
                    st.code(fact["value"], language=None)
            st.divider()

    with tab3:
        st.json(comparisons)
        st.download_button("Download structured data (.json)", data=json.dumps(comparisons, indent=2), file_name="structured_data.json")

else:
    st.info("Click **Run Pipeline** to fetch, extract, and reconcile the compliance data.")