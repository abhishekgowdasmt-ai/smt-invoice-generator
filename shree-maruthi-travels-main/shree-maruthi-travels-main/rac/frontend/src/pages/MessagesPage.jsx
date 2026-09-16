import React, { useState, useEffect } from 'react'
import Navigation from '../components/Navigation'
import SortTh from '../components/SortTh'
import { API } from '../services/api'
import { QRCodeSVG } from 'qrcode.react'

const MessagesPage = () => {
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(true)
  const [selectedMessage, setSelectedMessage] = useState(null)
  const [filters, setFilters] = useState({ page: 1, limit: 50, send_status: '', sort_by: 'created_at', sort_order: 'DESC' })
  const [pagination, setPagination] = useState({ page: 1, limit: 50, total: 0 })

  useEffect(() => {
    loadMessages()
  }, [filters.page, filters.send_status, filters.sort_by, filters.sort_order])

  const loadMessages = async () => {
    setLoading(true)
    try {
      const params = {
        page: filters.page,
        limit: filters.limit,
        ...(filters.send_status && { send_status: filters.send_status }),
        sort_by: filters.sort_by,
        sort_order: filters.sort_order,
      }
      const response = await API.getMessages(params)
      setMessages(response.data)
      setPagination(response.pagination)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const toggleSort = (field) => {
    setFilters((current) => {
      if (current.sort_by === field) {
        return { ...current, page: 1, sort_order: current.sort_order === 'DESC' ? 'ASC' : 'DESC' }
      }
      return { ...current, page: 1, sort_by: field, sort_order: field === 'created_at' ? 'DESC' : 'ASC' }
    })
  }

  const renderBadge = (status) => {
    const colors = {
      pending: '#95a5a6',
      queued: '#3498db',
      ready: '#3498db',
      sent: '#2ecc71',
      skipped: '#7f8c8d',
      failed: '#e74c3c'
    }
    return <span className="badge" style={{ backgroundColor: colors[status] || '#95a5a6' }}>{status || '-'}</span>
  }

  const handleOpenWhatsApp = async (message) => {
    let link = message.wa_link
    if (!link && message.assignment_id) {
      const result = await API.resendMessage(message.assignment_id)
      link = result.wa_link
      if (link) setSelectedMessage({ ...message, wa_link: link, message_body: result.message_body || message.message_body })
    }
    if (link) window.open(link, '_blank', 'noopener')
  }

  return (
    <div>
      <Navigation />
      <div className="container">
        <h1>Message Log</h1>
        <p className="text-muted" style={{ marginBottom: '16px' }}>If WhatsApp is linked, assign sends from your account. If a row is still Ready, open WhatsApp or scan that chat QR.</p>

        <div className="filters">
          <select
            value={filters.send_status}
            onChange={(e) => setFilters({ ...filters, send_status: e.target.value, page: 1 })}
            className="input"
          >
            <option value="">All statuses</option>
            <option value="sent">Sent</option>
            <option value="ready">Ready</option>
            <option value="skipped">Skipped</option>
            <option value="failed">Failed</option>
          </select>
        </div>

        {loading ? (
          <p className="loading">Loading...</p>
        ) : (
          <div className="message-layout">
            <div className="message-list">
              <table className="table">
                <thead>
                  <tr>
                    <SortTh field="booking.source_booking_id" label="Booking" sortBy={filters.sort_by} sortOrder={filters.sort_order} onSort={toggleSort} />
                    <SortTh field="driver.driver_name" label="Driver" sortBy={filters.sort_by} sortOrder={filters.sort_order} onSort={toggleSort} />
                    <SortTh field="phone_number" label="Phone" sortBy={filters.sort_by} sortOrder={filters.sort_order} onSort={toggleSort} />
                    <SortTh field="send_status" label="Status" sortBy={filters.sort_by} sortOrder={filters.sort_order} onSort={toggleSort} />
                    <SortTh field="created_at" label="Created" sortBy={filters.sort_by} sortOrder={filters.sort_order} onSort={toggleSort} />
                  </tr>
                </thead>
                <tbody>
                  {messages.map((msg) => (
                    <tr
                      key={msg.message_log_id}
                      onClick={() => setSelectedMessage(msg)}
                      className={selectedMessage?.message_log_id === msg.message_log_id ? 'selected' : ''}
                      style={{ cursor: 'pointer' }}
                    >
                      <td className="fw-600">{msg.booking?.source_booking_id}</td>
                      <td>{msg.driver?.driver_name}</td>
                      <td>{msg.phone_number}</td>
                      <td>{renderBadge(msg.send_status)}</td>
                      <td>{msg.created_at ? new Date(msg.created_at).toLocaleString() : '-'}</td>
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
                <span>Page {pagination.page}</span>
                <button
                  onClick={() => setFilters({ ...filters, page: filters.page + 1 })}
                  disabled={pagination.page >= Math.ceil(pagination.total / pagination.limit)}
                  className="btn-secondary"
                >
                  Next
                </button>
              </div>
            </div>

            {selectedMessage && (
              <div className="message-detail">
                <h2>Message Details</h2>
                <div className="detail-info">
                  <p><strong>Booking ID:</strong> {selectedMessage.booking?.source_booking_id}</p>
                  <p><strong>Driver:</strong> {selectedMessage.driver?.driver_name}</p>
                  <p><strong>Phone:</strong> {selectedMessage.phone_number}</p>
                  <p><strong>Status:</strong> {renderBadge(selectedMessage.send_status)}</p>
                </div>

                <div className="message-body">
                  <h3>Message Content</h3>
                  <pre>{selectedMessage.message_body}</pre>
                </div>

                {(selectedMessage.wa_link || selectedMessage.assignment_id) && (
                  <div className="action-buttons" style={{ display: 'flex', flexDirection: 'column', gap: '12px', alignItems: 'flex-start' }}>
                    <button onClick={() => handleOpenWhatsApp(selectedMessage)} className="btn-primary">
                      Open WhatsApp
                    </button>
                    {selectedMessage.wa_link && (
                      <div style={{ background: 'white', padding: '12px', borderRadius: '12px', border: '1px solid #eee' }}>
                        <QRCodeSVG value={selectedMessage.wa_link} size={160} />
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

export default MessagesPage
