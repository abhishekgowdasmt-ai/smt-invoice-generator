import React, { useMemo, useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import Navigation from '../components/Navigation'
import { useAuth } from '../App'
import { API } from '../services/api'

const Spark = ({ values, color }) => {
  const points = values.length ? values : [0, 0]
  const max = Math.max(...points, 1)
  const w = 88
  const h = 36
  const step = points.length > 1 ? w / (points.length - 1) : w
  const d = points.map((value, index) => `${index ? 'L' : 'M'}${index * step},${h - (value / max) * (h - 4) - 2}`).join(' ')
  return (
    <svg className="rac-spark" viewBox={`0 0 ${w} ${h}`} aria-hidden="true">
      <path d={d} fill="none" stroke={color} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  )
}

const ago = (value) => {
  const then = Date.parse(value)
  if (!then) return ''
  const mins = Math.max(1, Math.round((Date.now() - then) / 60000))
  if (mins < 60) return `${mins}m ago`
  const hours = Math.round(mins / 60)
  if (hours < 48) return `${hours}h ago`
  return `${Math.round(hours / 24)}d ago`
}

const Dashboard = () => {
  const [summary, setSummary] = useState(null)
  const [insights, setInsights] = useState(null)
  const [waStatus, setWaStatus] = useState(null)
  const [error, setError] = useState('')
  const { token } = useAuth()

  useEffect(() => {
    API.getDashboardSummary()
      .then((data) => setSummary(data.data))
      .catch((err) => setError(err.message))
    API.getInsights().then((res) => setInsights(res.data)).catch(() => {})
    API.getWhatsappStatus().then(setWaStatus).catch(() => {})
  }, [token])

  const spark = useMemo(
    () => (insights?.by_month || []).map((row) => row.count).slice(-8),
    [insights]
  )

  const kpis = summary ? [
    { label: 'Upload Today', value: summary.total_uploaded_today, note: 'New bookings', tone: 'blue', to: '/upload' },
    { label: 'Unassigned', value: summary.unassigned_rides, note: 'Awaiting assignment', tone: 'amber', to: '/assignment' },
    { label: 'Assigned', value: summary.assigned_rides, note: 'Driver assigned', tone: 'green', to: '/bookings' },
    { label: 'Completed', value: summary.completed_rides || 0, note: 'Total success', tone: 'navy', spark: true, to: '/bookings' },
    { label: 'Message Sent', value: summary.message_sent_count, note: 'WhatsApp notifications', tone: 'purple', to: '/messages' },
    { label: 'Cancelled', value: summary.cancelled_rides || 0, note: 'Rejected/Cancelled', tone: 'red', to: '/bookings' },
    { label: 'Driver unpaid', value: summary.unpaid_driver_payments || 0, note: 'Assigned/completed, not paid', tone: 'teal', to: '/bookings?payment=Unpaid' },
    { label: 'All history', value: summary.total_bookings || 0, note: 'Every stored trip', tone: 'slate', spark: true, to: '/bookings' },
  ] : []

  const actions = [
    { to: '/upload', title: 'Upload Excel', text: 'Add the duty Excel used for RAC bookings.', icon: 'up' },
    { to: '/bookings', title: 'View Bookings', text: 'Open the full duty list and filter by month.', icon: 'cal' },
    { to: '/assignment', title: 'Assign Drivers', text: 'Match unassigned trips to a driver.', icon: 'user' },
    { to: '/drivers', title: 'Manage Drivers', text: 'Roster, WhatsApp numbers, and vehicles.', icon: 'team' },
    { to: '/messages', title: 'Message Log', text: 'See what was sent after assignment.', icon: 'chat' },
    { to: '/insights', title: 'Insights', text: 'Trips, km, cab mix, and duty packages.', icon: 'chart' },
  ]

  return (
    <div className="rac-frame">
      <Navigation />
      <div className="container rac-page">
        <div className="rac-page-head">
          <div>
            <h1>Dashboard</h1>
            <p>Monitor assignments and WhatsApp activity at a glance.</p>
          </div>
          {waStatus && !waStatus.isReady && (
            <Link to="/whatsapp-qr" className="rac-wa-cta">Link WhatsApp</Link>
          )}
        </div>

        {error ? <p className="error">{error}</p> : null}

        {summary ? (
          <div className="rac-kpi-grid">
            {kpis.map((card) => (
              <Link to={card.to} className={`rac-kpi tone-${card.tone}`} key={card.label}>
                <div>
                  <span>{card.label}</span>
                  <strong>{Number(card.value).toLocaleString('en-IN')}</strong>
                  <small>{card.note}</small>
                </div>
                {card.spark ? <Spark values={spark} color={card.tone === 'navy' ? '#3b82f6' : '#8b5cf6'} /> : null}
              </Link>
            ))}
          </div>
        ) : (
          <p className="loading">Loading statistics...</p>
        )}

        <div className="rac-dash-split">
          <section className="rac-panel">
            <h2>Quick Actions</h2>
            <p className="rac-panel-sub">Perform common tasks quickly</p>
            <div className="rac-action-grid">
              {actions.map((item) => (
                <Link to={item.to} className="rac-action" key={item.to}>
                  <span className={`rac-action-ico ico-${item.icon}`} />
                  <strong>{item.title}</strong>
                  <small>{item.text}</small>
                </Link>
              ))}
            </div>
          </section>
          <section className="rac-panel">
            <div className="rac-panel-head">
              <h2>Recent Activity</h2>
              <Link to="/messages">View All ›</Link>
            </div>
            <ul className="rac-activity">
              {(summary?.recent_activity || []).length ? (summary.recent_activity.map((item, index) => (
                <li key={`${item.title}-${index}`}>
                  <span className={`rac-dot kind-${item.kind}`} />
                  <div>
                    <strong>{item.title}</strong>
                    <small>{item.detail}</small>
                  </div>
                  <em>{ago(item.at)}</em>
                </li>
              ))) : (
                <li className="rac-empty">No recent uploads, assignments, or messages yet.</li>
              )}
            </ul>
          </section>
        </div>
        <p className="rac-foot">SMT Portal · RAC Management</p>
      </div>
    </div>
  )
}

export default Dashboard
