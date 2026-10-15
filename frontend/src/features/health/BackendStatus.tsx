import { useEffect, useState } from 'react'

type Status = 'checking' | 'online' | 'offline'

const LABEL: Record<Status, string> = {
  checking: 'Checking backend…',
  online: 'Backend online',
  offline: 'Backend offline',
}

const DOT: Record<Status, string> = {
  checking: 'bg-muted-foreground',
  online: 'bg-emerald-500',
  offline: 'bg-destructive',
}

/** Small header badge that proves the Vite → FastAPI proxy works. */
export function BackendStatus() {
  const [status, setStatus] = useState<Status>('checking')

  useEffect(() => {
    fetch('/api/health')
      .then((response) => setStatus(response.ok ? 'online' : 'offline'))
      .catch(() => setStatus('offline'))
  }, [])

  return (
    <span className="text-muted-foreground flex items-center gap-2 text-sm">
      <span className={`size-2 rounded-full ${DOT[status]}`} />
      {LABEL[status]}
    </span>
  )
}
