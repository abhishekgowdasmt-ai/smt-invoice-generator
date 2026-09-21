import { useEffect, useRef, useState } from 'react'
import Navigation from '../components/Navigation'
import { API } from '../services/api'

const statusLabel = (status) => {
  if (status === 'PUBLISHED') return 'OCR → Published'
  if (status === 'DUPLICATE_IMAGE') return 'OCR → Duplicate image'
  if (status === 'DUPLICATE_BOOKING') return 'OCR → Duplicate booking'
  if (status === 'REVIEW_REQUIRED') return 'OCR → Review Required'
  if (status === 'FAILED') return 'OCR → Failed'
  if (status === 'PROCESSING') return 'OCR → Processing'
  if (status === 'RECEIVED') return 'Uploaded → queued'
  return status || 'queued'
}

const BookingOcrPage = () => {
  const [status, setStatus] = useState(null)
  const [records, setRecords] = useState([])
  const [reviews, setReviews] = useState([])
  const [error, setError] = useState('')
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState('')
  const [localFiles, setLocalFiles] = useState([])
  const fileRef = useRef(null)

  const refresh = () => {
    API.getOcrStatus()
      .then((data) => {
        setStatus(data)
        setRecords(data.records || [])
        setReviews(data.reviews || [])
        setError('')
      })
      .catch((err) => setError(err.message))
  }

  useEffect(() => {
    refresh()
    const timer = setInterval(refresh, 4000)
    return () => clearInterval(timer)
  }, [])

  const sendFiles = async (fileList) => {
    const files = Array.from(fileList || [])
    if (!files.length) return
    setUploading(true)
    setError('')
    setProgress(`Uploading 0/${files.length}`)
    setLocalFiles(files.map((file) => file.name))
    try {
      await API.uploadOcrImages(files)
      setProgress(`Uploaded ${files.length}/${files.length} · processing`)
      refresh()
    } catch (err) {
      setError(err.message)
    } finally {
      setUploading(false)
    }
  }

  const onDrop = (event) => {
    event.preventDefault()
    sendFiles(event.dataTransfer.files)
  }

  const reviewFields = (review) => {
    const payload = review.payload || {}
    const form = document.getElementById(`review-${review.id}`)
    const data = { ...payload, ingest_record_id: payload.ingest_record_id || '' }
    if (form) {
      form.querySelectorAll('input[name]').forEach((el) => {
        data[el.name] = el.value
      })
    }
    return data
  }

  const runReview = async (review, action) => {
    try {
      await API.ocrReviewAction(review.id, action, reviewFields(review))
      refresh()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div>
      <Navigation />
      <div className="container">
        <h1>RAC Booking OCR</h1>
        <p className="text-muted" style={{ marginBottom: '16px' }}>
          Drop booking-table screenshots. Fields are extracted automatically. Do not type a new booking.
        </p>
        {status && (
          <div className="result-stats" style={{ marginBottom: '16px' }}>
            <div className="stat"><span className="label">Images received</span><span className="value">{status.received ?? status.uploaded ?? 0}</span></div>
            <div className="stat success"><span className="label">Published</span><span className="value">{status.published ?? 0}</span></div>
            <div className="stat"><span className="label">Duplicate images</span><span className="value">{status.duplicate_image ?? 0}</span></div>
            <div className="stat"><span className="label">Duplicate bookings</span><span className="value">{status.duplicate_booking ?? 0}</span></div>
            <div className="stat"><span className="label">Review required</span><span className="value">{status.needs_review ?? 0}</span></div>
            <div className="stat error"><span className="label">Failed</span><span className="value">{status.failed ?? 0}</span></div>
          </div>
        )}
        <div className="upload-box" onDragOver={(event) => event.preventDefault()} onDrop={onDrop}>
          <label className="file-input-label">
            <input ref={fileRef} type="file" multiple accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp" onChange={(event) => sendFiles(event.target.files)} />
            <div className="file-input-placeholder">
              <p>DROP BOOKING IMAGES HERE</p>
              <p className="text-small">JPG JPEG PNG WebP · multiple files · no PDFs</p>
              {uploading && <p>{progress || 'Uploading…'}</p>}
            </div>
          </label>
          <button type="button" className="btn btn-primary" style={{ marginTop: '12px' }} onClick={() => fileRef.current && fileRef.current.click()} disabled={uploading}>
            {uploading ? (progress || 'Uploading…') : 'Upload images'}
          </button>
        </div>
        {error && <div className="alert alert-error" style={{ marginTop: '12px' }}>{error}</div>}
        <ul style={{ marginTop: '16px', listStyle: 'none' }}>
          {localFiles.map((name) => {
            const match = records.find((row) => row.source_file_name === name)
            return (
              <li key={name} className="file-selected" style={{ marginBottom: '8px' }}>
                <p>{name}</p>
                <span>{statusLabel(match?.status)}{match?.error ? ` · ${match.error}` : ''}</span>
              </li>
            )
          })}
        </ul>
        <h2 style={{ marginTop: '24px' }}>Review required</h2>
        <p className="text-muted" style={{ marginBottom: '8px' }}>
          If a field is empty, type it from the screenshot. Cab is required. Then Approve &amp; Publish.
        </p>
        {error && <div className="alert alert-error" style={{ marginTop: '12px' }}>{error}</div>}
        {(reviews || []).length === 0 && <p className="text-muted">No conflicts waiting for review.</p>}
        {(reviews || []).map((review) => {
          const payload = review.payload || {}
          const img = (review.image_path || '').split(/[/\\]/).pop()
          return (
            <article key={review.id} className="ocr-review-card" id={`review-${review.id}`}>
              {img ? <img src={`/api/v1/bookings/ocr-image/${encodeURIComponent(img)}`} alt="source" /> : null}
              <div>
                <p className="reason">{review.reason || ''}</p>
                <label>Booking ID <input name="booking_id" defaultValue={payload.booking_id || ''} /></label>
                <label>Type <input name="booking_type" defaultValue={payload.booking_type || ''} /></label>
                <label>Cab <input name="cab_type" defaultValue={payload.cab_type || ''} /></label>
                <label>Date <input name="trip_date" defaultValue={payload.trip_date || ''} /></label>
                <label>Time <input name="trip_time" defaultValue={payload.trip_time || ''} /></label>
                <label>Address <input name="planned_start_address" defaultValue={payload.planned_start_address || ''} /></label>
                <input type="hidden" name="ingest_record_id" defaultValue={payload.ingest_record_id || ''} />
                <input type="hidden" name="source" defaultValue={payload.source || ''} />
                <button type="button" onClick={() => runReview(review, 'approve')}>Approve &amp; Publish</button>
                <button type="button" className="ghost" onClick={() => runReview(review, 'edit')}>Edit</button>
                <button type="button" className="ghost" onClick={() => runReview(review, 'reject')}>Reject</button>
              </div>
            </article>
          )
        })}
        <h2 style={{ marginTop: '24px' }}>Recent processing</h2>
        <table className="table">
          <thead>
            <tr>
              <th>Filename</th><th>Source</th><th>Booking ID</th><th>Date</th><th>Status</th><th>Reason</th><th>Timestamp</th>
            </tr>
          </thead>
          <tbody>
            {records.map((row) => (
              <tr key={row.id}>
                <td>{row.source_file_name}</td>
                <td>{row.source}</td>
                <td>{row.booking_id}</td>
                <td>{row.booking_date}</td>
                <td>{row.status}</td>
                <td>{row.error}</td>
                <td>{row.processed_at || row.created_at}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default BookingOcrPage
