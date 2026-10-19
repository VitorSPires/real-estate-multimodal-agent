# Eval results (openai)

> 3 setups × full dataset. Accuracy = share of facts correct.

| Setup | Accuracy | amenity_from_floorplan | amenity_from_text | brochure_text | chart | conflict | fees | fees_from_photo | Cost (USD) | Calls | Escalations | Time (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `single:openai/gpt-6-luna` | **100%** | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 0.0050 | 20 | 0 | 30.8 |
| `routed` | **100%** | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 0.0375 | 20 | 0 | 20.5 |
| `single:openai/gpt-6.1-sol` | **100%** | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 0.0858 | 20 | 0 | 14.4 |

## Suggested routing (best accuracy per task, cheapest on ties)

- `chart` → `openai/gpt-6-luna`
- `document_photo` → `openai/gpt-6-luna`
- `floor_plan` → `openai/gpt-6-luna`
- `text` → `openai/gpt-6-luna`

## Failures

**routed**

- none

**single:openai/gpt-6-luna**

- none

**single:openai/gpt-6.1-sol**

- none

