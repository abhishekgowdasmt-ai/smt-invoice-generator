import React, { useState, useEffect } from 'react'
import Navigation from '../components/Navigation'
import { API } from '../services/api'
import { QRCodeSVG } from 'qrcode.react'

const waLink = (phone, body) => {
    const digits = String(phone || '').replace(/\D/g, '')
    const full = digits.length === 10 ? `91${digits}` : digits
    if (!full) return ''
    return `https://wa.me/${full}?text=${encodeURIComponent(body || '')}`
}

const WhatsAppSettings = () => {
    const [drivers, setDrivers] = useState([])
    const [driverId, setDriverId] = useState('')
    const [phone, setPhone] = useState('')
    const [message, setMessage] = useState('Namaste, this is Shree Maruthi Travels. You have a new trip assignment. Please confirm.')
    const [error, setError] = useState(null)

    useEffect(() => {
        API.getDrivers({ active_only: true, limit: 200 })
            .then((res) => setDrivers(res.data || []))
            .catch((err) => setError(err.message))
    }, [])

    const selected = drivers.find((row) => row.driver_id === driverId)
    const link = waLink(phone || selected?.whatsapp_number, message)

    const chooseDriver = (id) => {
        setDriverId(id)
        const row = drivers.find((item) => item.driver_id === id)
        if (row?.whatsapp_number) setPhone(row.whatsapp_number)
    }

    return (
        <div>
            <Navigation />
            <div className="container">
                <div className="page-header">
                    <h1>WhatsApp</h1>
                    <p className="subtitle">Scan the QR with your phone, or tap Open WhatsApp. The message sends from your WhatsApp, not from the server.</p>
                </div>

                {error && <div className="alert alert-error" style={{ marginBottom: '20px' }}>{error}</div>}

                <div className="settings-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '20px' }}>
                    <div className="card">
                        <h3>Write message</h3>
                        <div className="form-group">
                            <label>Driver</label>
                            <select className="input" value={driverId} onChange={(e) => chooseDriver(e.target.value)}>
                                <option value="">Select driver</option>
                                {drivers.map((driver) => (
                                    <option key={driver.driver_id} value={driver.driver_id}>
                                        {driver.driver_name} ({driver.whatsapp_number})
                                    </option>
                                ))}
                            </select>
                        </div>
                        <div className="form-group">
                            <label>WhatsApp number</label>
                            <input
                                className="input"
                                value={phone}
                                onChange={(e) => setPhone(e.target.value)}
                                placeholder="9198XXXXXXXX"
                            />
                        </div>
                        <div className="form-group">
                            <label>Message</label>
                            <textarea
                                className="input"
                                rows="8"
                                value={message}
                                onChange={(e) => setMessage(e.target.value)}
                            />
                        </div>
                        {link ? (
                            <a className="btn-primary" href={link} target="_blank" rel="noreferrer" style={{ display: 'inline-block', textDecoration: 'none' }}>
                                Open WhatsApp
                            </a>
                        ) : (
                            <p className="text-muted">Enter a driver number to generate the QR.</p>
                        )}
                    </div>

                    <div className="card text-center" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                        <h3>Scan QR code</h3>
                        {link ? (
                            <>
                                <p style={{ marginBottom: '15px' }}>Open WhatsApp on your phone → Linked devices is not needed. Scan this code to open the chat with the message filled in. Then tap Send.</p>
                                <div style={{ background: 'white', padding: '20px', borderRadius: '12px', boxShadow: '0 4px 12px rgba(0,0,0,0.1)', border: '1px solid #eee' }}>
                                    <QRCodeSVG value={link} size={256} />
                                </div>
                            </>
                        ) : (
                            <div style={{ padding: '40px', background: '#f9f9f9', borderRadius: '8px', border: '1px dashed #ccc' }}>
                                <p>Select a driver or type a number to show the QR code.</p>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    )
}

export default WhatsAppSettings
