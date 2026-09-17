const API_URL = import.meta.env.VITE_API_URL || '/api/v1'

const getHeaders = () => {
  const token = localStorage.getItem('token')
  return {
    'Content-Type': 'application/json',
    ...(token && { 'Authorization': `Bearer ${token}` })
  }
}

export const apiCall = async (endpoint, options = {}) => {
  const url = `${API_URL}${endpoint}`
  const response = await fetch(url, {
    credentials: 'same-origin',
    ...options,
    headers: { ...getHeaders(), ...options.headers }
  })

  const contentType = response.headers.get('content-type') || ''
  const isJson = contentType.includes('application/json')
  if (!isJson) {
    throw new Error(response.ok ? 'Server returned a page instead of data. Refresh and try again.' : `Request failed (${response.status})`)
  }

  const data = await response.json()
  if (!response.ok) {
    throw new Error(data.message || `HTTP ${response.status}`)
  }
  return data
}

export const API = {
  // Drivers
  createDriver: (data) => apiCall('/drivers', { method: 'POST', body: JSON.stringify(data) }),
  getDrivers: (params) => apiCall(`/drivers?${new URLSearchParams(params)}`),
  getDriver: (id) => apiCall(`/drivers/${id}`),
  updateDriver: (id, data) => apiCall(`/drivers/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  updateDriverStatus: (id, data) => apiCall(`/drivers/${id}/status`, { method: 'PATCH', body: JSON.stringify(data) }),

  // Bookings
  getBookings: (params) => apiCall(`/bookings?${new URLSearchParams(params)}`),
  getBooking: (id) => apiCall(`/bookings/${id}`),
  updateBookingStatus: (id, status) => apiCall(`/bookings/${id}/status`, { method: 'PATCH', body: JSON.stringify({ status }) }),
  updateBookingPayment: (id, data) => apiCall(`/bookings/${id}/payment`, { method: 'PATCH', body: JSON.stringify(data) }),
  updateBookingsPaymentBulk: (data) => apiCall('/bookings/payments/bulk', { method: 'PATCH', body: JSON.stringify(data) }),

  // Upload
  uploadExcel: (file) => {
    const formData = new FormData()
    formData.append('file', file)
    const token = localStorage.getItem('token')
    
    return fetch(`${API_URL}/uploads/excel`, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        ...(token ? { 'Authorization': `Bearer ${token}` } : {})
      },
      body: formData
    }).then(async (res) => {
      const contentType = res.headers.get('content-type')
      const isJson = contentType && contentType.includes('application/json')
      
      if (!res.ok) {
        let error = 'Upload failed'
        try {
          if (isJson) {
            const data = await res.json()
            error = data.message || error
          } else {
            const text = await res.text()
            error = text || error
          }
        } catch (e) {
          // If we can't parse the error response, use default
        }
        throw new Error(error)
      }

      if (!isJson) {
        throw new Error('Invalid response format from server')
      }
      return res.json()
    })
  },
  getUploadStatus: (batchId) => apiCall(`/uploads/${batchId}/status`),
  getUploadHistory: (params) => apiCall(`/uploads/history?${new URLSearchParams(params)}`),

  // Assignments
  createAssignment: (data) => apiCall('/assignments', { method: 'POST', body: JSON.stringify(data) }),
  getAssignment: (id) => apiCall(`/assignments/${id}`),
  resendMessage: (id) => apiCall(`/assignments/${id}/resend-message`, { method: 'POST' }),

  // Messages
  getMessages: (params) => apiCall(`/messages?${new URLSearchParams(params)}`),
  getMessage: (id) => apiCall(`/messages/${id}`),

  // Dashboard
  getDashboardSummary: () => apiCall('/dashboard/summary'),
  getInsights: () => apiCall('/dashboard/insights'),

  // WhatsApp
  getWhatsappStatus: () => apiCall('/whatsapp/status')
}
