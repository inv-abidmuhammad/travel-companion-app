import { useState, useEffect, useRef } from 'react'
import {
  sendChatMessage,
  fetchTripResume,
  syncTripFromConversation,
} from '../services/api'

export function ChatModal({ isOpen, onClose, selectedTrip, onTripUpdated }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [threadId, setThreadId] = useState(null)
  const [tripId, setTripId] = useState(null)
  const [tripMeta, setTripMeta] = useState(null)
  const [awaitingConfirmation, setAwaitingConfirmation] = useState(false)
  const messagesEndRef = useRef(null)

  useEffect(() => {
    if (!isOpen) return

    if (selectedTrip) {
      setTripId(selectedTrip.trip_id)
      setThreadId(selectedTrip.thread_id)
      setTripMeta(selectedTrip)
      setLoading(true)

      fetchTripResume(selectedTrip.trip_id)
        .then((resumeData) => {
          if (resumeData) {
            setTripMeta((prev) => ({ ...prev, ...resumeData }))
            if (resumeData.thread_id) setThreadId(resumeData.thread_id)

            if (resumeData.messages?.length > 0) {
              const visible = resumeData.messages
                .filter((m) => m.role !== 'internal')
                .map((m) => ({
                  role: m.role === 'user' || m.type === 'human' ? 'user' : 'assistant',
                  content: typeof m.content === 'string' ? m.content : (m.text || ''),
                }))
                .filter((m) => m.content.trim().length > 0)

              if (visible.length > 0) {
                setMessages(visible)
                return
              }
            }
          }

          setMessages([
            {
              role: 'assistant',
              content: `Resuming trip to ${selectedTrip.destination || 'your destination'}. What would you like to update or plan next?`,
            },
          ])
        })
        .catch(() => {
          setMessages([
            {
              role: 'assistant',
              content: `Resuming trip to ${selectedTrip.destination || 'your destination'}. What would you like to update?`,
            },
          ])
        })
        .finally(() => setLoading(false))
    } else {
      setTripId(null)
      setThreadId(null)
      setTripMeta(null)
      setMessages([
        {
          role: 'assistant',
          content:
            'Where would you like to go next? Share your dream destination, budget, or travel dates to begin planning!',
        },
      ])
    }
  }, [isOpen, selectedTrip])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  if (!isOpen) return null

  const handleClose = async () => {
    if (tripId) {
      try {
        await syncTripFromConversation(tripId)
      } catch (err) {
        // sync failure shouldn't prevent closing
      }
    }
    onTripUpdated?.()
    onClose()
  }

  const handleSend = async (e) => {
    e?.preventDefault()
    const trimmed = input.trim()
    if (!trimmed || loading) return

    const userMsg = { role: 'user', content: trimmed }
    setMessages((prev) => [...prev, userMsg])
    setInput('')
    setLoading(true)

    try {
      const res = await sendChatMessage({
        message: trimmed,
        threadId,
        tripId,
        userId: 'anonymous',
      })

      const activeTripId = res.trip_id || tripId
      if (res.thread_id) setThreadId(res.thread_id)
      if (res.trip_id) setTripId(res.trip_id)
      setAwaitingConfirmation(Boolean(res.awaiting_confirmation))

      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: res.reply },
      ])

      if (activeTripId) {
        syncTripFromConversation(activeTripId)
          .then((updatedTrip) => {
            if (updatedTrip) setTripMeta(updatedTrip)
            onTripUpdated?.()
          })
          .catch(() => {})
      }
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content:
            'Sorry, I had trouble reaching the planner service. Please ensure the backend is running.',
        },
      ])
    } finally {
      setLoading(false)
    }
  }

  const destinationName =
    tripMeta?.destination || selectedTrip?.destination || 'Destination'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
      <div className="flex h-[85vh] w-full max-w-2xl flex-col rounded-3xl bg-white shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-gray-100 px-6 py-4">
          <div>
            <h3 className="font-display text-xl font-medium text-[#1E2A44]">
              {selectedTrip || tripMeta ? `Trip to ${destinationName}` : 'AI Trip Planner'}
            </h3>
            <p className="font-body text-xs text-gray-500">
              {awaitingConfirmation
                ? 'Waiting for your confirmation...'
                : tripMeta?.budget
                ? `Budget: ₹${Number(tripMeta.budget).toLocaleString('en-IN')} · ${tripMeta.duration_days ? `${tripMeta.duration_days} days` : ''}`
                : 'Powered by LangGraph'}
            </p>
          </div>
          <button
            type="button"
            onClick={handleClose}
            className="flex h-9 w-9 items-center justify-center rounded-full text-gray-400 hover:bg-gray-100 hover:text-gray-700 cursor-pointer"
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        {/* Message history */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {messages.map((m, idx) => (
            <div
              key={idx}
              className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[80%] rounded-2xl px-4 py-3 font-body text-sm leading-relaxed whitespace-pre-wrap ${
                  m.role === 'user'
                    ? 'bg-[#1E2A44] text-white'
                    : 'bg-gray-100 text-gray-800'
                }`}
              >
                {m.content}
              </div>
            </div>
          ))}

          {loading && (
            <div className="flex justify-start">
              <div className="max-w-[80%] rounded-2xl bg-gray-100 px-4 py-3 font-body text-sm text-gray-500 animate-pulse">
                Thinking and updating itinerary...
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <form onSubmit={handleSend} className="border-t border-gray-100 p-4 flex gap-3">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={
              awaitingConfirmation
                ? 'Type yes / no / your response...'
                : 'e.g. Plan a 4-day trip to Kyoto with ₹50,000 budget'
            }
            className="flex-1 rounded-2xl bg-gray-100 px-4 py-3 font-body text-sm text-gray-800 outline-none focus:ring-2 focus:ring-[#C89A3C]"
            disabled={loading}
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="rounded-2xl bg-[#C89A3C] px-6 py-3 font-body text-sm font-semibold text-white transition hover:bg-[#B78B33] disabled:opacity-50 cursor-pointer"
          >
            Send
          </button>
        </form>
      </div>
    </div>
  )
}
