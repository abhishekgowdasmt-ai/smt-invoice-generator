import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import Navigation from '../components/Navigation'
import { useAuth } from '../App'
import { API } from '../services/api'
import { QRCodeSVG } from 'qrcode.react'

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
        
        {waStatus && waStatus.provider === 'wwebjs' && !waStatus.isReady && (
          <div className="card" style={{ marginBottom: '20px', backgroundColor: '#fff3cd', color: '#856404', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <h3>📱 WhatsApp Authentication Required</h3>
              <p>Driver notifications are currently paused. Please link your device to resume.</p>
            </div>
            <Link to="/whatsapp-qr" className="btn-primary">Go to QR Code</Link>
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
