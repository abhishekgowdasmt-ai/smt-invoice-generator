import React, { useState, useEffect } from 'react'
import Navigation from '../components/Navigation'
import { API } from '../services/api'

const DriversPage = () => {
  const [drivers, setDrivers] = useState([])
  const [loading, setLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [editingDriver, setEditingDriver] = useState(null)
  const [filters, setFilters] = useState({ page: 1, limit: 50, active_only: true, search: '' })
  const [pagination, setPagination] = useState({ page: 1, limit: 50, total: 0 })
  const [formData, setFormData] = useState({
    driver_name: '',
    whatsapp_number: '',
    alternate_number: '',
    vehicle_number: '',
    vehicle_type: '',
    home_area: '',
    notes: ''
  })

  useEffect(() => {
    loadDrivers()
  }, [filters.page, filters.active_only])

  const loadDrivers = async () => {
    setLoading(true)
    try {
      const params = {
        page: filters.page,
        limit: filters.limit,
        active_only: filters.active_only,
        ...(filters.search && { search: filters.search })
      }
      const response = await API.getDrivers(params)
      setDrivers(response.data)
      setPagination(response.pagination)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    try {
      if (editingDriver) {
        await API.updateDriver(editingDriver.driver_id, formData)
      } else {
        await API.createDriver(formData)
      }
      setShowModal(false)
      setEditingDriver(null)
      setFormData({
        driver_name: '',
        whatsapp_number: '',
        alternate_number: '',
        vehicle_number: '',
        vehicle_type: '',
        home_area: '',
        notes: ''
      })
      loadDrivers()
    } catch (err) {
      alert(`Error: ${err.message}`)
    }
  }

  const handleEdit = (driver) => {
    setEditingDriver(driver)
    setFormData({
      driver_name: driver.driver_name,
      whatsapp_number: driver.whatsapp_number,
      alternate_number: driver.alternate_number || '',
      vehicle_number: driver.vehicle_number || '',
      vehicle_type: driver.vehicle_type || '',
      home_area: driver.home_area || '',
      notes: driver.notes || ''
    })
    setShowModal(true)
  }

  const handleToggleStatus = async (driver) => {
    try {
      await API.updateDriverStatus(driver.driver_id, { active_status: !driver.active_status })
      loadDrivers()
    } catch (err) {
      alert(`Error: ${err.message}`)
    }
  }

  return (
    <div>
      <Navigation />
      <div className="container">
        <div className="page-header">
          <h1>Drivers Master</h1>
          <button onClick={() => { setEditingDriver(null); setFormData({...formData}); setShowModal(true) }} className="btn-primary">
            + Add Driver
          </button>
        </div>

        <div className="filters">
          <div className="filter-row">
            <input
              type="text"
              placeholder="Search by name, vehicle, WhatsApp..."
              value={filters.search}
              onChange={(e) => setFilters({ ...filters, search: e.target.value })}
              className="input"
            />
            <label className="checkbox">
              <input
                type="checkbox"
                checked={filters.active_only}
                onChange={(e) => setFilters({ ...filters, active_only: e.target.checked, page: 1 })}
              />
              Show Active Only
            </label>
          </div>
        </div>

        {loading ? (
          <p className="loading">Loading...</p>
        ) : (
          <div className="table-responsive">
            <table className="table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>WhatsApp</th>
                  <th>Vehicle</th>
                  <th>Vehicle Type</th>
                  <th>Home Area</th>
                  <th>Assignments</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {drivers.map((driver) => (
                  <tr key={driver.driver_id}>
                    <td className="fw-600">{driver.driver_name}</td>
                    <td>{driver.whatsapp_number}</td>
                    <td>{driver.vehicle_number}</td>
                    <td>{driver.vehicle_type}</td>
                    <td>{driver.home_area}</td>
                    <td>{driver.total_assignments}</td>
                    <td>
                      <span className="badge" style={{ backgroundColor: driver.active_status ? '#2ecc71' : '#95a5a6' }}>
                        {driver.active_status ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td>
                      <button onClick={() => handleEdit(driver)} className="btn-small">Edit</button>
                      <button
                        onClick={() => handleToggleStatus(driver)}
                        className="btn-small"
                        style={{ backgroundColor: driver.active_status ? '#e74c3c' : '#2ecc71' }}
                      >
                        {driver.active_status ? 'Deactivate' : 'Activate'}
                      </button>
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
        )}

        {showModal && (
          <div className="modal">
            <div className="modal-content">
              <div className="modal-header">
                <h2>{editingDriver ? 'Edit Driver' : 'Add Driver'}</h2>
                <button onClick={() => setShowModal(false)} className="close-btn">×</button>
              </div>
              <form onSubmit={handleSubmit} className="form">
                <div className="form-group">
                  <label>Driver Name *</label>
                  <input
                    type="text"
                    value={formData.driver_name}
                    onChange={(e) => setFormData({ ...formData, driver_name: e.target.value })}
                    required
                    className="input"
                  />
                </div>
                <div className="form-group">
                  <label>WhatsApp Number * (E.164)</label>
                  <input
                    type="tel"
                    value={formData.whatsapp_number}
                    onChange={(e) => setFormData({ ...formData, whatsapp_number: e.target.value })}
                    placeholder="+919876543210"
                    required
                    className="input"
                  />
                </div>
                <div className="form-group">
                  <label>Alternate Number</label>
                  <input
                    type="tel"
                    value={formData.alternate_number}
                    onChange={(e) => setFormData({ ...formData, alternate_number: e.target.value })}
                    className="input"
                  />
                </div>
                <div className="form-group">
                  <label>Vehicle Number</label>
                  <input
                    type="text"
                    value={formData.vehicle_number}
                    onChange={(e) => setFormData({ ...formData, vehicle_number: e.target.value })}
                    className="input"
                  />
                </div>
                <div className="form-group">
                  <label>Vehicle Type</label>
                  <select
                    value={formData.vehicle_type}
                    onChange={(e) => setFormData({ ...formData, vehicle_type: e.target.value })}
                    className="input"
                  >
                    <option value="">Select</option>
                    <option value="SEDAN">SEDAN</option>
                    <option value="SUV">SUV</option>
                    <option value="TEMPO">TEMPO</option>
                    <option value="OTHER">OTHER</option>
                  </select>
                </div>
                <div className="form-group">
                  <label>Home Area</label>
                  <input
                    type="text"
                    value={formData.home_area}
                    onChange={(e) => setFormData({ ...formData, home_area: e.target.value })}
                    className="input"
                  />
                </div>
                <div className="form-group">
                  <label>Notes</label>
                  <textarea
                    value={formData.notes}
                    onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                    className="input"
                    rows="3"
                  />
                </div>
                <div className="modal-buttons">
                  <button type="submit" className="btn-primary">Save</button>
                  <button type="button" onClick={() => setShowModal(false)} className="btn-secondary">Cancel</button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default DriversPage
