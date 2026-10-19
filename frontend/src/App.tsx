import { useCallback, useEffect, useState } from 'react'
import { AssistantRuntimeProvider } from '@assistant-ui/react'
import { RotateCcwIcon } from 'lucide-react'

import { Thread } from '@/components/assistant-ui/thread.aui'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { TooltipProvider } from '@/components/ui/tooltip'
import { useAssistantThread } from '@/features/chat/useAssistantThread'
import { Welcome } from '@/features/chat/Welcome'
import { EvidenceViewer, type EvidenceRequest } from '@/features/evidence/EvidenceViewer'
import { BackendStatus } from '@/features/health/BackendStatus'
import { DropZone } from '@/features/ingestion/DropZone'
import { useIngestion } from '@/features/ingestion/useIngestion'
import { useLiveSession } from '@/features/voice/useLiveSession'
import { VoiceControls } from '@/features/voice/VoiceControls'
import { VoiceContext } from '@/features/voice/voiceContext'
import { ListingCard } from '@/features/listings/ListingCard'
import { api, type ChatStep, type Evidence, type Health, type ListingRecord } from '@/lib/api'

export default function App() {
  const [listings, setListings] = useState<ListingRecord[]>([])
  const [health, setHealth] = useState<Health>()
  const [evidence, setEvidence] = useState<EvidenceRequest | null>(null)
  const [highlighted, setHighlighted] = useState<string[]>([])

  const refreshListings = useCallback(() => {
    api.listings().then(setListings).catch(() => setListings([]))
  }, [])

  useEffect(() => {
    refreshListings()
    api.health().then(setHealth).catch(() => undefined)
  }, [refreshListings])

  const upsertListing = useCallback((listing: ListingRecord) => {
    setListings((current) =>
      [...current.filter((item) => item.id !== listing.id), listing].sort((a, b) => a.id.localeCompare(b.id)),
    )
  }, [])

  const ingestion = useIngestion(upsertListing, refreshListings)

  const showEvidence = useCallback((listing: ListingRecord, field: string) => {
    const value = field in listing.amenities ? listing.amenities[field] : field === 'price_trend' ? listing.price_trend : listing.fields[field]
    if (!value) return
    setEvidence({
      listingTitle: listing.title,
      field,
      value: value.value,
      evidence: value.evidence,
      conflicts: value.conflict.map((alt) => ({ value: alt.value, note: alt.note, evidence: alt.evidence })),
    })
  }, [])

  /** Tool calls from the assistant (typed or spoken) drive the screen. */
  const onStep = useCallback((step: ChatStep) => {
    const result = step.result as Record<string, unknown>
    if (step.tool === 'show_evidence' && result.found) {
      setEvidence({
        listingTitle: String(result.title),
        field: String(result.field),
        value: result.value,
        evidence: result.evidence as Evidence[],
        conflicts: (result.conflicts as { value: unknown; note: string }[]) ?? [],
      })
      setHighlighted([String(result.listing_id)])
    }
    if (step.tool === 'filter_listings') {
      setHighlighted(((result.matches as { id: string }[]) ?? []).map((match) => match.id))
    }
  }, [])

  const thread = useAssistantThread({ runs: ingestion.runs, listings, onStep })
  const { addVoiceStep } = thread
  const voice = useLiveSession({
    onTranscript: thread.addVoiceTranscript,
    onToolCall: useCallback((step: ChatStep) => {
      onStep(step)
      addVoiceStep(step)
    }, [addVoiceStep, onStep]),
  })

  const start = async (begin: () => Promise<string>) => {
    const runId = await begin()
    thread.addRun(runId)
  }

  const reset = async () => {
    await api.reset()
    ingestion.clear()
    setListings([])
    setHighlighted([])
  }

  return (
    <TooltipProvider>
      <VoiceContext.Provider value={voice}>
        <AssistantRuntimeProvider runtime={thread.runtime}>
          <div className="bg-background text-foreground flex h-dvh flex-col">
            <header className="flex items-center justify-between gap-3 border-b px-4 py-3 sm:px-6">
              <div className="flex items-center gap-2">
                <h1 className="text-lg font-semibold">ListingLens</h1>
                {health?.llm_provider === 'fake' && (
                  <Badge variant="outline" className="border-amber-500/50 text-amber-700 dark:text-amber-300" title="No API key configured: model answers are canned test fixtures.">
                    Offline mode
                  </Badge>
                )}
              </div>
              <BackendStatus />
            </header>

            <main className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[360px_1fr]">
              <aside className="flex min-h-0 flex-col gap-4 overflow-y-auto border-b p-4 lg:border-r lg:border-b-0">
                <DropZone
                  disabled={ingestion.isRunning}
                  onFiles={(files) => start(() => ingestion.upload(files))}
                  onSample={() => start(ingestion.startSample)}
                />
                {listings.map((listing) => (
                  <ListingCard
                    key={listing.id}
                    listing={listing}
                    highlighted={highlighted.includes(listing.id)}
                    onShowEvidence={showEvidence}
                  />
                ))}
                {listings.length > 0 && (
                  <Button variant="ghost" size="sm" className="text-muted-foreground self-start" onClick={reset}>
                    <RotateCcwIcon /> Start over
                  </Button>
                )}
              </aside>
              <section className="min-h-0" aria-busy={thread.isSending}>
                <Thread components={{ Welcome, ComposerActions: VoiceControls }} />
              </section>
            </main>
          </div>
          <EvidenceViewer request={evidence} onClose={() => setEvidence(null)} />
        </AssistantRuntimeProvider>
      </VoiceContext.Provider>
    </TooltipProvider>
  )
}
