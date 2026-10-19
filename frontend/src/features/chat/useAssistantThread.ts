import { useCallback, useMemo, useRef, useState } from 'react'
import { useExternalStoreRuntime, type AppendMessage, type ThreadMessageLike } from '@assistant-ui/react'

import type { IngestionRun } from '@/features/ingestion/useIngestion'
import type { Speaker } from '@/features/voice/useLiveSession'
import { api, type ChatStep, type ListingRecord } from '@/lib/api'

/** One entry of the conversation timeline. Ingestion runs appear in the thread where they started. */
export type TimelineEntry =
  | { kind: 'run'; runId: string }
  | { kind: 'user'; id: string; text: string; via?: 'voice' }
  | { kind: 'assistant'; id: string; text: string; steps: ChatStep[]; via?: 'voice' }

type Options = {
  runs: IngestionRun[]
  listings: ListingRecord[]
  onStep: (step: ChatStep) => void
}

const LEVEL_ICON = { info: '', warn: '⚠️ ', success: '✅ ', error: '❌ ' } as const

/**
 * Owns the conversation timeline and exposes it to assistant-ui through an external-store runtime:
 * we keep the messages in React state, assistant-ui only renders them and calls `onNew`.
 */
export function useAssistantThread({ runs, listings, onStep }: Options) {
  const [timeline, setTimeline] = useState<TimelineEntry[]>([])
  const [isSending, setIsSending] = useState(false)

  const addRun = useCallback((runId: string) => {
    setTimeline((current) => [...current, { kind: 'run', runId }])
  }, [])

  // --- Voice: transcripts and tool calls land in the same thread as typed messages -------------
  const voiceTurn = useRef<{ speaker: Speaker; id: string; hasText: boolean } | undefined>(undefined)

  const startVoiceTurn = (speaker: Speaker, text: string, steps: ChatStep[] = []) => {
    const id = crypto.randomUUID()
    voiceTurn.current = { speaker, id, hasText: text.length > 0 }
    const entry: TimelineEntry =
      speaker === 'user' ? { kind: 'user', id, text, via: 'voice' } : { kind: 'assistant', id, text, steps, via: 'voice' }
    setTimeline((current) => [...current, entry])
  }

  const changeVoiceTurn = (change: (entry: TimelineEntry) => TimelineEntry) => {
    const id = voiceTurn.current?.id
    setTimeline((current) => current.map((entry) => (entry.kind !== 'run' && entry.id === id ? change(entry) : entry)))
  }

  const addVoiceTranscript = useCallback((speaker: Speaker, delta: string, newTurn: boolean) => {
    const turn = voiceTurn.current
    // An assistant turn opened by a tool call (no words yet) takes the words that follow it.
    const continues = turn?.speaker === speaker && (!newTurn || (speaker === 'assistant' && !turn.hasText))
    if (!continues) return startVoiceTurn(speaker, delta)
    turn.hasText = true
    changeVoiceTurn((entry) => (entry.kind === 'run' ? entry : { ...entry, text: entry.text + delta }))
  }, [])

  const addVoiceStep = useCallback((step: ChatStep) => {
    if (voiceTurn.current?.speaker !== 'assistant') return startVoiceTurn('assistant', '', [step])
    changeVoiceTurn((entry) => (entry.kind === 'assistant' ? { ...entry, steps: [...entry.steps, step] } : entry))
  }, [])

  const onNew = useCallback(
    async (message: AppendMessage) => {
      const text = message.content.map((part) => (part.type === 'text' ? part.text : '')).join('').trim()
      if (!text) return
      const history = [
        ...timeline.flatMap((entry) =>
          entry.kind === 'run' ? [] : [{ role: entry.kind, content: entry.text } as const],
        ),
        { role: 'user' as const, content: text },
      ]
      setTimeline((current) => [...current, { kind: 'user', id: crypto.randomUUID(), text }])
      setIsSending(true)
      try {
        const response = await api.chat(history)
        response.steps.forEach(onStep)
        setTimeline((current) => [
          ...current,
          { kind: 'assistant', id: crypto.randomUUID(), text: response.reply, steps: response.steps },
        ])
      } catch {
        setTimeline((current) => [
          ...current,
          { kind: 'assistant', id: crypto.randomUUID(), text: 'Sorry — I could not reach the backend.', steps: [] },
        ])
      } finally {
        setIsSending(false)
      }
    },
    [onStep, timeline],
  )

  const messages = useMemo(
    () => timeline.map((entry) => toMessage(entry, runs, listings)).filter((m): m is ThreadMessageLike => m !== null),
    [listings, runs, timeline],
  )

  const runtime = useExternalStoreRuntime({
    messages,
    isRunning: isSending,
    onNew,
    convertMessage: (message: ThreadMessageLike) => message,
    // Starter prompts only until the conversation begins (they'd be stale afterwards).
    suggestions: listings.length && !timeline.some((entry) => entry.kind === 'user')
      ? [
          { prompt: 'Which apartments did the broker send?' },
          { prompt: 'I need at least two bedrooms.' },
          { prompt: 'Compare all of them.' },
        ]
      : [],
  })

  return { runtime, isSending, addRun, addVoiceTranscript, addVoiceStep }
}

function toMessage(entry: TimelineEntry, runs: IngestionRun[], listings: ListingRecord[]): ThreadMessageLike | null {
  if (entry.kind === 'user') return { id: entry.id, role: 'user', content: [{ type: 'text', text: entry.text }] }

  if (entry.kind === 'assistant') {
    return {
      id: entry.id,
      role: 'assistant',
      content: [
        ...entry.steps.map((step, index) => ({
          type: 'tool-call' as const,
          toolCallId: `${entry.id}-${index}`,
          toolName: step.tool,
          args: step.arguments as never,
          result: step.result,
        })),
        ...(entry.text ? [{ type: 'text' as const, text: entry.text }] : []),
      ],
    }
  }

  const run = runs.find((candidate) => candidate.id === entry.runId)
  if (!run) return null
  const narration = run.narration.map((line) => `- ${LEVEL_ICON[line.level]}${line.text}`).join('\n')
  const running = run.status === 'running'
  return {
    id: `run-${run.id}`,
    role: 'assistant',
    status: running ? { type: 'running' } : { type: 'complete', reason: 'stop' },
    content: [
      { type: 'reasoning', text: narration || '- Starting…' },
      ...(running ? [] : [{ type: 'text' as const, text: runSummary(run, listings) }]),
    ],
  }
}

function runSummary(run: IngestionRun, listings: ListingRecord[]): string {
  if (run.status === 'failed') {
    const error = [...run.narration].reverse().find((line) => line.level === 'error')
    return `I couldn't finish reading the documents. ${error?.text ?? ''}`
  }
  const names = listings.map((listing) => `**${listing.title}**`).join(', ')
  const conflicts = listings.filter((listing) => Object.values(listing.fields).some((f) => f.conflict.length)).length
  return (
    `I read ${run.documents} documents and found ${listings.length} apartments: ${names}. ` +
    (conflicts ? `${conflicts} of them have documents that disagree — I flagged those on the cards. ` : '') +
    'Tell me what matters to you, or tap the mic and just talk.'
  )
}
