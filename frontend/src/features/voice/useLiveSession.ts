import { useCallback, useRef, useState } from 'react'

import type { ChatStep } from '@/lib/api'

export type VoiceStatus = 'idle' | 'connecting' | 'listening' | 'thinking' | 'speaking' | 'error'
export type Speaker = 'user' | 'assistant'

type Handlers = {
  /** A piece of transcript. `newTurn` = start a new message instead of appending to the last one. */
  onTranscript: (speaker: Speaker, delta: string, newTurn: boolean) => void
  /** A tool the voice session's backend model called, with its result (drives the UI like typed chat). */
  onToolCall: (step: ChatStep) => void
}

type LiveEvent = {
  type: string
  delta?: string
  start_ms?: number
  end_ms?: number
  event?: { type?: string; item?: { type?: string; call_id?: string; name?: string; arguments?: string } }
  error?: { message?: string }
}

// Transcripts arrive as deltas only. A pause longer than this starts a new message.
const TURN_GAP_MS = 1200

/**
 * A GPT-Live-1 call over WebRTC:
 * 1. microphone + RTCPeerConnection + data channel "oai-events"
 * 2. our backend trades the SDP offer for OpenAI's answer (the API key never reaches the browser)
 * 3. audio flows directly; transcripts and tool calls arrive as data-channel events
 * 4. tool calls are relayed to POST /api/live/tools and the result is sent back on the channel
 */
export function useLiveSession({ onTranscript, onToolCall }: Handlers) {
  const [status, setStatus] = useState<VoiceStatus>('idle')
  const [error, setError] = useState<string>()
  const [muted, setMuted] = useState(false)

  const peer = useRef<RTCPeerConnection | undefined>(undefined)
  const channel = useRef<RTCDataChannel | undefined>(undefined)
  const mic = useRef<MediaStream | undefined>(undefined)
  const speaker = useRef<HTMLAudioElement | undefined>(undefined)
  const lastTurn = useRef<{ speaker: Speaker; endMs: number } | undefined>(undefined)
  const handledCalls = useRef(new Set<string>())

  const send = useCallback((event: Record<string, unknown>) => {
    if (channel.current?.readyState === 'open') channel.current.send(JSON.stringify(event))
  }, [])

  const transcript = useCallback(
    (who: Speaker, event: LiveEvent) => {
      const previous = lastTurn.current
      const newTurn = !previous || previous.speaker !== who || (event.start_ms ?? 0) - previous.endMs > TURN_GAP_MS
      lastTurn.current = { speaker: who, endMs: event.end_ms ?? 0 }
      onTranscript(who, event.delta ?? '', newTurn)
    },
    [onTranscript],
  )

  const runTool = useCallback(
    async (item: NonNullable<LiveEvent['event']>['item']) => {
      if (!item?.call_id || !item.name || handledCalls.current.has(item.call_id)) return
      handledCalls.current.add(item.call_id)
      setStatus('thinking')

      const args = item.arguments ? (JSON.parse(item.arguments) as Record<string, unknown>) : {}
      let result: Record<string, unknown>
      try {
        const response = await fetch('/api/live/tools', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name: item.name, arguments: args }),
        })
        result = await response.json()
      } catch {
        result = { error: 'The tool could not be reached.' }
      }
      onToolCall({ tool: item.name, arguments: args, result })
      send({ type: 'response.item.create', item: { type: 'function_call_output', call_id: item.call_id, output: JSON.stringify(result) } })
      send({ type: 'response.create' })
    },
    [onToolCall, send],
  )

  const handle = useCallback(
    (event: LiveEvent) => {
      switch (event.type) {
        case 'session.started':
          setStatus('listening')
          send({
            type: 'session.instructions.append',
            delegation_id: null,
            content: 'Greet the user in one short sentence and ask how you can help with the apartments.',
          })
          break
        case 'session.input_transcript.delta':
          setStatus('listening')
          transcript('user', event)
          break
        case 'session.output_transcript.delta':
          setStatus('speaking')
          transcript('assistant', event)
          break
        case 'session.delegation.created':
          setStatus('thinking')
          break
        case 'response.event':
          if (event.event?.type === 'response.output_item.done' && event.event.item?.type === 'function_call') {
            void runTool(event.event.item)
          }
          break
        case 'error':
          setError(event.error?.message ?? 'Voice session error')
          break
      }
    },
    [runTool, send, transcript],
  )

  const disconnect = useCallback(() => {
    send({ type: 'session.close' })
    mic.current?.getTracks().forEach((track) => track.stop())
    peer.current?.close()
    speaker.current?.remove()
    peer.current = channel.current = mic.current = speaker.current = undefined
    lastTurn.current = undefined
    handledCalls.current.clear()
    setMuted(false)
    setStatus('idle')
  }, [send])

  const connect = useCallback(async () => {
    setError(undefined)
    setStatus('connecting')
    try {
      const connection = new RTCPeerConnection()
      peer.current = connection
      mic.current = await navigator.mediaDevices.getUserMedia({ audio: true })
      mic.current.getTracks().forEach((track) => connection.addTrack(track, mic.current!))

      const audio = new Audio()
      audio.autoplay = true
      document.body.appendChild(audio)
      speaker.current = audio
      connection.ontrack = (event) => {
        audio.srcObject = event.streams[0]
      }
      connection.onconnectionstatechange = () => {
        if (connection.connectionState === 'failed') {
          setError('The voice connection dropped.')
          setStatus('error')
        }
      }

      channel.current = connection.createDataChannel('oai-events')
      channel.current.onmessage = (message) => handle(JSON.parse(message.data) as LiveEvent)

      await connection.setLocalDescription(await connection.createOffer())
      const response = await fetch('/api/live/session', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sdp: connection.localDescription?.sdp }),
      })
      const body = await response.json()
      if (!response.ok) throw new Error(body.detail ?? 'Could not start the voice session.')
      await connection.setRemoteDescription({ type: 'answer', sdp: body.sdp })
    } catch (cause) {
      disconnect()
      const micBlocked = cause instanceof DOMException && cause.name === 'NotAllowedError'
      setError(
        micBlocked
          ? 'Microphone access is blocked — allow it in the browser to talk.'
          : cause instanceof Error
            ? cause.message
            : 'Could not start the voice session.',
      )
      setStatus('error')
    }
  }, [disconnect, handle])

  const toggleMute = useCallback(() => {
    const next = !muted
    mic.current?.getAudioTracks().forEach((track) => (track.enabled = !next))
    send({ type: next ? 'session.input_audio.mute' : 'session.input_audio.unmute' })
    setMuted(next)
  }, [muted, send])

  return { status, error, muted, connect, disconnect, toggleMute }
}
