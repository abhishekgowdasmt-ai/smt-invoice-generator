import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../App'
import Navigation from '../components/Navigation'
import { API } from '../services/api'

const UploadPage = () => {
  const { token } = useAuth()
  const [file, setFile] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const downloadTemplate = async () => {
    try {
      const response = await fetch('/api/v1/uploads/template.xlsx', {
        headers: { Authorization: `Bearer ${token}` }
      })
      if (!response.ok) throw new Error('Could not download template')
      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = 'smt-booking-template.xlsx'
      link.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      setError(err.message)
    }
  }

  const handleFileChange = (e) => {
    const selectedFile = e.target.files?.[0]
    if (selectedFile) {
      if (!['application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'application/vnd.ms-excel'].includes(selectedFile.type)) {
        setError('Only Excel files (.xlsx, .xls) are allowed')
        return
      }
      if (selectedFile.size > 10 * 1024 * 1024) {
        setError('File size must be less than 10 MB')
        return
      }
      setFile(selectedFile)
      setError(null)
    }
  }

  const handleUpload = async (e) => {
    e.preventDefault()
    if (!file) {
      setError('Please select a file')
      return
    }

    setUploading(true)
    try {
      const response = await API.uploadExcel(file)
      setResult(response)
      setFile(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setUploading(false)
    }
  }

  return (
    <div>
      <Navigation />
      <div className="container">
        <h1>Upload Excel Bookings</h1>
        <p className="text-muted" style={{ marginBottom: '16px' }}>
          Use the SMT column headers. Download a sample file if you are unsure.
          {' '}
          <button type="button" className="btn-secondary" onClick={downloadTemplate}>Download template</button>
        </p>

        <div className="upload-form">
          <div className="upload-box">
            {!file ? (
              <label className="file-input-label">
                <input type="file" onChange={handleFileChange} accept=".xlsx,.xls" />
                <div className="file-input-placeholder">
                  <p>📁 Drag & drop Excel file or click to choose</p>
                  <p className="text-small">Supported: .xlsx, .xls | Max size: 10 MB</p>
                </div>
              </label>
            ) : (
              <div className="file-selected">
                <p>📄 {file.name}</p>
                <button type="button" onClick={() => setFile(null)} className="btn-secondary">
                  Change File
                </button>
              </div>
            )}
          </div>

          {error && <div className="alert alert-error">{error}</div>}

          {file && (
            <button onClick={handleUpload} disabled={uploading} className="btn-primary">
              {uploading ? '⏳ Uploading...' : 'Upload'}
            </button>
          )}
        </div>

        {result && (
          <div className="upload-result">
            <div className="result-header">
              <h2>✅ Upload Result</h2>
              <p className="batch-id">Batch ID: {result.batch_id}</p>
            </div>

            <div className="result-stats">
              <div className="stat">
                <span className="label">Total Rows</span>
                <span className="value">{result.total_rows}</span>
              </div>
              <div className="stat success">
                <span className="label">Success</span>
                <span className="value">{result.success_rows}</span>
              </div>
              <div className="stat error">
                <span className="label">Failed</span>
                <span className="value">{result.failed_rows}</span>
              </div>
            </div>

            {result.errors && result.errors.length > 0 && (
              <div className="error-list">
                <h3>Failed Rows:</h3>
                <table className="table">
                  <thead>
                    <tr>
                      <th>Row</th>
                      <th>Booking ID</th>
                      <th>Error</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.errors.map((err, idx) => (
                      <tr key={idx} className="error-row">
                        <td>{err.row_number}</td>
                        <td>{err.booking_id}</td>
                        <td>{err.error}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            <div className="action-buttons">
              <Link to="/bookings" className="btn-primary">View Bookings</Link>
              <button onClick={() => { setResult(null); setFile(null) }} className="btn-secondary">
                New Upload
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default UploadPage
