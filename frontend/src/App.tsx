import { useState } from 'react'
import {
  AssistantRuntimeProvider,
  useExternalStoreRuntime,
  type AppendMessage,
  type ThreadMessageLike,
} from '@assistant-ui/react'

import { Thread } from '@/components/assistant-ui/thread.aui'
import { TooltipProvider } from '@/components/ui/tooltip'
import { BackendStatus } from '@/features/health/BackendStatus'

// Phase 0 placeholder: the thread is fed by local state only.
// Phase 5 replaces this with ingestion narration (SSE) + the agent conversation.
function useScaffoldRuntime() {
  const [messages, setMessages] = useState<ThreadMessageLike[]>([])

  const onNew = async (message: AppendMessage) => {
    const text = message.content
      .map((part) => (part.type === 'text' ? part.text : ''))
      .join('')
    setMessages((current) => [
      ...current,
      { role: 'user', content: [{ type: 'text', text }] },
      {
        role: 'assistant',
        content: [{ type: 'text', text: 'The agent is not connected yet (Phase 0 scaffold).' }],
      },
    ])
  }

  return useExternalStoreRuntime({
    messages,
    onNew,
    convertMessage: (message: ThreadMessageLike) => message,
  })
}

export default function App() {
  const runtime = useScaffoldRuntime()

  return (
    <TooltipProvider>
      <AssistantRuntimeProvider runtime={runtime}>
        <div className="bg-background text-foreground flex h-dvh flex-col">
          <header className="flex items-center justify-between border-b px-6 py-3">
            <h1 className="text-lg font-semibold">ListingLens</h1>
            <BackendStatus />
          </header>

          <main className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[320px_1fr]">
            <aside className="text-muted-foreground hidden border-r p-6 text-sm lg:block">
              Documents and listing cards will appear here.
            </aside>
            <section className="min-h-0">
              <Thread />
            </section>
          </main>
        </div>
      </AssistantRuntimeProvider>
    </TooltipProvider>
  )
}
