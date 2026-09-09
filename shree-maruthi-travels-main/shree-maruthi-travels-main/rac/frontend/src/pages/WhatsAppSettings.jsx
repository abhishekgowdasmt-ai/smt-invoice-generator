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
                    <h1>Send WhatsApp</h1>
                    <p className="subtitle">This is not a login QR. The website does not connect to your WhatsApp account. Each QR opens one chat, from your phone, to one driver.</p>
                </div>

                <div className="card" style={{ marginBottom: '20px', background: '#eef6ff', border: '1px solid #c5ddf5' }}>
                    <h3 style={{ marginBottom: '8px' }}>Why a driver is required</h3>
                    <p style={{ marginBottom: '10px' }}>
                        WhatsApp Web “link a device” would keep the office WhatsApp logged in on the server. That cannot stay running on this free host, so we do not do it.
                    </p>
                    <p>
                        Your WhatsApp is already on your phone. Pick the driver (or type a number), then scan. The QR is the chat with that person. Change driver, get a new QR, send again.
                    </p>
                </div>

                {error && <div className="alert alert-error" style={{ marginBottom: '20px' }}>{error}</div>}

                <div className="settings-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '20px' }}>
                    <div className="card">
                        <h3>1. Who should receive it?</h3>
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
                    </div>

                    <div className="card text-center" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                        <h3>2. Send from your phone</h3>
                        {link ? (
                            <>
                                <p style={{ marginBottom: '15px' }}>
                                    Scan with your phone camera or WhatsApp, then tap Send. Or open the chat on this computer.
                                </p>
                                <div style={{ background: 'white', padding: '20px', borderRadius: '12px', boxShadow: '0 4px 12px rgba(0,0,0,0.1)', border: '1px solid #eee' }}>
                                    <QRCodeSVG value={link} size={256} />
                                </div>
                                <a
                                    className="btn-primary"
                                    href={link}
                                    target="_blank"
                                    rel="noreferrer"
                                    style={{ display: 'inline-block', textDecoration: 'none', marginTop: '16px' }}
                                >
                                    Open WhatsApp
                                </a>
                                {selected?.driver_name && (
                                    <p className="text-muted" style={{ marginTop: '12px' }}>
                                        Chat: {selected.driver_name}
                                    </p>
                                )}
                            </>
                        ) : (
                            <div style={{ padding: '40px', background: '#f9f9f9', borderRadius: '8px', border: '1px dashed #ccc' }}>
                                <p>No QR yet — it would not know who to message.</p>
                                <p className="text-muted" style={{ marginTop: '8px' }}>Select a driver on the left, or type their WhatsApp number.</p>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    )
}

export default WhatsAppSettings
