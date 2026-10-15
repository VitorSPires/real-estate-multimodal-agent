# 02 — Talking to the assistant

## What the user sees

After the documents are read, the user asks questions in the chat — "I need at least two
bedrooms", "and a BBQ grill", "is it a good price for the area?". The assistant answers in a few
sentences, highlights the matching apartment cards, and opens the exact document region that
proves the deciding fact (for example the BBQ symbol on the floor plan). If the documents disagree
about something, the assistant says so. Each answer shows the lookups it made ("1 tool call"),
which can be expanded.

## Step by step

1. The user types a message. The frontend sends the whole conversation (text only) to
   `POST /api/chat`.
2. The backend runs a tool-calling loop: the chat model reads the instructions
   (`app/assistant/instructions.py`) and may call conversation tools several times before it
   answers (up to 5 rounds).
3. Tools are plain functions over the stored listings (`app/assistant/tools.py`): list, filter,
   get one, compare, neighborhood price check, show evidence. No model reads documents here — the
   answers come from the already verified data.
4. The response contains the reply and every tool call with its result. The frontend renders the
   tool calls in the thread and reacts to them: `filter_listings` highlights the matching cards,
   `show_evidence` opens the evidence viewer.
5. Clicking any value on a card also opens the evidence viewer: the PDF page with the source
   region highlighted, or the image the value was read from, plus the quote, the method (PDF text
   layer / vision model / computed) and the model.

## Rules

- Every fact must come from a tool result; the model is told never to guess.
- Requirements accumulate over the conversation ("and a BBQ grill" keeps "two bedrooms").
- Conflicts and low-confidence values (< 0.7) are mentioned explicitly.
- Answers are short and speakable — the same instructions serve the voice session.

## States and errors

- No documents yet → the assistant asks the user to drop files or try the samples.
- Unknown or ambiguous listing name → the tool returns an error listing the known ids; the model
  can recover by asking or using an id.
- Backend unreachable → the thread shows "Sorry — I could not reach the backend."
- Offline mode (no API key) → a rule-based stand-in (`app/assistant/offline.py`) handles the demo
  conversation with the same tools.

## Code references

- `POST /api/chat` — `backend/app/api/chat.py` → `app/assistant/chat.py`
- Tools — `backend/app/assistant/tools.py`; instructions — `app/assistant/instructions.py`
- Frontend thread — `frontend/src/features/chat/useAssistantThread.ts`
- Cards — `frontend/src/features/listings/ListingCard.tsx`
- Evidence viewer — `frontend/src/features/evidence/EvidenceViewer.tsx`
