export function Sidebar({ onPlanTrip, onViewTrips, tripCount }) {
  return (
    <aside className="relative w-full shrink-0 md:w-100">
      <div className="flex h-full flex-col items-center gap-8 py-20 px-16">
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
            onClick={onPlanTrip}
            className="nav-btn w-60 nav-btn-primary cursor-pointer"
            aria-label="Plan a trip with AI"
          >
            Plan a trip
          </button>
          <button
            type="button"
            onClick={onViewTrips}
            aria-current="page"
            className="nav-btn w-60 nav-btn-active cursor-pointer"
            aria-label="View my trips"
          >
            <span className="h-1.5 w-1.5 rounded-full bg-[#3C6E63]" aria-hidden="true" />
            My trips
          </button>
        </nav>

        {tripCount != null && (
          <p className="mt-auto font-body text-xs text-gray-400">
            {tripCount} {tripCount === 1 ? 'trip' : 'trips'} on the board
          </p>
        )}
      </div>
    </aside>
  )
}

