import React, { useState, useContext, createContext, useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate, useNavigate } from 'react-router-dom'

// Pages
import Dashboard from './pages/Dashboard'
import UploadPage from './pages/UploadPage'
import BookingsPage from './pages/BookingsPage'
import BookingDetailPage from './pages/BookingDetailPage'
import DriversPage from './pages/DriversPage'
import AssignmentPage from './pages/AssignmentPage'
import MessagesPage from './pages/MessagesPage'
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
  const [loading, setLoading] = useState(false)
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

  const login = async (email, password) => {
    setLoading(true)
    try {
      const apiUrl = import.meta.env.VITE_API_URL || '/api/v1'
      const response = await fetch(`${apiUrl}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
      })
      const data = await response.json()
      
      if (data.success) {
        setToken(data.token)
        setUser(data.user)
        return data
      } else {
        throw new Error(data.message)
      }
    } finally {
      setLoading(false)
    }
  }

  const logout = () => {
    setToken(null)
    setUser(null)
  }

  const value = { user, token, loading, bootstrapping, login, logout, isAuthenticated: !!token }

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  )
}

// Pages
const LoginPage = () => {
  const { login, loading, isAuthenticated, bootstrapping } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('admin@dispatch.local')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')

  if (bootstrapping) {
    return <div className="login-container"><p style={{ color: '#fff' }}>Opening dispatch…</p></div>
  }
  if (isAuthenticated) {
    return <Navigate to="/dashboard" />
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    try {
      await login(email, password)
      navigate('/dashboard')
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div className="login-container">
      <h1>Dispatch Management System</h1>
      <form onSubmit={handleSubmit}>
        <input
          type="email"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        {error && <p className="error">{error}</p>}
        <button type="submit" disabled={loading}>
          {loading ? 'Logging in...' : 'Login'}
        </button>
      </form>
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
          <Route path="/bookings" element={<ProtectedRoute><BookingsPage /></ProtectedRoute>} />
          <Route path="/bookings/:bookingId" element={<ProtectedRoute><BookingDetailPage /></ProtectedRoute>} />
          <Route path="/drivers" element={<ProtectedRoute><DriversPage /></ProtectedRoute>} />
          <Route path="/assignment" element={<ProtectedRoute><AssignmentPage /></ProtectedRoute>} />
          <Route path="/messages" element={<ProtectedRoute><MessagesPage /></ProtectedRoute>} />
          <Route path="/whatsapp-qr" element={<ProtectedRoute><WhatsAppSettings /></ProtectedRoute>} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}

export default App
