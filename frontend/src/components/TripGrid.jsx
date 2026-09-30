import { TripCard } from './TripCard'

export function TripGrid({ trips = [], loading = false, onSelectTrip }) {
  if (loading) {
    return (
      <main className="rounded-l-4xl bg-gray-100 flex-1 p-10 md:px-20 md:py-22 h-screen overflow-auto scrollbar-none">
        <section className="grid grid-cols-1 gap-20 sm:grid-cols-2 xl:grid-cols-3">
          {[1, 2, 3].map((n) => (
            <div
              key={n}
              className="h-80 rounded-3xl bg-white/70 animate-pulse p-6 flex flex-col justify-between"
            >
              <div className="space-y-4">
                <div className="h-4 w-24 bg-gray-200 rounded" />
                <div className="h-12 w-48 bg-gray-200 rounded" />
                <div className="h-4 w-full bg-gray-200 rounded" />
              </div>
              <div className="h-8 w-full bg-gray-200 rounded" />
            </div>
          ))}
        </section>
      </main>
    )
  }

  if (trips.length === 0) {
    return (
      <main className="rounded-l-4xl bg-gray-100 flex-1 p-10 md:px-20 md:py-22 h-screen overflow-auto flex items-center justify-center">
        <div className="text-center max-w-sm">
          <p className="font-display text-2xl text-gray-700">No trips pinned yet</p>
          <p className="font-body text-sm text-gray-500 mt-2">
            Click &ldquo;Plan a trip&rdquo; to start a conversation with the AI travel companion.
          </p>
        </div>
      </main>
    )
  }

  return (
    <main className="rounded-l-4xl bg-gray-100 flex-1 p-10 md:px-20 md:py-22 h-screen overflow-auto scrollbar-none">
      <section className="grid grid-cols-1 gap-20 sm:grid-cols-2 xl:grid-cols-3">
        {trips.map((trip, index) => (
          <TripCard
            key={trip.trip_id || `${trip.destination}-${index}`}
            trip={trip}
            index={index}
            onSelect={onSelectTrip}
          />
        ))}
      </section>
    </main>
  )
}

