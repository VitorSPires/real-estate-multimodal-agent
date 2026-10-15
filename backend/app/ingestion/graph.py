"""Wiring only: which node runs after which. The nodes themselves live in nodes.py.

    classify ─┬─ parse_pdf ─────┬─┬─ extract_text ───────────────────┐
              └─ prepare_image ─┘ └─ triage_images ── extract_visual ─┴─ verify ─┬─ merge ── persist
                                                                        ▲        │
                                                                        └ escalate (once per reading)
"""

from langgraph.graph import END, START, StateGraph

from app.ingestion import nodes
from app.ingestion.nodes import IngestionContext, IngestionState


def build_graph():
    graph = StateGraph(IngestionState, context_schema=IngestionContext)

    graph.add_node("classify", nodes.classify)
    graph.add_node("parse_pdf", nodes.parse_pdf)
    graph.add_node("prepare_image", nodes.prepare_image)
    graph.add_node("extract_text", nodes.extract_text)
    graph.add_node("triage_images", nodes.triage_images)
    graph.add_node("extract_visual", nodes.extract_visual)
    graph.add_node("verify", nodes.verify_readings)
    graph.add_node("escalate", nodes.escalate)
    graph.add_node("merge", nodes.merge_listings)
    graph.add_node("persist", nodes.persist)

    graph.add_edge(START, "classify")
    # PDFs and images are prepared in parallel...
    graph.add_edge("classify", "parse_pdf")
    graph.add_edge("classify", "prepare_image")
    # ...and both must finish before any model reads a region (a list = wait for all).
    graph.add_edge(["parse_pdf", "prepare_image"], "extract_text")
    graph.add_edge(["parse_pdf", "prepare_image"], "triage_images")
    graph.add_edge("triage_images", "extract_visual")
    graph.add_edge(["extract_text", "extract_visual"], "verify")
    graph.add_conditional_edges("verify", nodes.needs_escalation, {"escalate": "escalate", "merge": "merge"})
    graph.add_edge("escalate", "verify")
    graph.add_edge("merge", "persist")
    graph.add_edge("persist", END)

    return graph.compile()


ingestion_graph = build_graph()
