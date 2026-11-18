import React, { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import Navigation from '../components/Navigation'
import { API } from '../services/api'
import { QRCodeSVG } from 'qrcode.react'

const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

const formatTripDate = (value) => {
  const match = String(value || '').match(/^(\d{4})-(\d{2})-(\d{2})/)
  if (!match) return value || '-'
  const month = MONTH_NAMES[Number(match[2]) - 1]
  if (!month) return value
  return `${Number(match[3])} ${month} ${match[1]}`
}

const BookingDetailPage = () => {
  const { bookingId } = useParams()
  const navigate = useNavigate()
  const [booking, setBooking] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [assignmentModal, setAssignmentModal] = useState(false)
  const [drivers, setDrivers] = useState([])
  const [selectedDriver, setSelectedDriver] = useState(null)
  const [assignmentNotes, setAssignmentNotes] = useState('')
  const [sendMessage, setSendMessage] = useState(true)
  const [assigning, setAssigning] = useState(false)
  const [waDraft, setWaDraft] = useState(null)

  useEffect(() => {
    loadBooking()
    loadDrivers()
  }, [bookingId])

  const loadBooking = async () => {
    try {
      const response = await API.getBooking(bookingId)
      setBooking(response.data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const loadDrivers = async () => {
    try {
      const response = await API.getDrivers({ active_only: true, limit: 200 })
      setDrivers(response.data)
    } catch (err) {
      console.error('Failed to load drivers:', err)
    }
  }

  const handleAssign = async () => {
    if (!selectedDriver) {
      alert('Please select a driver')
      return
    }

    setAssigning(true)
    try {
      const result = await API.createAssignment({
        booking_id: booking.booking_id,
        driver_id: selectedDriver.driver_id,
        assignment_notes: assignmentNotes,
        send_message_now: sendMessage
      })
      setAssignmentModal(false)
      setSelectedDriver(null)
      setAssignmentNotes('')
      loadBooking()
      const lines = []
      if (result.reassigned) {
        lines.push(result.previous_whatsapp_status === 'sent'
          ? `${result.previous_driver_name} was told this duty is no longer theirs.`
          : `${result.previous_driver_name || 'The previous driver'} was not reached on WhatsApp.`)
      }
      if (!sendMessage) {
        lines.push(result.reassigned ? 'Duty reassigned. No WhatsApp was sent.' : 'Booking assigned. No WhatsApp was sent.')
      } else if (result.whatsapp_status === 'sent') {
        lines.push(`${result.driver_name} received the duty on WhatsApp.`)
      } else {
        lines.push(`WhatsApp did not reach ${result.driver_name}.`)
        if (result.wa_link) setWaDraft(result)
      }
      alert(lines.join(' '))
    } catch (err) {
      alert('Failed to assign: ' + err.message)
    } finally {
      setAssigning(false)
    }
  }

  const handleResend = async () => {
    if (!booking?.assignment_id) {
      alert('No assignment to resend')
      return
    }
    try {
      const result = await API.resendMessage(booking.assignment_id)
      loadBooking()
      if (result.whatsapp_status === 'sent' || result.whatsapp_message_status === 'sent') {
        alert(`Duty resent to ${result.driver_name} on WhatsApp.`)
      } else {
        if (result.wa_link) setWaDraft(result)
        alert(result.message || 'WhatsApp did not send')
      }
    } catch (err) {
      alert('Failed to resend: ' + err.message)
    }
  }

  const handleUnassign = async () => {
    const name = booking?.assignedDriver?.driver_name || 'this driver'
    if (!window.confirm(`Remove ${name} from this duty and tell them on WhatsApp that it is no longer theirs?`)) return
    try {
      const result = await API.unassignBooking(booking.booking_id)
      loadBooking()
      alert(result.message || 'Driver removed')
    } catch (err) {
      alert('Failed to remove driver: ' + err.message)
    }
  }

  const handleUpdateStatus = async (newStatus) => {
    const driverName = booking?.assignedDriver?.driver_name
    const extra = newStatus === 'Cancelled' && booking?.assigned_driver_id
      ? ` ${driverName || 'The driver'} will be told on WhatsApp that this trip is cancelled.`
      : ''
    if (!window.confirm(`Are you sure you want to change status to ${newStatus}?${extra}`)) return
    
    try {
      const result = await API.updateBookingStatus(bookingId, newStatus)
      loadBooking()
      alert(result.message || `Booking ${newStatus} successfully!`)
    } catch (err) {
      alert('Failed to update status: ' + err.message)
    }
  }

  if (loading) return <div><Navigation /><p className="loading">Loading...</p></div>
  if (error) return <div><Navigation /><p className="error">{error}</p></div>
  if (!booking) return <div><Navigation /><p>Booking not found</p></div>

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
        <div className="page-header">
          <h1>Booking Detail: {booking.source_booking_id}</h1>
          <div style={{ display: 'flex', gap: '10px' }}>
            {booking.status !== 'Completed' && booking.status !== 'Cancelled' && booking.assigned_driver_id && (
              <button onClick={() => handleUpdateStatus('Completed')} className="btn-primary" style={{ backgroundColor: '#2c3e50' }}>Mark Completed</button>
            )}
            {booking.status !== 'Cancelled' && booking.status !== 'Completed' && (
              <button onClick={() => handleUpdateStatus('Cancelled')} className="btn-secondary" style={{ backgroundColor: '#e74c3c', color: 'white', border: 'none' }}>Cancel Booking</button>
            )}
            <button onClick={() => navigate('/bookings')} className="btn-secondary">← Back</button>
          </div>
        </div>

        {waDraft?.wa_link && (
          <div className="card" style={{ marginBottom: '20px', display: 'flex', gap: '24px', alignItems: 'center', flexWrap: 'wrap' }}>
            <div>
              <h3>Send WhatsApp to {waDraft.driver_name}</h3>
              <p>Scan this QR with your phone or tap Open WhatsApp, then tap Send.</p>
              <a className="btn-primary" href={waDraft.wa_link} target="_blank" rel="noreferrer" style={{ display: 'inline-block', marginTop: '12px', textDecoration: 'none' }}>
                Open WhatsApp
              </a>
            </div>
            <div style={{ background: 'white', padding: '12px', borderRadius: '12px', border: '1px solid #eee' }}>
              <QRCodeSVG value={waDraft.wa_link} size={160} />
            </div>
          </div>
        )}

        <div className="booking-detail">
          <div className="detail-section">
            <h2>Booking Info</h2>
            <div className="detail-grid">
              <div className="detail-row">
                <label>Booking ID</label>
                <span>{booking.source_booking_id}</span>
              </div>
              <div className="detail-row">
                <label>System ID</label>
                <span>{booking.booking_id}</span>
              </div>
              <div className="detail-row">
                <label>Trip Date</label>
                <span>{formatTripDate(booking.trip_date)}</span>
              </div>
              <div className="detail-row">
                <label>Employee Name</label>
                <span>{booking.employee_name}</span>
              </div>
              <div className="detail-row">
                <label>Status</label>
                <span>{renderStatusBadge(booking.status)}</span>
              </div>
            </div>
          </div>

          <div className="detail-section">
            <h2>Ride Info</h2>
            <div className="detail-grid">
              <div className="detail-row">
                <label>Vehicle</label>
                <span>{booking.source_vehicle_no} ({booking.cab_type})</span>
              </div>
              <div className="detail-row">
                <label>Vendor</label>
                <span>{booking.vendor_name}</span>
              </div>
              <div className="detail-row">
                <label>Pickup</label>
                <span>{booking.planned_start}</span>
              </div>
              <div className="detail-row">
                <label>Route</label>
                <span>{booking.route_text}</span>
              </div>
              <div className="detail-row">
                <label>Pickup Time</label>
                <span>{booking.pickup_time}</span>
              </div>
              <div className="detail-row">
                <label>End Time</label>
                <span>{booking.end_time}</span>
              </div>
              <div className="detail-row">
                <label>Total Hours</label>
                <span>{booking.total_hours_text}</span>
              </div>
              <div className="detail-row">
                <label>Duty Type</label>
                <span>{booking.duty_type}</span>
              </div>
            </div>
          </div>

          <div className="detail-section">
            <h2>Billing Info</h2>
            <div className="detail-grid">
              <div className="detail-row">
                <label>Driver Hours</label>
                <span>{booking.driver_hours}</span>
              </div>
              <div className="detail-row">
                <label>Driver KM</label>
                <span>{booking.driver_km}</span>
              </div>
              <div className="detail-row">
                <label>Start KM</label>
                <span>{booking.start_km}</span>
              </div>
              <div className="detail-row">
                <label>End KM</label>
                <span>{booking.end_km}</span>
              </div>
              <div className="detail-row">
                <label>Total KM</label>
                <span>{booking.total_km}</span>
              </div>
              <div className="detail-row">
                <label>Toll</label>
                <span>₹{booking.toll}</span>
              </div>
              <div className="detail-row">
                <label>Parking</label>
                <span>₹{booking.parking}</span>
              </div>
              <div className="detail-row">
                <label>Amount</label>
                <span className="fw-bold" style={{ color: '#2ecc71' }}>₹{booking.amount}</span>
              </div>
            </div>
          </div>

          <div className="detail-section">
            <h2>Driver payment</h2>
            <div className="detail-grid">
              <div className="detail-row">
                <label>Status</label>
                <span className="badge" style={{ backgroundColor: String(booking.driver_payment_status || '').toLowerCase() === 'paid' ? '#2ecc71' : '#e67e22' }}>
                  {String(booking.driver_payment_status || '').toLowerCase() === 'paid' ? 'Paid' : 'Unpaid'}
                </span>
              </div>
              {booking.driver_paid_at && (
                <div className="detail-row">
                  <label>Paid at</label>
                  <span>{new Date(booking.driver_paid_at).toLocaleString()}</span>
                </div>
              )}
              {booking.assignedDriver?.driver_name && (
                <div className="detail-row">
                  <label>Pay to</label>
                  <span>{booking.assignedDriver.driver_name}</span>
                </div>
              )}
            </div>
            <button
              onClick={async () => {
                const paid = String(booking.driver_payment_status || '').toLowerCase() === 'paid'
                try {
                  await API.updateBookingPayment(booking.booking_id, { paid: !paid })
                  loadBooking()
                } catch (err) {
                  alert(err.message)
                }
              }}
              className="btn-primary"
              style={{ marginTop: '12px', backgroundColor: String(booking.driver_payment_status || '').toLowerCase() === 'paid' ? '#e67e22' : '#2ecc71' }}
            >
              {String(booking.driver_payment_status || '').toLowerCase() === 'paid' ? 'Mark unpaid' : 'Mark driver paid'}
            </button>
          </div>

          <div className="detail-section">
            <h2>Assignment</h2>
            {booking.assigned_driver_id ? (
              <div className="detail-grid">
                <div className="detail-row">
                  <label>Assigned Driver</label>
                  <span>{booking.assignedDriver?.driver_name}</span>
                </div>
                <div className="detail-row">
                  <label>Assigned At</label>
                  <span>{booking.assigned_at ? new Date(booking.assigned_at).toLocaleString() : '-'}</span>
                </div>
                <div className="detail-row">
                  <label>WhatsApp</label>
                  <span>{booking.whatsapp_message_status === 'sent' ? 'Sent' : booking.whatsapp_message_status === 'replaced' ? 'Reassigned' : 'Not sent yet'}</span>
                </div>
              </div>
            ) : (
              <p className="text-muted">Not assigned yet</p>
            )}
            {booking.assigned_driver_id && booking.whatsapp_message_status !== 'sent' && booking.status !== 'Cancelled' && (
              <p className="text-muted" style={{ marginTop: '12px' }}>The driver has not received this duty on WhatsApp yet.</p>
            )}
            {booking.status === 'Cancelled' && booking.assigned_driver_id && (
              <p className="text-muted" style={{ marginTop: '12px' }}>This booking is cancelled and {booking.assignedDriver?.driver_name || 'the driver'} is still attached. Reassign to put the duty back on a driver. Both drivers get a WhatsApp.</p>
            )}
            {booking.status !== 'Completed' && (
              <div style={{ display: 'flex', gap: '10px', marginTop: '16px', flexWrap: 'wrap' }}>
                {booking.assigned_driver_id && booking.status !== 'Cancelled' && (
                  <button onClick={handleResend} className="btn-primary">Resend WhatsApp</button>
                )}
                <button onClick={() => setAssignmentModal(true)} className="btn-primary">
                  {booking.assigned_driver_id ? 'Reassign' : 'Assign Now'}
                </button>
                {booking.assigned_driver_id && (
                  <button onClick={handleUnassign} className="btn-secondary">Remove driver</button>
                )}
              </div>
            )}
          </div>

          {booking.remarks && (
            <div className="detail-section">
              <h2>Remarks</h2>
              <p>{booking.remarks}</p>
            </div>
          )}
        </div>

        {/* Assignment Modal */}
        {assignmentModal && (
          <div className="modal-overlay">
            <div className="modal-content">
              <h2>{booking.assigned_driver_id ? 'Reassign this duty' : 'Assign Booking to Driver'}</h2>
              <p style={{ marginBottom: '20px', color: '#666' }}>
                Booking: {booking.source_booking_id}
                {booking.assigned_driver_id ? `. ${booking.assignedDriver?.driver_name || 'The current driver'} will be told this duty is no longer theirs.` : ''}
              </p>
              
              <div style={{ marginBottom: '20px' }}>
                <label style={{ display: 'block', marginBottom: '10px', fontWeight: 'bold' }}>Select Driver</label>
                <select 
                  value={selectedDriver?.driver_id || ''} 
                  onChange={(e) => {
                    const driver = drivers.find(d => d.driver_id === e.target.value)
                    setSelectedDriver(driver)
                  }}
                  style={{
                    width: '100%',
                    padding: '10px',
                    borderRadius: '4px',
                    border: '1px solid #ddd',
                    fontSize: '14px'
                  }}
                >
                  <option value="">-- Select a driver --</option>
                  {drivers.map(driver => (
                    <option key={driver.driver_id} value={driver.driver_id}>
                      {driver.driver_name} ({driver.whatsapp_number}){driver.driver_id === booking.assigned_driver_id ? ' — current' : ''}
                    </option>
                  ))}
                </select>
              </div>

              <div style={{ marginBottom: '20px' }}>
                <label style={{ display: 'block', marginBottom: '10px', fontWeight: 'bold' }}>Notes (Optional)</label>
                <textarea 
                  value={assignmentNotes}
                  onChange={(e) => setAssignmentNotes(e.target.value)}
                  placeholder="Add any notes for the driver..."
                  style={{
                    width: '100%',
                    padding: '10px',
                    borderRadius: '4px',
                    border: '1px solid #ddd',
                    fontSize: '14px',
                    minHeight: '80px',
                    fontFamily: 'inherit'
                  }}
                />
              </div>

              <div style={{ marginBottom: '20px' }}>
                <label style={{ display: 'flex', alignItems: 'center', cursor: 'pointer' }}>
                  <input 
                    type="checkbox" 
                    checked={sendMessage}
                    onChange={(e) => setSendMessage(e.target.checked)}
                    style={{ marginRight: '10px' }}
                  />
                  {booking.assigned_driver_id
                    ? 'Send WhatsApp: tell the current driver the duty is off them, and send the trip to the new driver'
                    : 'Send WhatsApp message to driver after assignment'}
                </label>
              </div>

              <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end' }}>
                <button 
                  onClick={() => {
                    setAssignmentModal(false)
                    setSelectedDriver(null)
                    setAssignmentNotes('')
                  }}
                  className="btn-secondary"
                  disabled={assigning}
                >
                  Cancel
                </button>
                <button 
                  onClick={handleAssign}
                  className="btn-primary"
                  disabled={assigning || !selectedDriver}
                >
                  {assigning ? 'Saving...' : (booking.assigned_driver_id ? 'Reassign' : 'Assign')}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default BookingDetailPage
