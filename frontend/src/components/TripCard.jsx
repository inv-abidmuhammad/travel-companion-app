export function TripCard({ trip }) {
  return (
    <div className='flex flex-col justify-end bg-white shadow-md rounded-3xl aspect-3/4 hover:-translate-y-1 hover:shadow-lg hover:cursor-pointer transition-all duration-300'>
        <div>
          
        </div>
        
        <div className='px-5 py-8'>
            <p className="mb-3 text-2xl">{trip.origin} →</p>
            <h2 className='text-6xl font-bold mb-2'>{trip.destination}</h2>
            <p className="mt-5 text-xl">{trip.description}</p>
        </div>
    </div>
  )
}
