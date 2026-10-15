import { useState } from 'react'

import { Badge } from '@/components/ui/badge'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { fileUrl, type Evidence } from '@/lib/api'
import { labelFor, METHOD_LABELS } from '@/lib/format'
import { cn } from '@/lib/utils'

export type EvidenceRequest = {
  listingTitle: string
  field: string
  value: unknown
  evidence: Evidence[]
  conflicts: { value: unknown; note: string | null; evidence?: Evidence[] }[]
}

type Props = { request: EvidenceRequest | null; onClose: () => void }

/** Shows the page (or image) a fact came from, with the source region highlighted. */
export function EvidenceViewer({ request, onClose }: Props) {
  const sources = request ? [...request.evidence, ...request.conflicts.flatMap((c) => c.evidence ?? [])] : []
  const [selected, setSelected] = useState(0)
  const current = sources[Math.min(selected, sources.length - 1)]

  return (
    <Sheet
      open={request !== null}
      onOpenChange={(open) => {
        if (!open) {
          setSelected(0)
          onClose()
        }
      }}
    >
      <SheetContent className="w-full gap-0 sm:max-w-xl">
        {request && (
          <>
            <SheetHeader>
              <SheetTitle>
                {labelFor(request.field)} · {request.listingTitle}
              </SheetTitle>
              <SheetDescription>
                Value: <strong className="text-foreground">{formatValue(request.value)}</strong>
              </SheetDescription>
            </SheetHeader>

            <div className="flex flex-col gap-3 overflow-y-auto px-4 pb-6">
              {request.conflicts.map((conflict) => (
                <p key={String(conflict.note)} className="rounded-md bg-amber-500/10 px-3 py-2 text-sm text-amber-700 dark:text-amber-300">
                  ⚠ {conflict.note ?? `Another source says ${formatValue(conflict.value)}`}
                </p>
              ))}

              {sources.length > 1 && (
                <div className="flex flex-wrap gap-1">
                  {sources.map((source, index) => (
                    <button
                      key={`${source.document}-${index}`}
                      type="button"
                      onClick={() => setSelected(index)}
                      className={cn(
                        'rounded-md border px-2 py-1 text-xs',
                        index === selected ? 'border-primary bg-accent' : 'text-muted-foreground',
                      )}
                    >
                      {source.document}
                      {source.page ? ` p.${source.page}` : ''}
                    </button>
                  ))}
                </div>
              )}

              {current ? <Source evidence={current} /> : <p className="text-muted-foreground text-sm">No source recorded (not mentioned in any document).</p>}
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  )
}

function Source({ evidence }: { evidence: Evidence }) {
  const [x0, y0, x1, y1] = evidence.bbox ?? [0, 0, 0, 0]
  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-1.5 text-xs">
        <span className="font-medium">{evidence.document}</span>
        {evidence.page && <span className="text-muted-foreground">page {evidence.page}</span>}
        <Badge variant="outline">{METHOD_LABELS[evidence.method]}</Badge>
        {evidence.model && <Badge variant="secondary">{evidence.model.split('/').pop()}</Badge>}
      </div>
      {evidence.quote && <blockquote className="border-l-2 pl-3 text-sm italic">“{evidence.quote}”</blockquote>}
      {evidence.image_path && (
        <div className="relative overflow-hidden rounded-md border">
          <img src={fileUrl(evidence.image_path)} alt={`Source: ${evidence.document}`} className="block w-full" />
          {evidence.bbox && (
            <div
              className="absolute rounded-sm border-2 border-amber-500 bg-amber-400/25 shadow-[0_0_0_9999px_rgba(0,0,0,0.25)]"
              style={{
                left: `${x0 * 100}%`,
                top: `${y0 * 100}%`,
                width: `${(x1 - x0) * 100}%`,
                height: `${(y1 - y0) * 100}%`,
              }}
            />
          )}
        </div>
      )}
    </div>
  )
}

function formatValue(value: unknown): string {
  if (typeof value === 'number') return value.toLocaleString('en-US')
  if (typeof value === 'boolean') return value ? 'yes' : 'not mentioned'
  if (Array.isArray(value)) return `${value.length} data points`
  return String(value ?? '—')
}
