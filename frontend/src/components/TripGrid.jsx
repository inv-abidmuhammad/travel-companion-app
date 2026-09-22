import { TripCard } from './TripCard'

export function TripGrid({ trips = [] }) {
  return (
    <main className="flex-1 p-6 md:p-20">
      <section className="grid grid-cols-1 gap-20 sm:grid-cols-2 xl:grid-cols-3">
        {trips.map((trip, index) => (
          <TripCard key={`${trip.destination}-${index}`} trip={trip} index={index} />
        ))}
      </section>
    </main>
  )
}
