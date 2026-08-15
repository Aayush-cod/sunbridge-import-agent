from src.graph import build_graph


def main():
    print("SunBridge Trading — Bangladesh Import Compliance Agent")
    print("=" * 55)

    app = build_graph()
    final_state = app.invoke({})

    print("\nDone. Outputs generated:")
    print("  Structured data (JSON):", final_state["structured_json_path"])
    print("  Human-readable report:", final_state["report_path"])


if __name__ == "__main__":
    main()