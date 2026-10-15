import { createContext } from 'react'

import type { useLiveSession } from './useLiveSession'

/** The voice session lives in App; the composer (deep inside the thread) reads it from here. */
export const VoiceContext = createContext<ReturnType<typeof useLiveSession> | null>(null)
