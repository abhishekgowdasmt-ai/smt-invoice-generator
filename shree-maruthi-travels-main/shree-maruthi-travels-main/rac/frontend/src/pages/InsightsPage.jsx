import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import Navigation from '../components/Navigation'
import { API } from '../services/api'

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
        <div className="settings-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '20px', marginTop: '20px' }}>
          <div className="card">
            <h3>By month</h3>
            <table className="table table-compact">
              <tbody>
                {(data.by_month || []).map((row) => (
                  <tr key={row.month}>
                    <td><Link to={`/bookings?month=${row.month}`}>{row.month}</Link></td>
                    <td className="fw-600">{row.count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="card">
            <h3>Cab type</h3>
            <table className="table table-compact">
              <tbody>
                {(data.by_cab || []).map((row) => (
                  <tr key={row.name}>
                    <td>{row.name}</td>
                    <td className="fw-600">{row.count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="card">
            <h3>Top drivers</h3>
            <table className="table table-compact">
              <tbody>
                {(data.top_drivers || []).map((row) => (
                  <tr key={row.name}>
                    <td>{row.name}</td>
                    <td className="fw-600">{row.count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="card">
            <h3>Top pickup areas</h3>
            <table className="table table-compact">
              <tbody>
                {(data.top_areas || []).map((row) => (
                  <tr key={row.name}>
                    <td>{row.name}</td>
                    <td className="fw-600">{row.count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}

export default InsightsPage
