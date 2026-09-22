const STATUS_STYLES = {
  draft: { label: 'Draft', ink: '#6E6A5C' },
  planned: { label: 'Planned', ink: '#3C6E63' },
  cancelled: { label: 'Cancelled', ink: '#9C4A35' },
  completed: { label: 'Completed', ink: '#B78B33' },
}

const ROTATIONS = ['-1.4deg', '0.9deg', '-0.6deg', '1.2deg']

export function TripCard({ trip, index = 0 }) {
  const status = STATUS_STYLES[trip.status] ?? STATUS_STYLES.draft
  const rotation = ROTATIONS[index % ROTATIONS.length]
  const budget = Number(trip.budget).toLocaleString('en-IN')

  return (
    <article
      className="trip-card"
      tabIndex={0}
      style={{ '--card-rotation': rotation }}
    >
      <span className="trip-card-pin" aria-hidden="true" />

      <span
        className="trip-card-stamp"
        style={{ borderColor: status.ink, color: status.ink }}
      >
        {status.label}
      </span>

      <p className="font-body text-xs tracking-wide">
        Departing from {trip.origin}
      </p>
      <h3 className="my-5 font-display text-5xl font-medium">
        {trip.destination}
      </h3>
      <p className="mt-3 line-clamp-2 font-display text-[15px] italic leading-snug text-[#5B5648]">
        {trip.description}
      </p>

      <div className="mt-6 flex items-center gap-6 border-t border-dashed border-[#D8CBA6] pt-4">
        <div>
          <p className="trip-stat-label">Budget</p>
          <p className="trip-stat-value">₹{budget}</p>
        </div>
        <div>
          <p className="trip-stat-label">Duration</p>
          <p className="trip-stat-value">{trip.duration_days} days</p>
        </div>
      </div>
    </article>
  )
}