import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import Navigation from '../components/Navigation'
import { API } from '../services/api'

const BookingsPage = () => {
  const [bookings, setBookings] = useState([])
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)
  const [filters, setFilters] = useState({ page: 1, limit: 50, status: '', search: '', date: '' })
  const [pagination, setPagination] = useState({ page: 1, limit: 50, total: 0 })

  useEffect(() => {
    loadBookings()
  }, [filters.page, filters.status, filters.date])

  const loadBookings = async () => {
    setLoading(true)
    try {
      const params = {
        page: filters.page,
        limit: filters.limit,
        ...(filters.status && { status: filters.status }),
        ...(filters.search && { search: filters.search }),
        ...(filters.date && { date: filters.date })
      }
      const response = await API.getBookings(params)
      setBookings(response.data)
      setSummary(response.summary)
      setPagination(response.pagination)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const handleSearch = (e) => {
    e.preventDefault()
    setFilters({ ...filters, page: 1 })
  }

  const renderStatusBadge = (status) => {
    const colors = {
      'Uploaded': '#3498db',
      'Unassigned': '#f39c12',
      'Assigned': '#2ecc71',
      'Message Sent': '#27ae60',
      'Message Failed': '#e74c3c',
      'Completed': '#2c3e50',
      'Cancelled': '#95a5a6'
    }
    return <span className="badge" style={{ backgroundColor: colors[status] || '#95a5a6' }}>{status}</span>
  }

  return (
    <div>
      <Navigation />
      <div className="container">
        <h1>Bookings</h1>

        {summary && (
          <div className="kpi-cards" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '15px', marginBottom: '20px' }}>
            <div className="card" style={{ padding: '15px', borderLeft: '4px solid #3498db' }}>
              <span className="card-label" style={{ fontSize: '12px', color: '#666' }}>📋 Total Bookings</span>
              <h2 style={{ margin: '5px 0', fontSize: '24px' }}>{summary.total}</h2>
            </div>
            <div className="card" style={{ padding: '15px', borderLeft: '4px solid #f39c12' }}>
              <span className="card-label" style={{ fontSize: '12px', color: '#666' }}>⏳ Unassigned</span>
              <h2 style={{ margin: '5px 0', fontSize: '24px' }}>{summary.unassigned}</h2>
            </div>
            <div className="card" style={{ padding: '15px', borderLeft: '4px solid #2ecc71' }}>
              <span className="card-label" style={{ fontSize: '12px', color: '#666' }}>✅ Assigned</span>
              <h2 style={{ margin: '5px 0', fontSize: '24px' }}>{summary.assigned}</h2>
            </div>
            <div className="card" style={{ padding: '15px', borderLeft: '4px solid #2c3e50' }}>
              <span className="card-label" style={{ fontSize: '12px', color: '#666' }}>🏁 Completed</span>
              <h2 style={{ margin: '5px 0', fontSize: '24px' }}>{summary.completed}</h2>
            </div>
            <div className="card" style={{ padding: '15px', borderLeft: '4px solid #e74c3c' }}>
              <span className="card-label" style={{ fontSize: '12px', color: '#666' }}>🚫 Cancelled</span>
              <h2 style={{ margin: '5px 0', fontSize: '24px' }}>{summary.cancelled}</h2>
            </div>
          </div>
        )}

        <div className="filters">
          <form onSubmit={handleSearch} className="search-form" style={{ display: 'flex', flexWrap: 'wrap', gap: '10px' }}>
            <input
              type="text"
              placeholder="Search by ID, Employee..."
              value={filters.search}
              onChange={(e) => setFilters({ ...filters, search: e.target.value })}
              className="input"
              style={{ flex: '1', minWidth: '200px' }}
            />
            <input
              type="date"
              value={filters.date}
              onChange={(e) => setFilters({ ...filters, date: e.target.value, page: 1 })}
              className="input"
              style={{ width: 'auto' }}
            />
            <select
              value={filters.status}
              onChange={(e) => setFilters({ ...filters, status: e.target.value, page: 1 })}
              className="input"
              style={{ width: 'auto' }}
            >
              <option value="">All Status</option>
              <option value="Uploaded">Uploaded</option>
              <option value="Unassigned">Unassigned</option>
              <option value="Assigned">Assigned</option>
              <option value="Message Sent">Message Sent</option>
              <option value="Message Failed">Message Failed</option>
              <option value="Completed">Completed</option>
              <option value="Cancelled">Cancelled</option>
            </select>
            <button type="submit" className="btn-primary">Search</button>
          </form>
        </div>

        {loading ? (
          <p className="loading">Loading...</p>
        ) : (
          <div className="table-responsive">
            <table className="table">
              <thead>
                <tr>
                  <th>Booking ID</th>
                  <th>Date</th>
                  <th>Employee</th>
                  <th>Pickup</th>
                  <th>Time</th>
                  <th>Duty Type</th>
                  <th>Amount</th>
                  <th>Status</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {bookings.map((booking) => (
                  <tr key={booking.booking_id}>
                    <td className="fw-600">{booking.source_booking_id}</td>
                    <td>{new Date(booking.trip_date).toLocaleDateString()}</td>
                    <td>{booking.employee_name}</td>
                    <td>{booking.planned_start}</td>
                    <td>{booking.pickup_time}</td>
                    <td>{booking.duty_type}</td>
                    <td className="fw-600">₹{booking.amount}</td>
                    <td>{renderStatusBadge(booking.status)}</td>
                    <td>
                      <Link to={`/bookings/${booking.booking_id}`} className="btn-small">View</Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            <div className="pagination">
              <button
                onClick={() => setFilters({ ...filters, page: filters.page - 1 })}
                disabled={pagination.page === 1}
                className="btn-secondary"
              >
                Previous
              </button>
              <span>Page {pagination.page} of {Math.ceil(pagination.total / pagination.limit)}</span>
              <button
                onClick={() => setFilters({ ...filters, page: filters.page + 1 })}
                disabled={pagination.page >= Math.ceil(pagination.total / pagination.limit)}
                className="btn-secondary"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default BookingsPage
