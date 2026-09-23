import { useState, useEffect, useCallback } from 'react'
import { Sidebar } from './components/Sidebar'
import { TripGrid } from './components/TripGrid'
import { ChatModal } from './components/ChatModal'
import { fetchUserTrips } from './services/api'
import { trips as fallbackTrips } from './data/trips'

function App() {
  const [trips, setTrips] = useState([])
  const [loading, setLoading] = useState(true)
  const [chatOpen, setChatOpen] = useState(false)
  const [selectedTrip, setSelectedTrip] = useState(null)

  const loadTrips = useCallback(() => {
    setLoading(true)
    fetchUserTrips('anonymous')
      .then((data) => setTrips(data.length > 0 ? data : fallbackTrips))
      .catch((err) => {
        console.error('Backend unreachable, using fallback data:', err)
        setTrips(fallbackTrips)
      })
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    loadTrips()
  }, [loadTrips])

  const handlePlanTrip = () => {
    setSelectedTrip(null)
    setChatOpen(true)
  }

  const handleSelectTrip = (trip) => {
    setSelectedTrip(trip)
    setChatOpen(true)
  }

  return (
    <div className="flex min-h-screen flex-col md:flex-row">
      <Sidebar
        onPlanTrip={handlePlanTrip}
        onViewTrips={loadTrips}
        tripCount={trips.length}
      />
      <TripGrid
        trips={trips}
        loading={loading}
        onSelectTrip={handleSelectTrip}
      />
      <ChatModal
        isOpen={chatOpen}
        onClose={() => {
          setChatOpen(false)
          setSelectedTrip(null)
          loadTrips()
        }}
        selectedTrip={selectedTrip}
        onTripUpdated={loadTrips}
      />
    </div>
  )
}

export default App
