import React, { useState, useEffect } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import Navigation from '../components/Navigation'
import SortTh from '../components/SortTh'
import { API } from '../services/api'

const DATE_FIRST = { trip_date: 'DESC', pickup_time: 'ASC', amount: 'DESC' }

const formatDate = (value) => {
  if (!value) return '-'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return parsed.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
}

const BookingsPage = () => {
  const [searchParams] = useSearchParams()
  const [bookings, setBookings] = useState([])
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)
  const [savingId, setSavingId] = useState(null)
  const [filters, setFilters] = useState({
    page: 1,
    limit: 50,
    status: '',
    search: searchParams.get('search') || '',
    date: '',
    payment: searchParams.get('payment') || '',
    month: searchParams.get('month') || '',
    sort_by: 'trip_date',
    sort_order: 'DESC',
  })
  const [pagination, setPagination] = useState({ page: 1, limit: 50, total: 0 })

  useEffect(() => {
    const fromUrl = searchParams.get('search') || ''
    if (fromUrl && fromUrl !== filters.search) {
      setFilters((current) => ({ ...current, search: fromUrl, page: 1 }))
      return
    }
    loadBookings()
  }, [filters.page, filters.status, filters.date, filters.payment, filters.month, filters.search, filters.sort_by, filters.sort_order, searchParams])

  const loadBookings = async () => {
    setLoading(true)
    try {
      const params = {
        page: filters.page,
        limit: filters.limit,
        ...(filters.status && { status: filters.status }),
        ...(filters.search && { search: filters.search }),
        ...(filters.date && { date: filters.date }),
        ...(filters.payment && { payment: filters.payment }),
        ...(filters.month && { month: filters.month }),
        sort_by: filters.sort_by,
        sort_order: filters.sort_order,
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

  const toggleSort = (field) => {
    setFilters((current) => {
      if (current.sort_by === field) {
        return { ...current, page: 1, sort_order: current.sort_order === 'DESC' ? 'ASC' : 'DESC' }
      }
      return { ...current, page: 1, sort_by: field, sort_order: DATE_FIRST[field] || 'ASC' }
    })
  }

  const isPaid = (booking) => String(booking.driver_payment_status || '').toLowerCase() === 'paid'

  const togglePayment = async (booking) => {
    setSavingId(booking.booking_id)
    try {
      await API.updateBookingPayment(booking.booking_id, { paid: !isPaid(booking) })
      await loadBookings()
    } catch (err) {
      alert(err.message)
    } finally {
      setSavingId(null)
    }
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
        <p className="card-subtitle" style={{ marginBottom: '16px' }}>
          Click a column heading to sort. Date uses latest first; click again for oldest.
        </p>

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
            <div className="card" style={{ padding: '15px', borderLeft: '4px solid #e67e22' }}>
              <span className="card-label" style={{ fontSize: '12px', color: '#666' }}>💸 Driver unpaid</span>
              <h2 style={{ margin: '5px 0', fontSize: '24px' }}>{summary.driver_unpaid || 0}</h2>
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
            <select
              value={filters.month}
              onChange={(e) => setFilters({ ...filters, month: e.target.value, page: 1 })}
              className="input"
              style={{ width: 'auto' }}
            >
              <option value="">All months</option>
              <option value="2026-05">May 2026</option>
              <option value="2026-06">June 2026</option>
              <option value="2026-07">July 2026</option>
              <option value="2026-08">August 2026</option>
            </select>
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
            <select
              value={filters.payment}
              onChange={(e) => setFilters({ ...filters, payment: e.target.value, page: 1 })}
              className="input"
              style={{ width: 'auto' }}
            >
              <option value="">All payments</option>
              <option value="Unpaid">Driver unpaid</option>
              <option value="Paid">Driver paid</option>
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
                  <SortTh field="source_booking_id" label="Booking ID" sortBy={filters.sort_by} sortOrder={filters.sort_order} onSort={toggleSort} />
                  <SortTh field="trip_date" label="Date" sortBy={filters.sort_by} sortOrder={filters.sort_order} onSort={toggleSort} />
                  <SortTh field="employee_name" label="Employee" sortBy={filters.sort_by} sortOrder={filters.sort_order} onSort={toggleSort} />
                  <SortTh field="planned_start" label="Pickup" sortBy={filters.sort_by} sortOrder={filters.sort_order} onSort={toggleSort} />
                  <SortTh field="pickup_time" label="Time" sortBy={filters.sort_by} sortOrder={filters.sort_order} onSort={toggleSort} />
                  <SortTh field="duty_type" label="Duty Type" sortBy={filters.sort_by} sortOrder={filters.sort_order} onSort={toggleSort} />
                  <SortTh field="amount" label="Amount" sortBy={filters.sort_by} sortOrder={filters.sort_order} onSort={toggleSort} />
                  <SortTh field="status" label="Status" sortBy={filters.sort_by} sortOrder={filters.sort_order} onSort={toggleSort} />
                  <SortTh field="driver_payment_status" label="Driver pay" sortBy={filters.sort_by} sortOrder={filters.sort_order} onSort={toggleSort} />
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {bookings.map((booking) => (
                  <tr key={booking.booking_id}>
                    <td className="fw-600">{booking.source_booking_id}</td>
                    <td>{formatDate(booking.trip_date)}</td>
                    <td>{booking.employee_name}</td>
                    <td>{booking.planned_start}</td>
                    <td>{booking.pickup_time}</td>
                    <td>{booking.duty_type}</td>
                    <td className="fw-600">₹{booking.amount}</td>
                    <td>{renderStatusBadge(booking.status)}</td>
                    <td>
                      <button
                        type="button"
                        className="btn-small"
                        disabled={savingId === booking.booking_id}
                        onClick={() => togglePayment(booking)}
                        style={{
                          backgroundColor: isPaid(booking) ? '#2ecc71' : '#e67e22',
                          color: 'white',
                          border: 'none'
                        }}
                      >
                        {savingId === booking.booking_id ? '…' : isPaid(booking) ? 'Paid' : 'Unpaid'}
                      </button>
                    </td>
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
