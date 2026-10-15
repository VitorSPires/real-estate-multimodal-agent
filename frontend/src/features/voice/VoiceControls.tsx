import { useContext } from 'react'
import { MicIcon, MicOffIcon, PhoneOffIcon } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import type { VoiceStatus } from './useLiveSession'
import { VoiceContext } from './voiceContext'

const LABEL: Record<VoiceStatus, string> = {
  idle: 'Talk',
  connecting: 'Connecting…',
  listening: 'Listening',
  thinking: 'Checking…',
  speaking: 'Speaking',
  error: 'Talk',
}

/** Mic button in the composer. During a call: a pulsing orb with the call state, mute and hang up. */
export function VoiceControls() {
  const voice = useContext(VoiceContext)
  if (!voice) return null
  const inCall = voice.status !== 'idle' && voice.status !== 'error'

  if (!inCall) {
    return (
      <div className="flex items-center gap-2">
        {voice.error && <span className="text-destructive max-w-56 truncate text-xs" title={voice.error}>{voice.error}</span>}
        <Button type="button" variant="outline" size="sm" className="h-7 rounded-full" onClick={voice.connect}>
          <MicIcon /> Talk
        </Button>
      </div>
    )
  }

  return (
    <div className="flex items-center gap-1.5">
      <span className="relative flex size-3">
        <span
          className={cn(
            'absolute inline-flex size-full rounded-full opacity-75',
            voice.status === 'speaking' && 'animate-ping bg-emerald-400',
            voice.status === 'listening' && !voice.muted && 'animate-ping bg-sky-400',
            voice.status === 'thinking' && 'animate-pulse bg-amber-400',
          )}
        />
        <span
          className={cn(
            'relative inline-flex size-3 rounded-full',
            voice.status === 'speaking' ? 'bg-emerald-500' : voice.status === 'thinking' ? 'bg-amber-500' : 'bg-sky-500',
          )}
        />
      </span>
      <span className="text-muted-foreground w-20 text-xs">{voice.muted ? 'Muted' : LABEL[voice.status]}</span>
      <Button type="button" variant="ghost" size="icon" className="size-7 rounded-full" onClick={voice.toggleMute} aria-label={voice.muted ? 'Unmute' : 'Mute'}>
        {voice.muted ? <MicOffIcon /> : <MicIcon />}
      </Button>
      <Button type="button" variant="destructive" size="icon" className="size-7 rounded-full" onClick={voice.disconnect} aria-label="End call">
        <PhoneOffIcon />
      </Button>
    </div>
  )
}
