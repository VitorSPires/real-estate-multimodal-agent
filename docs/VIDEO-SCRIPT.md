# Demo video script (~2 min)

Goal: in two minutes, show that the system **reads hard documents, proves its answers, and talks**.
Record in English. Have the text-only fallback ready (type the same lines) if voice misbehaves.

## Before recording

- [ ] `backend/.env`: valid `OPENROUTER_API_KEY` (or `OPENAI_API_KEY`) and `OPENAI_API_KEY` for
      voice; `LLM_PROVIDER=auto` (the header must **not** show "Offline mode").
- [ ] Run the evals once and put the table in the README (scene 6 shows it).
- [ ] `_run/win.bat`, open http://localhost:5173, browser window ~1440×900, zoom 100%.
- [ ] Click **Start over** (or `POST /api/reset`) so the screen is empty.
- [ ] Copy the 9 files from `dataset/listings/*/` (not `ground_truth.json`) into one folder,
      ready to drag.
- [ ] Mic allowed for localhost; headset to avoid echo. Screen recorder at 1080p.
- [ ] Do one full dry run (warms up models, checks timing).

## Scenes

| # | Time | Screen | Say / do |
|---|---|---|---|
| 1 | 0:00 | Empty app | "A broker sent me four apartments — brochures, floor plans, a photo of a price sheet. Let's see what the agent makes of them." |
| 2 | 0:10 | Drag the 9 files | Drop them on the left. The narration panel opens by itself. |
| 3 | 0:15–0:45 | Narration streaming | Point at: "native text layer read for free", "floor plan → vision model", "property photo skipped", a retry with a stronger model if one happens, and the ⚠ conflicts at the end. Mention the cost line. |
| 4 | 0:45 | Cards | Click **Harbor View**'s amber "2 bd" → the viewer shows the brochure line "Bedrooms 2" and the conflict note; click the floor-plan tab to show the room labeled OFFICE. "The documents disagree, so it keeps both." Close. |
| 5 | 0:55–1:45 | Click **Talk** | "Hi! I got some apartment documents from a broker — can you help me pick one?" → "I need at least two bedrooms." → "And I really want a barbecue grill." (the floor plan with the BBQ opens by itself) → "Is it a good price for the area?" |
| 6 | 1:45 | README eval table | "I designed for hard cases, then measured: the cheap model got 100% too, so it's the default now — 7.8× cheaper, with a strong model only as a retry." End on the repo URL. |

## Lines to have ready (interview follow-ups)

- *Why LangGraph only in ingestion?* That's where the control flow is: parallel branches,
  verification, escalation. The live conversation uses deterministic tools so voice never waits
  on a vision call. (DECISIONS [002])
- *How do you know it's right?* Synthetic dataset with exact ground truth and designed traps;
  evals per source type. (DECISIONS [005], [010])
- *Cost?* Text layer is free; I designed a cautious routing (strong models on images), then the
  eval showed the cheap model gets 100% too — so cheap-first is the default, 7.8× cheaper, with a
  strong model only retrying readings that fail verification. Caveat: small synthetic test set;
  with harder documents I'd re-run the same eval. (DECISIONS [016])
- *What would you do for production?* Sideband connection for voice tools, a job queue instead of
  in-process tasks, calibrated confidence, real-document eval split.
