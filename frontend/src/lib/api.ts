// Types mirror backend/app/ingestion/schemas.py and the API responses.

export type Evidence = {
  document: string
  page: number | null
  bbox: [number, number, number, number] | null // normalized 0–1 on the page / image
  quote: string | null
  method: 'native_text' | 'vision' | 'computed'
  model: string | null
  image_path: string | null
}

export type Alternative = { value: unknown; evidence: Evidence[]; note: string | null }

export type FieldValue = {
  value: unknown
  confidence: number
  evidence: Evidence[]
  conflict: Alternative[]
}

export type ListingRecord = {
  id: string
  title: string
  documents: string[]
  fields: Record<string, FieldValue>
  amenities: Record<string, FieldValue>
  price_trend: FieldValue | null
  warnings: string[]
}

export type NarrationEvent = {
  id?: number
  type: 'narration'
  text: string
  level: 'info' | 'warn' | 'success' | 'error'
  document?: string
  listing?: string
}

export type RunEvent =
  | NarrationEvent
  | { id?: number; type: 'facts'; document: string; facts: Record<string, unknown> }
  | { id?: number; type: 'listing'; listing: ListingRecord }
  | { type: 'end' }

export type ChatStep = { tool: string; arguments: Record<string, unknown>; result: Record<string, unknown> }
export type ChatResponse = { reply: string; steps: ChatStep[]; offline: boolean }
export type Health = { status: string; llm_provider: 'openrouter' | 'openai' | 'fake' }

export const fileUrl = (path: string) => `/api/files/${path}`

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, init)
  if (!response.ok) throw new Error(`${init?.method ?? 'GET'} ${path} failed: ${response.status}`)
  return response.status === 204 ? (undefined as T) : response.json()
}

const postJson = <T>(path: string, body: unknown) =>
  request<T>(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })

export const api = {
  health: () => request<Health>('/health'),
  listings: () => request<ListingRecord[]>('/listings'),
  reset: () => request<void>('/reset', { method: 'POST' }),
  startSample: () => request<{ run_id: string }>('/ingestions/sample', { method: 'POST' }),
  upload: (files: File[]) => {
    const form = new FormData()
    files.forEach((file) => form.append('files', file))
    return request<{ run_id: string }>('/ingestions', { method: 'POST', body: form })
  },
  chat: (messages: { role: 'user' | 'assistant'; content: string }[]) => postJson<ChatResponse>('/chat', { messages }),
}
