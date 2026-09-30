const STATUS_STYLES = {
  draft: { label: 'Draft', ink: '#6E6A5C' },
  planned: { label: 'Planned', ink: '#3C6E63' },
  cancelled: { label: 'Cancelled', ink: '#9C4A35' },
  completed: { label: 'Completed', ink: '#B78B33' },
}

const ROTATIONS = ['-1.4deg', '0.9deg', '-0.6deg', '1.2deg']

export function TripCard({ trip, index = 0, onSelect }) {
  const status = STATUS_STYLES[trip.status] ?? STATUS_STYLES.draft
  const rotation = ROTATIONS[index % ROTATIONS.length]
  const budget =
    trip.budget != null
      ? Number(trip.budget).toLocaleString('en-IN')
      : '--'
  const duration =
    trip.duration_days != null ? `${trip.duration_days} days` : 'TBD'
  const description =
    trip.description || trip.itinerary_text || 'No itinerary details generated yet.'

  return (
    <article
      className="trip-card cursor-pointer"
      tabIndex={0}
      onClick={() => onSelect?.(trip)}
      onKeyDown={(e) => e.key === 'Enter' && onSelect?.(trip)}
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
        {trip.origin ? `Departing from ${trip.origin}` : 'Origin TBD'}
      </p>
      <h3 className="my-5 font-display text-5xl font-medium">
        {trip.destination || 'New Trip'}
      </h3>
      <p className="mt-3 line-clamp-2 font-display text-[15px] italic leading-snug text-[#5B5648]">
        {description}
      </p>

      <div className="mt-6 flex items-center gap-6 border-t border-dashed border-[#D8CBA6] pt-4">
        <div>
          <p className="trip-stat-label">Budget</p>
          <p className="trip-stat-value">₹{budget}</p>
        </div>
        <div>
          <p className="trip-stat-label">Duration</p>
          <p className="trip-stat-value">{duration}</p>
        </div>
      </div>
    </article>
  )
}