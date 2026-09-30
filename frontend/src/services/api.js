const API_BASE = '/api'

export async function fetchUserTrips(userId = 'anonymous') {
    const res = await fetch(`${API_BASE}/users/${userId}/trips`)
    if (!res.ok) throw new Error('Failed to fetch trips')
    return res.json()
}

export async function sendChatMessage({ message, threadId = null, tripId = null, userId = 'anonymous' }) {
    const res = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            message,
            thread_id: threadId,
            trip_id: tripId,
            user_id: userId,
        }),
    })
    if (!res.ok) throw new Error('Failed to send message')
    return res.json()
}


export async function fetchTripResume(tripId) {
    const res = await fetch(`${API_BASE}/trips/${tripId}/resume`)
    if (!res.ok) throw new Error('Failed to resume trip')
    return res.json()
}

export async function syncTripFromConversation(tripId) {
    const res = await fetch(`${API_BASE}/trips/${tripId}?sync_from_conversation=true`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
    })
    if (!res.ok) throw new Error('Failed to sync trip')
    return res.json()
}

