import { useCallback, useRef, useState } from 'react'

import { api, type ListingRecord, type NarrationEvent, type RunEvent } from '@/lib/api'

export type RunStatus = 'idle' | 'running' | 'done' | 'failed'

export type IngestionRun = {
  id: string
  status: RunStatus
  narration: NarrationEvent[]
  documents: number
}

/** Starts a run (upload or samples) and follows its SSE narration until the end event. */
export function useIngestion(onListing: (listing: ListingRecord) => void, onFinished: () => void) {
  const [runs, setRuns] = useState<IngestionRun[]>([])
  const sourceRef = useRef<EventSource | undefined>(undefined)

  const update = useCallback((id: string, change: (run: IngestionRun) => IngestionRun) => {
    setRuns((current) => current.map((run) => (run.id === id ? change(run) : run)))
  }, [])

  const follow = useCallback(
    (id: string, documents: number) => {
      sourceRef.current?.close()
      setRuns((current) => [...current, { id, status: 'running', narration: [], documents }])

      // EventSource reconnects on its own and sends Last-Event-ID, so a dropped connection resumes.
      const source = new EventSource(`/api/ingestions/${id}/events`)
      sourceRef.current = source
      source.onmessage = (message) => {
        const event = JSON.parse(message.data) as RunEvent
        if (event.type === 'narration') {
          update(id, (run) => ({
            ...run,
            narration: [...run.narration, event],
            status: event.level === 'error' ? 'failed' : run.status,
          }))
        } else if (event.type === 'listing') {
          onListing(event.listing)
        }
      }
      source.addEventListener('end', () => {
        source.close()
        update(id, (run) => ({ ...run, status: run.status === 'failed' ? 'failed' : 'done' }))
        onFinished()
      })
    },
    [onFinished, onListing, update],
  )

  const startSample = useCallback(async () => {
    const { run_id } = await api.startSample()
    follow(run_id, 9)
    return run_id
  }, [follow])

  const upload = useCallback(
    async (files: File[]) => {
      const { run_id } = await api.upload(files)
      follow(run_id, files.length)
      return run_id
    },
    [follow],
  )

  const clear = useCallback(() => {
    sourceRef.current?.close()
    setRuns([])
  }, [])

  const isRunning = runs.some((run) => run.status === 'running')
  return { runs, isRunning, startSample, upload, clear }
}
