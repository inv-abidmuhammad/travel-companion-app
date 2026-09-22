import { Sidebar } from './components/Sidebar'
import { TripGrid } from './components/TripGrid'
import { trips } from './data/trips'

function App() {
  return (
    <div className="flex min-h-screen flex-col md:flex-row">
      <Sidebar tripCount={trips.length} />
      <TripGrid trips={trips} />
    </div>
  )
}

export default App