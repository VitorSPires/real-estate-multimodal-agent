"""Run the ingestion pipeline from the terminal.

    python -m app.ingestion ../dataset/listings              # every PDF/image under the folder
    python -m app.ingestion a.pdf b.png --provider fake      # offline, canned answers
    python -m app.ingestion ../dataset/listings --json out.json
"""

import argparse
import asyncio
import json
import sys
import tempfile
from pathlib import Path

from openai import AuthenticationError

from app.config import settings
from app.ingestion.documents import IMAGE_SUFFIXES, PDF_SUFFIXES
from app.ingestion.runner import build_llm, run_ingestion

LEVEL_MARK = {"info": " ", "warn": "!", "success": "✓"}


def find_documents(inputs: list[Path]) -> list[Path]:
    suffixes = PDF_SUFFIXES | IMAGE_SUFFIXES
    found = []
    for item in inputs:
        found += sorted(p for p in item.rglob("*") if p.suffix.lower() in suffixes) if item.is_dir() else [item]
    return found


def print_event(event: dict) -> None:
    if event["type"] == "narration":
        print(f"{LEVEL_MARK.get(event['level'], ' ')} {event['text']}")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # narration uses → and ⚠; Windows consoles default to cp1252
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("inputs", nargs="+", type=Path, help="files or folders")
    parser.add_argument("--provider", choices=["openrouter", "openai", "fake"], help="override LLM_PROVIDER")
    parser.add_argument("--json", type=Path, help="write the merged listings to this file")
    args = parser.parse_args()

    paths = find_documents(args.inputs)
    with tempfile.TemporaryDirectory() as work:
        try:
            state = asyncio.run(run_ingestion(
                paths, llm=build_llm(settings, args.provider), work_dir=Path(work), data_dir=Path(work),
                on_event=print_event,
            ))
        except AuthenticationError:
            sys.exit("The model provider rejected the API key. Check backend/.env.")

    if args.json:
        listings = [listing.model_dump(mode="json") for listing in state.get("listings", [])]
        args.json.write_text(json.dumps(listings, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nWrote {len(listings)} listing(s) to {args.json}")


if __name__ == "__main__":
    main()
