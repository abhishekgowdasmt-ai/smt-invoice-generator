import React, { useState, useEffect } from 'react'
import Navigation from '../components/Navigation'
import { API } from '../services/api'
import { QRCodeSVG } from 'qrcode.react'

const AssignmentPage = () => {
  const [unassigned, setUnassigned] = useState([])
  const [drivers, setDrivers] = useState([])
  const [selectedBooking, setSelectedBooking] = useState(null)
  const [selectedDriver, setSelectedDriver] = useState(null)
  const [notes, setNotes] = useState('')
  const [sendMessage, setSendMessage] = useState(true)
  const [loading, setLoading] = useState(true)
  const [assigning, setAssigning] = useState(false)
  const [success, setSuccess] = useState(null)
  const [waDraft, setWaDraft] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      const bookingsResp = await API.getBookings({ status: 'Unassigned', limit: 100 })
      setUnassigned(bookingsResp.data)

      const driversResp = await API.getDrivers({ active_only: true, limit: 100 })
      setDrivers(driversResp.data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleAssign = async (e) => {
    e.preventDefault()
    if (!selectedBooking || !selectedDriver) {
      setError('Please select a booking and driver')
      return
    }

    setAssigning(true)
    try {
      const result = await API.createAssignment({
        booking_id: selectedBooking.booking_id,
        driver_id: selectedDriver.driver_id,
        assignment_notes: notes,
        send_message_now: sendMessage
      })
      setSuccess(`${selectedBooking.source_booking_id} assigned to ${selectedDriver.driver_name}`)
      if (sendMessage && result.wa_link) {
        setWaDraft(result)
        window.open(result.wa_link, '_blank', 'noopener')
      } else {
        setWaDraft(null)
      }
      setSelectedBooking(null)
      setSelectedDriver(null)
      setNotes('')
      loadData()
    } catch (err) {
      setError(err.message)
    } finally {
      setAssigning(false)
    }
  }

  return (
    <div>
      <Navigation />
      <div className="container">
        <h1>Assign Bookings to Drivers</h1>

        {error && <div className="alert alert-error" style={{ marginBottom: '20px' }}>{error}</div>}
        {success && <div className="alert alert-success" style={{ marginBottom: '20px' }}>{success}</div>}
        {waDraft?.wa_link && (
          <div className="card" style={{ marginBottom: '20px', display: 'flex', gap: '24px', alignItems: 'center', flexWrap: 'wrap' }}>
            <div>
              <h3>Send WhatsApp to {waDraft.driver_name}</h3>
              <p>WhatsApp should open with the trip message. If it did not, tap the button or scan this QR with your phone, then tap Send.</p>
              <a className="btn-primary" href={waDraft.wa_link} target="_blank" rel="noreferrer" style={{ display: 'inline-block', marginTop: '12px', textDecoration: 'none' }}>
                Open WhatsApp
              </a>
            </div>
            <div style={{ background: 'white', padding: '12px', borderRadius: '12px', border: '1px solid #eee' }}>
              <QRCodeSVG value={waDraft.wa_link} size={160} />
            </div>
          </div>
        )}

        {loading ? (
          <p className="loading">Loading...</p>
        ) : (
          <div className="assignment-layout">
            <div className="assignment-column">
              <h2>Unassigned Bookings ({unassigned.length})</h2>
              <div className="booking-list">
                {unassigned.length === 0 ? (
                  <p className="text-muted">No unassigned bookings</p>
                ) : (
                  <table className="table table-compact">
                    <thead>
                      <tr>
                        <th>Booking ID</th>
                        <th>Employee</th>
                        <th>Pickup</th>
                        <th>Time</th>
                      </tr>
                    </thead>
                    <tbody>
                      {unassigned.map((booking) => (
                        <tr
                          key={booking.booking_id}
                          onClick={() => setSelectedBooking(booking)}
                          className={selectedBooking?.booking_id === booking.booking_id ? 'selected' : ''}
                          style={{ cursor: 'pointer' }}
                        >
                          <td className="fw-600">{booking.source_booking_id}</td>
                          <td>{booking.employee_name}</td>
                          <td>{booking.planned_start}</td>
                          <td>{booking.pickup_time}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>

            <div className="assignment-column">
              {selectedBooking && (
                <>
                  <div className="selected-booking">
                    <h2>Selected Booking</h2>
                    <div className="booking-card">
                      <p><strong>Booking ID:</strong> {selectedBooking.source_booking_id}</p>
                      <p><strong>Employee:</strong> {selectedBooking.employee_name}</p>
                      <p><strong>Pickup:</strong> {selectedBooking.planned_start}</p>
                      <p><strong>Route:</strong> {selectedBooking.route_text?.substring(0, 100)}...</p>
                      <p><strong>Pickup Time:</strong> {selectedBooking.pickup_time}</p>
                      <p><strong>Amount:</strong> ₹{selectedBooking.amount}</p>
                    </div>
                  </div>

                  <div className="driver-selection">
                    <h2>Select Driver</h2>
                    <div className="driver-list">
                      {drivers.map((driver) => (
                        <div
                          key={driver.driver_id}
                          className={`driver-option ${selectedDriver?.driver_id === driver.driver_id ? 'selected' : ''}`}
                          onClick={() => setSelectedDriver(driver)}
                          style={{ cursor: 'pointer' }}
                        >
                          <div className="radio-circle"></div>
                          <div className="driver-info">
                            <p className="fw-600">{driver.driver_name}</p>
                            <p className="text-small">{driver.whatsapp_number} • {driver.vehicle_number} • {driver.vehicle_type}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  <form onSubmit={handleAssign} className="assignment-form">
                    <div className="form-group">
                      <label>Assignment Notes (optional)</label>
                      <textarea
                        value={notes}
                        onChange={(e) => setNotes(e.target.value)}
                        className="input"
                        rows="3"
                        placeholder="e.g., Morning shift, early pickup..."
                      />
                    </div>

                    <label className="checkbox">
                      <input
                        type="checkbox"
                        checked={sendMessage}
                        onChange={(e) => setSendMessage(e.target.checked)}
                      />
                      Send WhatsApp message now
                    </label>

                    <button type="submit" disabled={!selectedDriver || assigning} className="btn-primary">
                      {assigning ? 'Assigning...' : 'Confirm & Assign'}
                    </button>
                  </form>
                </>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default AssignmentPage
