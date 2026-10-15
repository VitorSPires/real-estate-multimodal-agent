# Synthetic dataset

Four fictional apartments, each with the documents a broker would send. Everything is generated
from [`spec.py`](spec.py), so the ground truth is known exactly and can't drift from the documents.

```bash
backend/.venv/Scripts/python -m dataset.generate     # writes dataset/listings/
backend/.venv/Scripts/python -m pytest dataset       # spec + rendering checks
```

(Use `backend/.venv/bin/python` on macOS / Linux.)

## Listings

| Slug | Listing | Beds | Area | Price (USD) | Documents |
|---|---|---|---|---|---|
| `listing-a` | Maple Court 302 · Riverside | 2 | 68 m² | 412,000 | brochure, floor plan |
| `listing-b` | Harbor View 1104 · Old Port | 2 (+ office) | 84 m² | 538,000 | brochure (with price chart), floor plan |
| `listing-c` | Linden Park 7 · Green Hills | 3 | 112 m² | 720,000 | brochure, floor plan, phone photo of price sheet |
| `listing-d` | Cedar Lofts 5B · Old Port | 1 | 45 m² | 298,000 | brochure, floor plan |

## Designed traps

| Listing | Trap | What a good pipeline does |
|---|---|---|
| A | The gym is only mentioned in the photo caption | Reads captions, not just the amenities list |
| B | Brochure says 2 bedrooms; the floor plan has 2 bedrooms + a room labeled `OFFICE` | Keeps 2, records a conflict with 3 |
| B | Gourmet balcony and BBQ grill only appear as floor-plan labels | Finds amenities in images |
| B | Neighborhood price trend is an unlabeled line chart | Reads values off the plot (±3% tolerance) |
| C | Condo fee and property tax only appear in a tilted, blurry phone photo (no text layer) | Routes the image to a vision model |
| D | Brochure states USD 5,900/m², but price ÷ area = 6,622 | Recomputes and flags the inconsistency |

Floor plans use real-estate shorthand (`MBR`, `BR`, `WC`, `KIT`, `LDY`) so reading them takes
interpretation, not just OCR.

**Demo query:** "at least two bedrooms" + "BBQ grill" → exactly one answer, `listing-b`
(enforced by a test).

## Files per listing

Named like files a broker would send (unique across listings, so all can be uploaded at once):

- `<title>-brochure.pdf` — 2 pages, native text layer, embedded photo (+ chart for B)
- `<title>-floorplan.png` — architectural-style plan
- `<title>-price-sheet.jpg` — only for C (`linden-park-7-price-sheet.jpg`)
- `ground_truth.json` — expected `fields`, where hard facts live (`sources`),
  `expected_conflicts`, and `tolerances`

Generation is deterministic: rerunning produces byte-identical files.
