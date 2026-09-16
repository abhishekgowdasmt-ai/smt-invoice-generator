import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import Navigation from '../components/Navigation'
import { API } from '../services/api'

const PALETTE = ['#667eea', '#2ecc71', '#f39c12', '#e74c3c', '#1abc9c', '#9b59b6', '#3498db', '#2c3e50']
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

const monthLabel = (value) => {
  const [year, month] = String(value || '').split('-')
  const name = MONTHS[Number(month) - 1]
  return name ? `${name} ${String(year).slice(2)}` : value
}

const formatNumber = (value) => {
  const num = Number(value) || 0
  return num.toLocaleString('en-IN', { maximumFractionDigits: 0 })
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
          <span className="insight-bar-value">{formatNumber(row.count)}</span>
        </div>
      ))}
    </div>
  )
}

const MonthLine = ({ rows }) => {
  if (!rows.length) return <p className="card-subtitle">No month data</p>
  const width = 640
  const height = 240
  const pad = { top: 18, right: 18, bottom: 36, left: 46 }
  const innerW = width - pad.left - pad.right
  const innerH = height - pad.top - pad.bottom
  const maxTrips = Math.max(...rows.map((row) => row.count), 1)
  const maxKm = Math.max(...rows.map((row) => Number(row.km) || 0), 1)
  const last = Math.max(rows.length - 1, 1)
  const xAt = (index) => pad.left + (index / last) * innerW
  const yTrips = (count) => pad.top + innerH - (count / maxTrips) * innerH
  const yKm = (km) => pad.top + innerH - (km / maxKm) * innerH
  const tripPath = rows.map((row, index) => `${index ? 'L' : 'M'}${xAt(index)},${yTrips(row.count)}`).join(' ')
  const kmPath = rows.map((row, index) => `${index ? 'L' : 'M'}${xAt(index)},${yKm(Number(row.km) || 0)}`).join(' ')
  const areaPath = `${tripPath} L${xAt(rows.length - 1)},${pad.top + innerH} L${xAt(0)},${pad.top + innerH} Z`
  const labelEvery = rows.length > 10 ? 2 : 1

  return (
    <div className="insight-line-wrap">
      <svg viewBox={`0 0 ${width} ${height}`} className="insight-line" role="img" aria-label="Trips and kilometres by month">
        {[0, 0.25, 0.5, 0.75, 1].map((tick) => {
          const y = pad.top + innerH * (1 - tick)
          return (
            <g key={tick}>
              <line x1={pad.left} x2={width - pad.right} y1={y} y2={y} className="insight-gridline" />
              <text x={pad.left - 8} y={y + 4} textAnchor="end" className="insight-axis">{formatNumber(maxTrips * tick)}</text>
            </g>
          )
        })}
        <path d={areaPath} className="insight-line-fill" />
        <path d={kmPath} className="insight-line-km" fill="none" />
        <path d={tripPath} className="insight-line-path" fill="none" />
        {rows.map((row, index) => (
          <Link key={row.month} to={`/bookings?month=${row.month}`}>
            <circle cx={xAt(index)} cy={yTrips(row.count)} r="3.5" className="insight-line-dot">
              <title>{`${monthLabel(row.month)}: ${row.count} trips, ${formatNumber(row.km)} km`}</title>
            </circle>
          </Link>
        ))}
        {rows.map((row, index) => (
          index % labelEvery === 0 ? (
            <text key={row.month} x={xAt(index)} y={height - 10} textAnchor="middle" className="insight-axis">
              {monthLabel(row.month)}
            </text>
          ) : null
        ))}
      </svg>
      <div className="insight-line-legend">
        <span><i className="swatch trips" /> Trips</span>
        <span><i className="swatch km" /> Kilometres</span>
      </div>
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
        <text x="70" y="66" textAnchor="middle" className="insight-donut-total">{formatNumber(total)}</text>
        <text x="70" y="84" textAnchor="middle" className="insight-donut-caption">trips</text>
      </svg>
      <ul className="insight-legend">
        {rows.map((row, index) => (
          <li key={row.name}>
            <span className="insight-swatch" style={{ background: PALETTE[index % PALETTE.length] }} />
            {row.name}
            <strong>{formatNumber(row.count)}</strong>
          </li>
        ))}
      </ul>
    </div>
  )
}

const Panel = ({ title, note, chart, rows, linkMonth, wide }) => (
  <div className={`card insight-panel${wide ? ' insight-wide' : ''}`}>
    <h3>{title}</h3>
    {note ? <p className="card-subtitle">{note}</p> : null}
    <div className={`insight-split${wide ? ' insight-split-wide' : ''}`}>
      <div className="insight-chart">{chart}</div>
      {rows ? (
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
                <td className="fw-600">{formatNumber(row.count)}</td>
                {row.km != null ? <td className="fw-600">{formatNumber(row.km)} km</td> : null}
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
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
  const duties = data.by_duty || []
  const busyMonths = months.filter((row) => row.count > 0)

  return (
    <div>
      <Navigation />
      <div className="container">
        <div className="page-header" style={{ display: 'block' }}>
          <h1>Duty insights</h1>
          <p className="card-subtitle" style={{ marginTop: '8px' }}>
            Line chart for monthly volume, donut for cab mix, bars for rankings. Counts follow whatever is currently in RAC bookings.
          </p>
        </div>
        <div className="kpi-cards">
          <div className="card">
            <span className="card-label">All trips</span>
            <h2>{formatNumber(data.total_trips)}</h2>
          </div>
          <div className="card">
            <span className="card-label">Total km</span>
            <h2>{formatNumber(data.total_km)}</h2>
          </div>
          <div className="card">
            <span className="card-label">Drivers</span>
            <h2>{formatNumber(data.unique_drivers)}</h2>
          </div>
          <div className="card">
            <span className="card-label">Employees</span>
            <h2>{formatNumber(data.unique_employees)}</h2>
          </div>
        </div>
        <div className="insight-grid">
          <Panel
            title="Trips and km by month"
            note="Time series — solid line is trip count, dashed line is kilometres."
            wide
            linkMonth
            rows={busyMonths.slice(-8)}
            chart={months.length ? <MonthLine rows={months} /> : <p className="card-subtitle">No month data</p>}
          />
          <Panel
            title="Cab mix"
            note="Share of trips by vehicle type. Spellings like Creysta / Ertga are grouped."
            rows={cabs}
            chart={cabs.length ? <Donut rows={cabs} /> : <p className="card-subtitle">No cab data</p>}
          />
          <Panel
            title="Duty type"
            note="Package mix after combining 12 Hrs / 120 Km and 8 Hrs / 80 Km variants."
            rows={duties}
            chart={duties.length ? <HBars rows={duties} color="#f39c12" /> : <p className="card-subtitle">No duty data</p>}
          />
          <Panel
            title="Top drivers"
            note="Most trips. Names are title-cased so RAJA and Raja count as one person."
            rows={drivers}
            chart={drivers.length ? <HBars rows={drivers} color="#667eea" /> : <p className="card-subtitle">No driver data</p>}
          />
          <Panel
            title="Top pickup areas"
            note="Highest volume starting points."
            rows={areas}
            chart={areas.length ? <HBars rows={areas} color="#1abc9c" /> : <p className="card-subtitle">No area data</p>}
          />
        </div>
      </div>
    </div>
  )
}

export default InsightsPage
