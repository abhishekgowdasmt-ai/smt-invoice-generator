import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import Navigation from '../components/Navigation'
import { useAuth } from '../App'
import { API } from '../services/api'

const Dashboard = () => {
  const [summary, setSummary] = useState(null)
  const [waStatus, setWaStatus] = useState(null)
  const { token } = useAuth()

  useEffect(() => {
    API.getDashboardSummary()
      .then(data => setSummary(data.data))
      .catch(err => console.error(err))

    API.getWhatsappStatus()
      .then(data => setWaStatus(data))
      .catch(err => console.error(err))
  }, [token])

  return (
    <div>
      <Navigation />
      <div className="container">
        <h1>Dashboard</h1>
        
        {waStatus && !waStatus.isReady && (
          <div className="card" style={{ marginBottom: '20px', backgroundColor: '#fff3cd', color: '#856404', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '16px' }}>
            <div>
              <h3>Link WhatsApp</h3>
              <p>Scan the login QR so trip messages send from your WhatsApp. You do not need a booking for this.</p>
            </div>
            <Link to="/whatsapp-qr" className="btn-primary">Scan QR</Link>
          </div>
        )}
        {waStatus && waStatus.isReady && (
          <div className="card" style={{ marginBottom: '20px', backgroundColor: '#d4edda', color: '#155724' }}>
            <h3>WhatsApp connected</h3>
            <p>Assignments will send from your linked account.</p>
          </div>
        )}

        {summary ? (
          <div className="kpi-cards">
            <div className="card">
              <span className="card-label">📤 Upload Today</span>
              <h2>{summary.total_uploaded_today}</h2>
              <p className="card-subtitle">New bookings</p>
            </div>
            <div className="card">
              <span className="card-label">⏳ Unassigned</span>
              <h2>{summary.unassigned_rides}</h2>
              <p className="card-subtitle">Awaiting assignment</p>
            </div>
            <div className="card">
              <span className="card-label">✅ Assigned</span>
              <h2>{summary.assigned_rides}</h2>
              <p className="card-subtitle">Driver assigned</p>
            </div>
            <div className="card" style={{ backgroundColor: '#2c3e50', color: 'white' }}>
              <span className="card-label" style={{ color: 'rgba(255,255,255,0.7)' }}>✅ Completed</span>
              <h2>{summary.completed_rides || 0}</h2>
              <p className="card-subtitle" style={{ color: 'rgba(255,255,255,0.7)' }}>Total success</p>
            </div>
            <div className="card">
              <span className="card-label">💬 Message Sent</span>
              <h2>{summary.message_sent_count}</h2>
              <p className="card-subtitle">WhatsApp notifications</p>
            </div>
            <div className="card">
              <span className="card-label" style={{ color: '#e74c3c' }}>🚫 Cancelled</span>
              <h2>{summary.cancelled_rides || 0}</h2>
              <p className="card-subtitle">Rejected/Cancelled</p>
            </div>
            <Link to="/bookings?payment=Unpaid" className="card" style={{ textDecoration: 'none', color: 'inherit' }}>
              <span className="card-label">💸 Driver unpaid</span>
              <h2>{summary.unpaid_driver_payments || 0}</h2>
              <p className="card-subtitle">Assigned/completed, not paid</p>
            </Link>
          </div>
        ) : (
          <p className="loading">Loading statistics...</p>
        )}

        <div className="dashboard-actions">
          <h2>Quick Actions</h2>
          <div className="action-buttons">
            <Link to="/upload" className="btn-primary">📤 Upload Excel</Link>
            <Link to="/bookings" className="btn-primary">📋 View Bookings</Link>
            <Link to="/assignment" className="btn-primary">🎯 Assign Drivers</Link>
            <Link to="/drivers" className="btn-primary">👥 Manage Drivers</Link>
            <Link to="/messages" className="btn-primary">💬 Message Log</Link>
          </div>
        </div>
      </div>
    </div>
  )
}

export default Dashboard
