import React, { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import Navigation from '../components/Navigation'
import { API } from '../services/api'

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
      await API.createAssignment({
        booking_id: booking.booking_id,
        driver_id: selectedDriver.driver_id,
        assignment_notes: assignmentNotes,
        send_message_now: sendMessage
      })
      setAssignmentModal(false)
      loadBooking()
      alert('Booking assigned successfully!')
    } catch (err) {
      alert('Failed to assign: ' + err.message)
    } finally {
      setAssigning(false)
    }
  }

  const handleUpdateStatus = async (newStatus) => {
    if (!window.confirm(`Are you sure you want to change status to ${newStatus}?`)) return
    
    try {
      await API.updateBookingStatus(bookingId, newStatus)
      loadBooking()
      alert(`Booking ${newStatus} successfully!`)
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
                <span>{new Date(booking.trip_date).toLocaleDateString()}</span>
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
            <h2>Assignment</h2>
            {booking.assigned_driver_id ? (
              <div className="detail-grid">
                <div className="detail-row">
                  <label>Assigned Driver</label>
                  <span>{booking.assignedDriver?.driver_name}</span>
                </div>
                <div className="detail-row">
                  <label>Assigned At</label>
                  <span>{new Date(booking.assigned_at).toLocaleString()}</span>
                </div>
              </div>
            ) : (
              <p className="text-muted">Not assigned yet</p>
            )}
            {booking.status === 'Unassigned' && (
              <button onClick={() => setAssignmentModal(true)} className="btn-primary">Assign Now</button>
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
              <h2>Assign Booking to Driver</h2>
              <p style={{ marginBottom: '20px', color: '#666' }}>Booking: {booking.source_booking_id}</p>
              
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
                      {driver.driver_name} ({driver.whatsapp_number})
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
                  Send WhatsApp message to driver after assignment
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
                  {assigning ? 'Assigning...' : 'Assign'}
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
