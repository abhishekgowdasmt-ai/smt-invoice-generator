import React, { useState, useEffect } from 'react'
import Navigation from '../components/Navigation'
import { API } from '../services/api'

const MessagesPage = () => {
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(true)
  const [selectedMessage, setSelectedMessage] = useState(null)
  const [filters, setFilters] = useState({ page: 1, limit: 50, send_status: '', delivery_status: '' })
  const [pagination, setPagination] = useState({ page: 1, limit: 50, total: 0 })

  useEffect(() => {
    loadMessages()
  }, [filters.page, filters.send_status, filters.delivery_status])

  const loadMessages = async () => {
    setLoading(true)
    try {
      const params = {
        page: filters.page,
        limit: filters.limit,
        ...(filters.send_status && { send_status: filters.send_status }),
        ...(filters.delivery_status && { delivery_status: filters.delivery_status })
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

  const renderBadge = (status, type = 'send') => {
    const colors = {
      'pending': '#95a5a6',
      'queued': '#3498db',
      'sent': '#2ecc71',
      'delivered': '#27ae60',
      'read': '#1abc9c',
      'failed': '#e74c3c'
    }
    return <span className="badge" style={{ backgroundColor: colors[status] || '#95a5a6' }}>{status}</span>
  }

  const handleResend = async (message) => {
    try {
      if (message.assignment_id) {
        await API.resendMessage(message.assignment_id)
        alert('Message queued for resend')
        loadMessages()
      }
    } catch (err) {
      alert(`Error: ${err.message}`)
    }
  }

  return (
    <div>
      <Navigation />
      <div className="container">
        <h1>Message Log</h1>

        <div className="filters">
          <select
            value={filters.send_status}
            onChange={(e) => setFilters({ ...filters, send_status: e.target.value, page: 1 })}
            className="input"
          >
            <option value="">All Send Status</option>
            <option value="pending">Pending</option>
            <option value="queued">Queued</option>
            <option value="sent">Sent</option>
            <option value="failed">Failed</option>
          </select>

          <select
            value={filters.delivery_status}
            onChange={(e) => setFilters({ ...filters, delivery_status: e.target.value, page: 1 })}
            className="input"
          >
            <option value="">All Delivery Status</option>
            <option value="queued">Queued</option>
            <option value="sent">Sent</option>
            <option value="delivered">Delivered</option>
            <option value="read">Read</option>
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
                    <th>Booking</th>
                    <th>Driver</th>
                    <th>Phone</th>
                    <th>Send Status</th>
                    <th>Delivery</th>
                    <th>Sent At</th>
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
                      <td>{msg.delivery_status ? renderBadge(msg.delivery_status) : '-'}</td>
                      <td>{msg.sent_at ? new Date(msg.sent_at).toLocaleTimeString() : '-'}</td>
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
                  <p><strong>Provider:</strong> {selectedMessage.provider_name}</p>
                  <p><strong>Send Status:</strong> {renderBadge(selectedMessage.send_status)}</p>
                  <p><strong>Delivery Status:</strong> {selectedMessage.delivery_status ? renderBadge(selectedMessage.delivery_status) : 'N/A'}</p>
                  <p><strong>Sent At:</strong> {selectedMessage.sent_at ? new Date(selectedMessage.sent_at).toLocaleString() : 'Not sent'}</p>
                  <p><strong>Delivered At:</strong> {selectedMessage.delivered_at ? new Date(selectedMessage.delivered_at).toLocaleString() : '-'}</p>
                  <p><strong>Retry Count:</strong> {selectedMessage.retry_count}</p>
                  {selectedMessage.failed_reason && (
                    <p><strong>Failed Reason:</strong> {selectedMessage.failed_reason}</p>
                  )}
                </div>

                <div className="message-body">
                  <h3>Message Content</h3>
                  <pre>{selectedMessage.message_body}</pre>
                </div>

                {selectedMessage.send_status === 'failed' && (
                  <div className="action-buttons">
                    <button onClick={() => handleResend(selectedMessage)} className="btn-primary">
                      Resend Message
                    </button>
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
