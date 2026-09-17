import React, { useState, useEffect } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import Navigation from '../components/Navigation'
import SortTh from '../components/SortTh'
import { API } from '../services/api'

const DATE_FIRST = { trip_date: 'DESC', pickup_time: 'ASC', amount: 'DESC' }
const MONTH_NAMES = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']

const istToday = () => new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Kolkata' }).format(new Date())

const addDays = (ymd, delta) => {
  const [year, month, day] = String(ymd).split('-').map(Number)
  const next = new Date(Date.UTC(year, month - 1, day + delta))
  return next.toISOString().slice(0, 10)
}

const formatDate = (value) => {
  const match = String(value || '').match(/^(\d{4})-(\d{2})-(\d{2})/)
  if (!match) return value || '-'
  const month = MONTH_NAMES[Number(match[2]) - 1]
  if (!month) return value
  return `${Number(match[3])} ${month.slice(0, 3)} ${match[1]}`
}

const monthLabel = (value) => {
  const [year, month] = String(value || '').split('-')
  const name = MONTH_NAMES[Number(month) - 1]
  return name ? `${name} ${year}` : value
}

const BookingsPage = () => {
  const [searchParams, setSearchParams] = useSearchParams()
  const tab = searchParams.get('tab') === 'history' ? 'history' : 'recent'
  const [bookings, setBookings] = useState([])
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)
  const [savingId, setSavingId] = useState(null)
  const [bulkBusy, setBulkBusy] = useState(false)
  const [selected, setSelected] = useState({})
  const today = summary?.today || istToday()
  const [filters, setFilters] = useState({
    page: 1,
    limit: tab === 'recent' ? 200 : 50,
    status: '',
    search: searchParams.get('search') || '',
    date: tab === 'recent' ? (searchParams.get('date') || today) : '',
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
  }, [tab, filters.page, filters.status, filters.date, filters.payment, filters.month, filters.search, filters.sort_by, filters.sort_order, searchParams])

  const loadBookings = async () => {
    setLoading(true)
    try {
      const params = {
        page: filters.page,
        limit: tab === 'recent' ? 200 : filters.limit,
        ...(filters.status && { status: filters.status }),
        ...(filters.search && { search: filters.search }),
        ...(filters.payment && { payment: filters.payment }),
        sort_by: filters.sort_by,
        sort_order: filters.sort_order,
      }
      if (tab === 'recent') {
        if (filters.date) params.date = filters.date
        else params.days = 3
      } else {
        if (filters.date) params.date = filters.date
        if (filters.month) params.month = filters.month
      }
      const response = await API.getBookings(params)
      setBookings(response.data)
      setSummary(response.summary)
      setPagination(response.pagination)
      setSelected({})
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const setTab = (next) => {
    const params = new URLSearchParams(searchParams)
    if (next === 'history') params.set('tab', 'history')
    else params.delete('tab')
    params.delete('date')
    setSearchParams(params)
    setFilters((current) => ({
      ...current,
      page: 1,
      month: next === 'history' ? current.month : '',
      date: next === 'recent' ? istToday() : '',
      limit: next === 'recent' ? 200 : 50,
    }))
  }

  const setRecentDay = (value) => {
    setFilters((current) => ({ ...current, date: value, page: 1 }))
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

  const selectedIds = Object.keys(selected).filter((id) => selected[id])
  const targetIds = selectedIds.length ? selectedIds : bookings.map((row) => row.booking_id)

  const markBulk = async (paid) => {
    if (!targetIds.length) return
    const label = paid ? 'Paid' : 'Unpaid'
    if (!window.confirm(`Mark ${targetIds.length} booking(s) as ${label}?`)) return
    setBulkBusy(true)
    try {
      await API.updateBookingsPaymentBulk({ booking_ids: targetIds, paid })
      await loadBookings()
    } catch (err) {
      alert(err.message)
    } finally {
      setBulkBusy(false)
    }
  }

  const toggleAll = (checked) => {
    const next = {}
    if (checked) bookings.forEach((row) => { next[row.booking_id] = true })
    setSelected(next)
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

  const dayPills = [
    { value: today, label: 'Today' },
    { value: addDays(today, -1), label: 'Yesterday' },
    { value: addDays(today, -2), label: 'Day before' },
    { value: '', label: 'All 3 days' },
  ]

  return (
    <div>
      <Navigation />
      <div className="container">
        <h1>Bookings</h1>
        <div className="rac-tabs" role="tablist">
          <button type="button" className={tab === 'recent' ? 'is-on' : ''} onClick={() => setTab('recent')}>
            Last 3 days
          </button>
          <button type="button" className={tab === 'history' ? 'is-on' : ''} onClick={() => setTab('history')}>
            All history
          </button>
        </div>
        <p className="card-subtitle" style={{ marginBottom: '16px' }}>
          {tab === 'recent'
            ? 'Today, yesterday, and the day before. Mark one booking or the whole list as paid or unpaid.'
            : 'Click a column heading to sort. Date uses latest first; click again for oldest.'}
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
            <div className="card" style={{ padding: '15px', borderLeft: '4px solid #27ae60' }}>
              <span className="card-label" style={{ fontSize: '12px', color: '#666' }}>✅ Driver paid</span>
              <h2 style={{ margin: '5px 0', fontSize: '24px' }}>{summary.driver_paid || 0}</h2>
            </div>
          </div>
        )}

        {tab === 'recent' && (
          <div className="rac-day-pills">
            {dayPills.map((pill) => (
              <button
                key={pill.label}
                type="button"
                className={filters.date === pill.value ? 'is-on' : ''}
                onClick={() => setRecentDay(pill.value)}
              >
                {pill.label}
              </button>
            ))}
            <button type="button" className="btn-small" disabled={bulkBusy || !bookings.length} onClick={() => markBulk(true)}>
              Mark {selectedIds.length ? 'selected' : 'all'} paid
            </button>
            <button type="button" className="btn-small" disabled={bulkBusy || !bookings.length} onClick={() => markBulk(false)} style={{ background: '#e67e22', color: '#fff', border: 'none' }}>
              Mark {selectedIds.length ? 'selected' : 'all'} unpaid
            </button>
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
            {tab === 'history' && (
              <>
                <select
                  value={filters.month}
                  onChange={(e) => setFilters({ ...filters, month: e.target.value, page: 1 })}
                  className="input"
                  style={{ width: 'auto' }}
                >
                  <option value="">All months</option>
                  {(summary?.months || []).map((month) => (
                    <option key={month} value={month}>{monthLabel(month)}</option>
                  ))}
                </select>
                <input
                  type="date"
                  value={filters.date}
                  onChange={(e) => setFilters({ ...filters, date: e.target.value, page: 1 })}
                  className="input"
                  style={{ width: 'auto' }}
                  title="Filter by trip date"
                />
              </>
            )}
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
                  {tab === 'recent' && (
                    <th>
                      <input
                        type="checkbox"
                        checked={bookings.length > 0 && selectedIds.length === bookings.length}
                        onChange={(e) => toggleAll(e.target.checked)}
                        aria-label="Select all"
                      />
                    </th>
                  )}
                  <SortTh field="source_booking_id" label="Booking ID" sortBy={filters.sort_by} sortOrder={filters.sort_order} onSort={toggleSort} />
                  <SortTh field="trip_date" label="Date" sortBy={filters.sort_by} sortOrder={filters.sort_order} onSort={toggleSort} />
                  <SortTh field="employee_name" label="Employee" sortBy={filters.sort_by} sortOrder={filters.sort_order} onSort={toggleSort} />
                  <SortTh field="planned_start" label="Pickup" sortBy={filters.sort_by} sortOrder={filters.sort_order} onSort={toggleSort} />
                  <SortTh field="pickup_time" label="Time" sortBy={filters.sort_by} sortOrder={filters.sort_order} onSort={toggleSort} />
                  <SortTh field="duty_type" label="Duty Type" sortBy={filters.sort_by} sortOrder={filters.sort_order} onSort={toggleSort} />
                  <SortTh field="cab_type" label="Cab" sortBy={filters.sort_by} sortOrder={filters.sort_order} onSort={toggleSort} />
                  <SortTh field="amount" label="Amount" sortBy={filters.sort_by} sortOrder={filters.sort_order} onSort={toggleSort} />
                  <SortTh field="status" label="Status" sortBy={filters.sort_by} sortOrder={filters.sort_order} onSort={toggleSort} />
                  <SortTh field="driver_payment_status" label="Driver pay" sortBy={filters.sort_by} sortOrder={filters.sort_order} onSort={toggleSort} />
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {bookings.map((booking) => (
                  <tr key={booking.booking_id}>
                    {tab === 'recent' && (
                      <td>
                        <input
                          type="checkbox"
                          checked={!!selected[booking.booking_id]}
                          onChange={(e) => setSelected((current) => ({ ...current, [booking.booking_id]: e.target.checked }))}
                          aria-label={`Select ${booking.source_booking_id}`}
                        />
                      </td>
                    )}
                    <td className="fw-600">{booking.source_booking_id}</td>
                    <td>{formatDate(booking.trip_date)}</td>
                    <td>{booking.employee_name}</td>
                    <td>{booking.planned_start}</td>
                    <td>{booking.pickup_time}</td>
                    <td>{booking.duty_type || booking.booking_type}</td>
                    <td>{booking.cab_type}</td>
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
            {!bookings.length && <p className="rac-empty">No bookings for this view.</p>}

            <div className="pagination">
              <button
                onClick={() => setFilters({ ...filters, page: filters.page - 1 })}
                disabled={pagination.page === 1}
                className="btn-secondary"
              >
                Previous
              </button>
              <span>Page {pagination.page} of {Math.max(1, Math.ceil(pagination.total / pagination.limit) || 1)}</span>
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
