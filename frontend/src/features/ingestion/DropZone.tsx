import { useRef, useState, type DragEvent } from 'react'
import { FileStackIcon, SparklesIcon, UploadIcon } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

const ACCEPT = '.pdf,.png,.jpg,.jpeg,.webp'

type Props = {
  disabled: boolean
  onFiles: (files: File[]) => void
  onSample: () => void
}

/** Drop the broker's files here — or try the bundled sample documents. */
export function DropZone({ disabled, onFiles, onSample }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)

  const onDrop = (event: DragEvent) => {
    event.preventDefault()
    setDragging(false)
    if (!disabled && event.dataTransfer.files.length) onFiles([...event.dataTransfer.files])
  }

  return (
    <div className="flex flex-col gap-2">
      <button
        type="button"
        disabled={disabled}
        onClick={() => inputRef.current?.click()}
        onDragOver={(event) => {
          event.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={cn(
          'text-muted-foreground hover:border-foreground/30 flex flex-col items-center gap-2 rounded-xl border border-dashed px-4 py-6 text-center text-sm transition-colors disabled:opacity-50',
          dragging && 'border-primary bg-accent text-foreground',
        )}
      >
        {dragging ? <FileStackIcon className="size-6" /> : <UploadIcon className="size-6" />}
        <span>
          <span className="text-foreground font-medium">Drop the broker&apos;s documents</span>
          <br />
          PDF brochures, floor plans, photos
        </span>
      </button>
      <input
        ref={inputRef}
        type="file"
        multiple
        accept={ACCEPT}
        className="hidden"
        onChange={(event) => {
          if (event.target.files?.length) onFiles([...event.target.files])
          event.target.value = ''
        }}
      />
      <Button variant="outline" size="sm" disabled={disabled} onClick={onSample}>
        <SparklesIcon /> Try sample documents
      </Button>
    </div>
  )
}
