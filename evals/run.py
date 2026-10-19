"""Run the ingestion pipeline over the dataset with several model setups and score each one.

    backend/.venv/Scripts/python -m evals.run                         # both strategies + single-model baselines
    backend/.venv/Scripts/python -m evals.run --models anthropic/claude-haiku-5.5 openai/gpt-6-luna
    backend/.venv/Scripts/python -m evals.run --provider fake         # offline: tests the harness only

Writes evals/results/<provider>-latest.{json,md}. Each setup is one full ingestion of all documents:
"cheap-first" is the default routing, "cautious" puts strong models on the hard inputs (both in
app/ingestion/routing.py); "single:<model>" uses one model for every task, escalation included.
"""

import argparse
import asyncio
import json
import sys
import tempfile
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))  # evals live next to backend/, import its `app` package

from app.config import settings  # noqa: E402
from app.ingestion.routing import Routing, cautious_routing, default_routing  # noqa: E402
from app.ingestion.runner import build_llm, run_ingestion  # noqa: E402
from evals.score import CATEGORY_TASK, Check, accuracy, score_listing  # noqa: E402

DATASET = ROOT / "dataset" / "listings"
RESULTS = Path(__file__).parent / "results"
CANDIDATES = (
    "anthropic/claude-haiku-5.5", "openai/gpt-6-luna", "google/gemini-3.8-flash",
    "anthropic/claude-sonnet-5.5", "openai/gpt-6.1-sol", "google/gemini-4-argon",
)


async def evaluate(name: str, routing: Routing, provider: str | None) -> dict:
    llm = build_llm(settings, provider)
    paths = sorted(p for p in DATASET.rglob("*") if p.suffix in {".pdf", ".png", ".jpg"})
    truths = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(DATASET.glob("*/ground_truth.json"))]

    started = time.perf_counter()
    with tempfile.TemporaryDirectory() as work:
        try:
            state = await run_ingestion(paths, llm=llm, routing=routing, work_dir=Path(work), data_dir=Path(work))
        finally:
            await llm.aclose()
    wall_s = time.perf_counter() - started

    records = {listing.title.lower(): listing.model_dump(mode="json") for listing in state.get("listings", [])}
    checks: list[Check] = []
    for truth in truths:
        checks += score_listing(truth, records.get(truth["fields"]["title"].lower()))

    calls = state.get("model_calls", [])
    by_category = defaultdict(list)
    for check in checks:
        by_category[check.category].append(check)
    return {
        "setup": name,
        "routing": routing.as_dict(),
        "accuracy": round(accuracy(checks), 4),
        "by_category": {category: round(accuracy(items), 4) for category, items in sorted(by_category.items())},
        "cost_usd": round(sum(c["cost_usd"] or 0 for c in calls), 6),
        "calls": len(calls),
        "escalations": sum(c["escalated"] for c in calls),
        "wall_s": round(wall_s, 1),
        "failures": [f"{c.listing} {c.name}: expected {c.expected!r}, got {c.actual!r}" for c in checks if not c.ok],
    }


def recommend(results: list[dict]) -> dict[str, str]:
    """Per routing task: the cheapest single-model setup with the best accuracy on that task's categories."""
    singles = [r for r in results if r["setup"].startswith("single:")]
    recommendation = {}
    for task in sorted(set(CATEGORY_TASK.values())):
        categories = [c for c, t in CATEGORY_TASK.items() if t == task]

        def task_accuracy(result):
            scores = [result["by_category"][c] for c in categories if c in result["by_category"]]
            return sum(scores) / len(scores) if scores else 0.0

        if singles:
            best = max(singles, key=lambda r: (round(task_accuracy(r), 3), -r["cost_usd"]))
            recommendation[task] = best["setup"].removeprefix("single:")
    return recommendation


def to_markdown(results: list[dict], provider: str, recommendation: dict[str, str]) -> str:
    categories = sorted({c for r in results for c in r["by_category"]})
    lines = [
        f"# Eval results ({provider})",
        "",
        "> Offline mode: canned answers. These numbers test the harness, NOT model quality."
        if provider == "fake" else f"> {len(results)} setups × full dataset. Accuracy = share of facts correct.",
        "",
        "| Setup | Accuracy | " + " | ".join(categories) + " | Cost (USD) | Calls | Escalations | Time (s) |",
        "|---|---|" + "---|" * len(categories) + "---|---|---|---|",
    ]
    for r in sorted(results, key=lambda r: (-r["accuracy"], r["cost_usd"])):
        cells = [f"{r['by_category'].get(c, 0):.0%}" for c in categories]
        lines.append(
            f"| `{r['setup']}` | **{r['accuracy']:.0%}** | " + " | ".join(cells)
            + f" | {r['cost_usd']:.4f} | {r['calls']} | {r['escalations']} | {r['wall_s']} |"
        )
    if recommendation:
        lines += ["", "## Suggested routing (best accuracy per task, cheapest on ties)", ""]
        lines += [f"- `{task}` → `{model}`" for task, model in recommendation.items()]
    lines += ["", "## Failures", ""]
    for r in results:
        lines += [f"**{r['setup']}**", ""] + [f"- {f}" for f in r["failures"]] + ([""] if r["failures"] else ["- none", ""])
    return "\n".join(lines) + "\n"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--provider", choices=["openrouter", "openai", "fake"], help="override LLM_PROVIDER")
    parser.add_argument("--models", nargs="*", help="single-model baselines to run (default: every candidate the provider can reach)")
    args = parser.parse_args()

    provider = args.provider or settings.resolved_llm_provider
    if args.models is None:  # OpenAI direct can only reach openai/* models
        args.models = [m for m in CANDIDATES if provider != "openai" or m.startswith("openai/")]
    setups = [("cheap-first (default)", default_routing(provider)), ("cautious", cautious_routing(provider))]
    setups += [(f"single:{m}", Routing.single_model(m)) for m in args.models]

    results = []
    for name, routing in setups:
        print(f"→ {name} …", flush=True)
        result = asyncio.run(evaluate(name, routing, provider))
        print(f"  accuracy {result['accuracy']:.0%} · ${result['cost_usd']:.4f} · {result['calls']} calls")
        results.append(result)

    recommendation = recommend(results)
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / f"{provider}-latest.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    (RESULTS / f"{provider}-latest.md").write_text(to_markdown(results, provider, recommendation), encoding="utf-8")
    print(f"\nWrote {RESULTS / f'{provider}-latest.md'}")


if __name__ == "__main__":
    main()
