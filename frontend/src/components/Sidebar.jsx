export function Sidebar({ tripCount = 0 }) {
  return (
    <aside className="relative w-full shrink-0 md:w-80">
      <div className="flex h-full flex-col gap-8 py-20 px-8">
        <div>
          <h1 className="font-display mb-2 text-3xl font-semibold tracking-wide">
            travelnote.ai
          </h1>
          <p className="mt-1 font-body tracking-wide text-xs">
            Your trips, planned and pinned.
          </p>
        </div>

        <nav className="flex flex-col gap-3">
          <button
            type="button"
            className="nav-btn nav-btn-primary"
            aria-label="Plan a trip with AI"
          >
            Plan a trip with AI
          </button>
          <button
            type="button"
            aria-current="page"
            className="nav-btn nav-btn-active"
            aria-label="View my trips"
          >
            <span className="h-1.5 w-1.5 rounded-full bg-[#3C6E63]" aria-hidden="true" />
            My trips
          </button>
        </nav>

        <p className="mt-auto font-body text-xs text-[#6B6553]">
          {tripCount} trips on the board
        </p>
      </div>

      <div
        className="sidebar-perforation pointer-events-none absolute inset-y-0 right-0 hidden w-2 md:block"
        aria-hidden="true"
      />
    </aside>
  )
}
