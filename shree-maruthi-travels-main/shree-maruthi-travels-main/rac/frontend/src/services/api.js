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
    ...options,
    headers: { ...getHeaders(), ...options.headers }
  })

  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.message || `HTTP ${response.status}`)
  }

  return response.json()
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

  // Upload
  uploadExcel: (file) => {
    const formData = new FormData()
    formData.append('file', file)
    const token = localStorage.getItem('token')
    
    return fetch(`${API_URL}/uploads/excel`, {
      method: 'POST',
      headers: {
        // ONLY set Authorization, let browser auto-set Content-Type to multipart/form-data
        'Authorization': `Bearer ${token}`
        // IMPORTANT: Do NOT set Content-Type - browser will auto-set it for FormData
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

  // WhatsApp
  getWhatsappStatus: () => apiCall('/whatsapp/status')
}
