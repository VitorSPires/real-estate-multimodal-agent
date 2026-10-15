export const usd = (value: unknown) =>
  typeof value === 'number' ? `$${value.toLocaleString('en-US')}` : '—'

export const AMENITY_LABELS: Record<string, string> = {
  bbq_grill: 'BBQ grill',
  pool: 'Pool',
  gym: 'Gym',
  gourmet_balcony: 'Gourmet balcony',
  pet_friendly: 'Pet friendly',
  elevator: 'Elevator',
  doorman: 'Doorman',
}

export const FIELD_LABELS: Record<string, string> = {
  price_usd: 'Price',
  area_m2: 'Area',
  price_per_m2: 'Price per m²',
  bedrooms: 'Bedrooms',
  suites: 'Suites',
  bathrooms: 'Bathrooms',
  parking_spots: 'Parking',
  floor: 'Floor',
  condo_fee_usd: 'Condo fee',
  property_tax_usd: 'Property tax',
  neighborhood: 'Neighborhood',
  price_trend: 'Neighborhood price trend',
}

export const labelFor = (field: string) =>
  FIELD_LABELS[field] ?? AMENITY_LABELS[field.replace('amenity.', '')] ?? field.replaceAll('_', ' ')

export const METHOD_LABELS = { native_text: 'PDF text layer', vision: 'Vision model', computed: 'Computed' } as const
