# Eval results (openai)

> 4 setups × full dataset. Accuracy = share of facts correct.

| Setup | Accuracy | amenity_from_floorplan | amenity_from_text | brochure_text | chart | conflict | fees | fees_from_photo | Cost (USD) | Calls | Escalations | Time (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `cheap-first (default)` | **100%** | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 0.0049 | 20 | 0 | 14.9 |
| `single:openai/gpt-6-luna` | **100%** | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 0.0050 | 20 | 0 | 14.0 |
| `cautious` | **100%** | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 0.0381 | 20 | 0 | 16.3 |
| `single:openai/gpt-6.1-sol` | **100%** | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 0.0846 | 20 | 0 | 15.8 |

## Suggested routing (best accuracy per task, cheapest on ties)

- `chart` → `openai/gpt-6-luna`
- `document_photo` → `openai/gpt-6-luna`
- `floor_plan` → `openai/gpt-6-luna`
- `text` → `openai/gpt-6-luna`

## Failures

**cheap-first (default)**

- none

**cautious**

- none

**single:openai/gpt-6-luna**

- none

**single:openai/gpt-6.1-sol**

- none

