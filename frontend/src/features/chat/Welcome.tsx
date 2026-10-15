/** Empty-thread message: what this app does, in two lines. */
export function Welcome() {
  return (
    <div className="mb-6 flex flex-col gap-2 px-2">
      <p className="text-2xl font-medium tracking-tight">Which apartment should you pick?</p>
      <p className="text-muted-foreground">
        Drop the brochures, floor plans and price sheets your broker sent. I&apos;ll read them, show you where every
        fact comes from, and help you decide — by text or by voice.
      </p>
    </div>
  )
}
