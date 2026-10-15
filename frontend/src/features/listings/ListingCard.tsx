import { AlertTriangleIcon, BathIcon, BedDoubleIcon, CarIcon, RulerIcon } from 'lucide-react'
import type { ReactNode } from 'react'

import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { FieldValue, ListingRecord } from '@/lib/api'
import { AMENITY_LABELS, usd } from '@/lib/format'
import { cn } from '@/lib/utils'

type Props = {
  listing: ListingRecord
  highlighted: boolean
  onShowEvidence: (listing: ListingRecord, field: string) => void
}

/** One apartment. Every value is clickable and opens the document region it came from. */
export function ListingCard({ listing, highlighted, onShowEvidence }: Props) {
  const field = (name: string): FieldValue | undefined => listing.fields[name]
  const conflicts = Object.entries(listing.fields).flatMap(([name, value]) =>
    value.conflict.filter((alt) => alt.note).map((alt) => ({ name, note: alt.note as string })),
  )
  const amenities = Object.entries(listing.amenities).filter(([, value]) => value.value === true)

  return (
    <Card
      className={cn('shrink-0 gap-3 py-4 transition-shadow', highlighted && 'ring-primary shadow-lg ring-2')}
      data-listing={listing.id}
    >
      <CardHeader className="px-4">
        <CardTitle className="flex items-baseline justify-between gap-2">
          <span>{listing.title}</span>
          <button
            type="button"
            onClick={() => onShowEvidence(listing, 'price_usd')}
            className="hover:text-primary text-base font-semibold"
          >
            {usd(field('price_usd')?.value)}
          </button>
        </CardTitle>
        <p className="text-muted-foreground text-sm">
          {String(field('neighborhood')?.value ?? '—')} · floor {String(field('floor')?.value ?? '—')} ·{' '}
          <button type="button" className="hover:text-foreground" onClick={() => onShowEvidence(listing, 'price_per_m2')}>
            {usd(field('price_per_m2')?.value)}/m²
          </button>
        </p>
      </CardHeader>

      <CardContent className="flex flex-col gap-3 px-4">
        <div className="-mx-1.5 flex flex-wrap gap-x-1">
          <Fact field={field('bedrooms')} onClick={() => onShowEvidence(listing, 'bedrooms')} icon={<BedDoubleIcon className="size-3.5" />} unit="bd" />
          <Fact field={field('bathrooms')} onClick={() => onShowEvidence(listing, 'bathrooms')} icon={<BathIcon className="size-3.5" />} unit="ba" />
          <Fact field={field('area_m2')} onClick={() => onShowEvidence(listing, 'area_m2')} icon={<RulerIcon className="size-3.5" />} unit="m²" />
          <Fact field={field('parking_spots')} onClick={() => onShowEvidence(listing, 'parking_spots')} icon={<CarIcon className="size-3.5" />} unit="" />
        </div>

        <p className="text-muted-foreground text-xs">
          <button type="button" className="hover:text-foreground" onClick={() => onShowEvidence(listing, 'condo_fee_usd')}>
            Condo {usd(field('condo_fee_usd')?.value)}/mo
          </button>
          {' · '}
          <button type="button" className="hover:text-foreground" onClick={() => onShowEvidence(listing, 'property_tax_usd')}>
            Tax {usd(field('property_tax_usd')?.value)}/yr
          </button>
        </p>

        {amenities.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {amenities.map(([name]) => (
              <Badge key={name} variant="secondary" asChild>
                <button type="button" onClick={() => onShowEvidence(listing, name)}>
                  {AMENITY_LABELS[name] ?? name}
                </button>
              </Badge>
            ))}
          </div>
        )}

        {conflicts.map(({ name, note }) => (
          <button
            key={`${name}-${note}`}
            type="button"
            onClick={() => onShowEvidence(listing, name)}
            className="flex items-start gap-1.5 rounded-md bg-amber-500/10 px-2 py-1.5 text-left text-xs text-amber-700 dark:text-amber-300"
          >
            <AlertTriangleIcon className="mt-0.5 size-3.5 shrink-0" />
            <span>{note}</span>
          </button>
        ))}

        <p className="text-muted-foreground text-[11px]">{listing.documents.length} documents</p>
      </CardContent>
    </Card>
  )
}

type FactProps = { field: FieldValue | undefined; icon: ReactNode; unit: string; onClick: () => void }

/** A small clickable fact; amber when the documents disagree about it. */
function Fact({ field, icon, unit, onClick }: FactProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      title="Show where this came from"
      className={cn(
        'hover:bg-accent flex items-center gap-1 rounded-md px-1.5 py-0.5 text-sm transition-colors',
        field?.conflict.length && 'text-amber-600 dark:text-amber-400',
      )}
    >
      {icon}
      {String(field?.value ?? '—')} {unit}
    </button>
  )
}
