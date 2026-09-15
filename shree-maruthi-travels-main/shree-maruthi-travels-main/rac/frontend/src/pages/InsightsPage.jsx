import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import Navigation from '../components/Navigation'
import { API } from '../services/api'

const PALETTE = ['#667eea', '#2ecc71', '#f39c12', '#e74c3c', '#1abc9c', '#9b59b6', '#3498db', '#2c3e50']

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

const monthLabel = (value) => {
  const [year, month] = String(value || '').split('-')
  const name = MONTHS[Number(month) - 1]
  return name ? `${name} ${year}` : value
}

const HBars = ({ rows, color = '#667eea' }) => {
  const max = Math.max(...rows.map((row) => row.count), 1)
  return (
    <div className="insight-bars">
      {rows.map((row) => (
        <div className="insight-bar-row" key={row.name}>
          <span className="insight-bar-label" title={row.name}>{row.name}</span>
          <div className="insight-bar-track">
            <div
              className="insight-bar-fill"
              style={{ width: `${(row.count / max) * 100}%`, background: color }}
            />
          </div>
          <span className="insight-bar-value">{row.count}</span>
        </div>
      ))}
    </div>
  )
}

const MonthColumns = ({ rows }) => {
  const max = Math.max(...rows.map((row) => row.count), 1)
  return (
    <div className="insight-columns">
      {rows.map((row, index) => (
        <Link to={`/bookings?month=${row.month}`} className="insight-col" key={row.month}>
          <span className="insight-col-value">{row.count}</span>
          <div className="insight-col-track">
            <div
              className="insight-col-fill"
              style={{ height: `${(row.count / max) * 100}%`, background: PALETTE[index % PALETTE.length] }}
            />
          </div>
          <span className="insight-col-label">{monthLabel(row.month)}</span>
        </Link>
      ))}
    </div>
  )
}

const Donut = ({ rows }) => {
  const total = rows.reduce((sum, row) => sum + row.count, 0) || 1
  const radius = 54
  const circumference = 2 * Math.PI * radius
  let offset = 0
  return (
    <div className="insight-donut-wrap">
      <svg viewBox="0 0 140 140" className="insight-donut" aria-hidden="true">
        <g transform="rotate(-90 70 70)">
          {rows.map((row, index) => {
            const length = (row.count / total) * circumference
            const circle = (
              <circle
                key={row.name}
                cx="70"
                cy="70"
                r={radius}
                fill="none"
                stroke={PALETTE[index % PALETTE.length]}
                strokeWidth="18"
                strokeDasharray={`${length} ${circumference - length}`}
                strokeDashoffset={-offset}
              />
            )
            offset += length
            return circle
          })}
        </g>
        <text x="70" y="66" textAnchor="middle" className="insight-donut-total">{total}</text>
        <text x="70" y="84" textAnchor="middle" className="insight-donut-caption">trips</text>
      </svg>
      <ul className="insight-legend">
        {rows.map((row, index) => (
          <li key={row.name}>
            <span className="insight-swatch" style={{ background: PALETTE[index % PALETTE.length] }} />
            {row.name}
            <strong>{row.count}</strong>
          </li>
        ))}
      </ul>
    </div>
  )
}

const Panel = ({ title, chart, rows, linkMonth }) => (
  <div className="card insight-panel">
    <h3>{title}</h3>
    <div className="insight-split">
      <div className="insight-chart">{chart}</div>
      <table className="table table-compact">
        <tbody>
          {rows.map((row) => (
            <tr key={row.name || row.month}>
              <td>
                {linkMonth ? (
                  <Link to={`/bookings?month=${row.month}`}>{monthLabel(row.month)}</Link>
                ) : (
                  row.name
                )}
              </td>
              <td className="fw-600">{row.count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  </div>
)

const InsightsPage = () => {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    API.getInsights()
      .then((res) => setData(res.data))
      .catch((err) => setError(err.message))
  }, [])

  if (error) {
    return <div><Navigation /><div className="container"><p className="error">{error}</p></div></div>
  }
  if (!data) {
    return <div><Navigation /><div className="container"><p className="loading">Loading history…</p></div></div>
  }

  const months = data.by_month || []
  const cabs = data.by_cab || []
  const drivers = data.top_drivers || []
  const areas = data.top_areas || []

  return (
    <div>
      <Navigation />
      <div className="container">
        <div className="page-header" style={{ display: 'block' }}>
          <h1>Duty insights</h1>
          <p className="card-subtitle" style={{ marginTop: '8px' }}>May–August 2026 history plus every booking uploaded after that.</p>
        </div>
        <div className="kpi-cards">
          <div className="card">
            <span className="card-label">All trips</span>
            <h2>{data.total_trips}</h2>
          </div>
          <div className="card">
            <span className="card-label">Total km</span>
            <h2>{data.total_km}</h2>
          </div>
          <div className="card">
            <span className="card-label">Drivers</span>
            <h2>{data.unique_drivers}</h2>
          </div>
          <div className="card">
            <span className="card-label">Employees</span>
            <h2>{data.unique_employees}</h2>
          </div>
        </div>
        <div className="insight-grid">
          <Panel
            title="By month"
            linkMonth
            rows={months}
            chart={months.length ? <MonthColumns rows={months} /> : <p className="card-subtitle">No month data</p>}
          />
          <Panel
            title="Cab type"
            rows={cabs}
            chart={cabs.length ? <Donut rows={cabs} /> : <p className="card-subtitle">No cab data</p>}
          />
          <Panel
            title="Top drivers"
            rows={drivers}
            chart={drivers.length ? <HBars rows={drivers} color="#667eea" /> : <p className="card-subtitle">No driver data</p>}
          />
          <Panel
            title="Top pickup areas"
            rows={areas}
            chart={areas.length ? <HBars rows={areas} color="#1abc9c" /> : <p className="card-subtitle">No area data</p>}
          />
        </div>
      </div>
    </div>
  )
}

export default InsightsPage
