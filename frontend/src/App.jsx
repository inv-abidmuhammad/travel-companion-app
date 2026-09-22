import { TripCard } from './components/TripCard'

function App() {

  const trips = [
    { origin: 'Kochi', destination: 'Paris', budget: 5000, duration_days: 7, status: 'draft', description: 'A wonderful trip to the city of lights.' },
    { origin: 'Delhi', destination: 'New York', budget: 8000, duration_days: 10, status: 'planned', description: 'Exploring the Big Apple.' },
    { origin: 'Kochi', destination: 'Tokyo', budget: 10000, duration_days: 14, status: 'cancelled', description: 'Experience the vibrant culture of Japan.' },
    { origin: 'Kochi', destination: 'Sydney', budget: 12000, duration_days: 12, status: 'completed', description: 'Enjoy the beautiful beaches and landmarks.' },
  ]

  return (
    <>
      <aside className='max-w-md'>
        <h1 className='text-7xl font-bold mb-5'>unknown app</h1>
        <p className='text-gray-700'>
          Travel Companion is a web application that helps you plan and organize your trips. You can create, view, and manage your trips with ease. Explore new destinations and make the most of your travel experiences!
        </p>
      </aside>
      <main>
        <section className='grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-7'>
          {trips.map((trip, index) => (
            <TripCard key={index} trip={trip} />
          ))}
        </section>
      </main>
    </>
  )
}

export default App
