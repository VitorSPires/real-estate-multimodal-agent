# Evals

Measures how well each model setup extracts the dataset's facts, and what it costs. The routing
in `backend/app/ingestion/routing.py` should be justified by these numbers.

```bash
backend/.venv/Scripts/python -m evals.run                    # routed + 6 single-model baselines (needs OPENROUTER_API_KEY)
backend/.venv/Scripts/python -m evals.run --models openai/gpt-6-luna anthropic/claude-haiku-5.5
backend/.venv/Scripts/python -m evals.run --provider fake    # offline: checks the harness, not models
backend/.venv/Scripts/python -m pytest evals                 # scorer tests
```

Results go to `evals/results/<provider>-latest.{md,json}`.

## How scoring works

Each listing's merged record is compared to its `ground_truth.json`, one check per fact. Checks
are grouped by **where the fact had to be read from**:

| Category | What it checks | Routing task |
|---|---|---|
| `brochure_text` | price, area, rooms, floor, neighborhood | `text` |
| `fees` / `fees_from_photo` | condo fee + property tax (brochure text vs. tilted phone photo) | `text` / `document_photo` |
| `amenity_from_text` | amenities in lists, descriptions and photo captions | `text` |
| `amenity_from_floorplan` | amenities only drawn on the floor plan (BBQ, balcony) | `floor_plan` |
| `chart` | the 5-point price trend, ±3% per point | `chart` |
| `conflict` | designed conflicts detected (office vs. bedroom, wrong price/m²) | `floor_plan` |

Each setup is a full ingestion run. `routed` uses the current routing; `single:<model>` uses one
model for every task (including escalation). The report suggests, per task, the model with the best
accuracy on that task's categories (cheapest on ties).

## Limits

- 4 listings, ~25 facts each: enough to spot a weak model on a task, not to rank close models.
- One run per setup; models are run at temperature 0, but results can still vary between runs.
- Triage accuracy isn't scored directly (a wrong triage shows up as missing facts downstream).
