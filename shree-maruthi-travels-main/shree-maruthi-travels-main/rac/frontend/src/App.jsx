import React, { useState, useContext, createContext, useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'

// Pages
import Dashboard from './pages/Dashboard'
import UploadPage from './pages/UploadPage'
import BookingOcrPage from './pages/BookingOcrPage'
import BookingsPage from './pages/BookingsPage'
import BookingDetailPage from './pages/BookingDetailPage'
import DriversPage from './pages/DriversPage'
import AssignmentPage from './pages/AssignmentPage'
import MessagesPage from './pages/MessagesPage'
import InsightsPage from './pages/InsightsPage'
import WhatsAppSettings from './pages/WhatsAppSettings'

// Auth Context
const AuthContext = createContext()

export const useAuth = () => {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return context
}

// Auth Provider
export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null)
  const [token, setToken] = useState(localStorage.getItem('token'))
  const [bootstrapping, setBootstrapping] = useState(!localStorage.getItem('token'))

  useEffect(() => {
    if (token) {
      localStorage.setItem('token', token)
      setBootstrapping(false)
      return
    }
    localStorage.removeItem('token')
    let cancelled = false
    const apiUrl = import.meta.env.VITE_API_URL || '/api/v1'
    fetch(`${apiUrl}/auth/staff`, { credentials: 'same-origin' })
      .then((res) => res.json())
      .then((data) => {
        if (!cancelled && data.success && data.token) {
          localStorage.setItem('token', data.token)
          setToken(data.token)
          setUser(data.user)
        }
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setBootstrapping(false)
      })
    return () => { cancelled = true }
  }, [token])

  const logout = async () => {
    localStorage.removeItem('token')
    setToken(null)
    setUser(null)
    try {
      await fetch('/api/admin/logout', {
        method: 'POST',
        credentials: 'same-origin',
      })
    } catch {
      // The browser token is already gone. Cookie clearing is retried by leaving the page.
    }
  }

  const value = { user, token, bootstrapping, logout, isAuthenticated: !!token }

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  )
}

// Pages
const LoginPage = () => {
  const { isAuthenticated, bootstrapping } = useAuth()

  if (bootstrapping) {
    return <div className="login-container"><p style={{ color: '#fff' }}>Opening dispatch…</p></div>
  }
  if (isAuthenticated) {
    return <Navigate to="/dashboard" />
  }

  return (
    <div className="login-container">
      <h1>Dispatch Management System</h1>
      <p style={{ color: '#fff' }}>Sign in with Google at /admin, then open dispatch again.</p>
    </div>
  )
}

// Protected Route
const ProtectedRoute = ({ children }) => {
  const { isAuthenticated, bootstrapping } = useAuth()
  if (bootstrapping) {
    return <div className="login-container"><p style={{ color: '#fff' }}>Opening dispatch…</p></div>
  }
  return isAuthenticated ? children : <Navigate to="/" />
}

function App() {
  return (
    <AuthProvider>
      <BrowserRouter basename="/admin/dispatch">
        <Routes>
          <Route path="/" element={<LoginPage />} />
          <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
          <Route path="/upload" element={<ProtectedRoute><UploadPage /></ProtectedRoute>} />
          <Route path="/booking-ocr" element={<ProtectedRoute><BookingOcrPage /></ProtectedRoute>} />
          <Route path="/bookings" element={<ProtectedRoute><BookingsPage /></ProtectedRoute>} />
          <Route path="/bookings/:bookingId" element={<ProtectedRoute><BookingDetailPage /></ProtectedRoute>} />
          <Route path="/drivers" element={<ProtectedRoute><DriversPage /></ProtectedRoute>} />
          <Route path="/assignment" element={<ProtectedRoute><AssignmentPage /></ProtectedRoute>} />
          <Route path="/messages" element={<ProtectedRoute><MessagesPage /></ProtectedRoute>} />
          <Route path="/insights" element={<ProtectedRoute><InsightsPage /></ProtectedRoute>} />
          <Route path="/whatsapp-qr" element={<ProtectedRoute><WhatsAppSettings /></ProtectedRoute>} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}

export default App
