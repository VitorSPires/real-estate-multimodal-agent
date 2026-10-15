# 03 — Voice conversation

## What the user sees

Next to the message box there is a **Talk** button. After the user allows the microphone, a small
colored dot shows the call state — listening (blue), checking (amber), speaking (green) — with
mute and hang-up buttons. The assistant greets the user and answers by voice; what both sides say
appears in the chat as text, and the same things happen on screen as in the typed chat: matching
cards light up and the evidence viewer opens on the document that proves the answer.

## Step by step

1. The user clicks **Talk**. The browser asks for the microphone, creates a WebRTC connection and
   a data channel called `oai-events`, and prepares a connection offer (SDP).
2. The browser sends the offer to `POST /api/live/session`. The backend creates the GPT-Live-1
   session with the OpenAI SDK (`client.live.create`) using its own API key, and returns OpenAI's
   answer. **The API key never reaches the browser.**
3. Audio now flows directly between the browser and OpenAI. GPT-Live-1 listens and speaks; for
   anything about the apartments it *delegates* to a backend Responses model, configured with the
   same instructions and tools as the typed chat.
4. When that model calls a tool, the event arrives on the data channel. The browser relays it to
   `POST /api/live/tools`, which runs the tool against the stored listings, and sends the result
   back on the channel (`function_call_output` + `response.create`). The app also reacts to the
   result (highlight cards, open evidence).
5. Transcripts arrive as small text pieces (`session.input_transcript.delta`,
   `session.output_transcript.delta`). They are appended to the current chat message; a change of
   speaker or a pause of more than 1.2 s starts a new message.
6. Mute sends `session.input_audio.mute` and disables the microphone track; hang up sends
   `session.close` and releases the microphone.

## Rules

- Voice needs `OPENAI_API_KEY` (GPT-Live is only on OpenAI's API, not on OpenRouter), even when
  extraction runs through OpenRouter or offline.
- The voice model never states listing facts itself; the backend model must use tools.
- Only known tools can be called through the relay (`404` otherwise).
- Typed messages during a call still go to the text chat (`POST /api/chat`).

## States and errors

- Microphone blocked → "Microphone access is blocked — allow it in the browser to talk."
- No key → `503` "Voice needs a valid OPENAI_API_KEY…"; rejected key → `502` with a clear message.
- Connection drops → "The voice connection dropped." and the call ends.

## Code references

- Backend: `backend/app/live/session.py` (session config), `backend/app/api/live.py`
  (`POST /api/live/session`, `POST /api/live/tools`)
- Frontend: `frontend/src/features/voice/useLiveSession.ts` (WebRTC + events),
  `VoiceControls.tsx` (button / call state), `useAssistantThread.ts` (`addVoiceTranscript`, `addVoiceStep`)
