import React, { useState, useEffect } from 'react'
import Navigation from '../components/Navigation'
import { API } from '../services/api'
import { QRCodeSVG } from 'qrcode.react'

const WhatsAppSettings = () => {
    const [status, setStatus] = useState(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)

    const fetchStatus = async () => {
        try {
            const data = await API.getWhatsappStatus()
            setStatus(data)
            setError(null)
        } catch (err) {
            console.error('Failed to fetch WhatsApp status:', err)
            setError('Could not reach the WhatsApp linker.')
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        fetchStatus()
        const interval = setInterval(fetchStatus, 3000)
        return () => clearInterval(interval)
    }, [])

    return (
        <div>
            <Navigation />
            <div className="container">
                <div className="page-header">
                    <h1>Link WhatsApp</h1>
                    <p className="subtitle">Scan once to connect your WhatsApp to this site. You do not pick a driver here. After it says Connected, assigning a booking sends the message from your account.</p>
                </div>

                {loading && !status ? (
                    <div className="card text-center">
                        <p className="loading">Checking WhatsApp status...</p>
                    </div>
                ) : error ? (
                    <div className="card" style={{ backgroundColor: '#f8d7da', color: '#721c24' }}>
                        <h3>Connection error</h3>
                        <p>{error}</p>
                        <button onClick={fetchStatus} className="btn-secondary" style={{ marginTop: '10px' }}>Retry</button>
                    </div>
                ) : (
                    <div className="settings-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '20px' }}>
                        <div className="card">
                            <h3>Connection status</h3>
                            <div style={{ margin: '20px 0' }}>
                                <div style={{ display: 'flex', alignItems: 'center', marginBottom: '10px' }}>
                                    <span style={{
                                        display: 'inline-block',
                                        width: '12px',
                                        height: '12px',
                                        borderRadius: '50%',
                                        backgroundColor: status?.isReady ? '#2ecc71' : '#e67e22',
                                        marginRight: '10px'
                                    }}></span>
                                    <strong style={{ fontSize: '1.2rem' }}>
                                        {status?.isReady ? 'Connected' : 'Scan to connect'}
                                    </strong>
                                </div>
                            </div>

                            {status?.isReady ? (
                                <div style={{ padding: '15px', backgroundColor: '#d4edda', borderRadius: '8px', border: '1px solid #c3e6cb', color: '#155724' }}>
                                    <p>Your WhatsApp is linked. When you assign a driver to a booking, the trip message goes from this account.</p>
                                </div>
                            ) : (
                                <div style={{ padding: '15px', backgroundColor: '#fff3cd', borderRadius: '8px', border: '1px solid #ffeeba', color: '#856404' }}>
                                    <p>On your phone: WhatsApp → Menu → Linked devices → Link a device. Then scan the QR on the right. No booking is required.</p>
                                </div>
                            )}
                            <p className="text-muted" style={{ marginTop: '16px' }}>
                                On the free host the site can sleep. If this page asks you to scan again, scan once more.
                            </p>
                        </div>

                        {!status?.isReady && (
                            <div className="card text-center" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                                <h3>Login QR</h3>
                                <p style={{ marginBottom: '15px' }}>This QR connects your account. It is not a chat with a driver.</p>
                                {status?.qr ? (
                                    <div style={{ background: 'white', padding: '20px', borderRadius: '12px', boxShadow: '0 4px 12px rgba(0,0,0,0.1)', border: '1px solid #eee' }}>
                                        <QRCodeSVG value={status.qr} size={256} />
                                    </div>
                                ) : (
                                    <div style={{ padding: '40px', background: '#f9f9f9', borderRadius: '8px', border: '1px dashed #ccc' }}>
                                        <p>{status?.message || 'Generating QR code…'}</p>
                                        <small>This can take up to a minute after the site wakes.</small>
                                    </div>
                                )}
                                <p style={{ marginTop: '15px', fontSize: '0.9rem', color: '#666' }}>
                                    This page refreshes by itself after you scan.
                                </p>
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    )
}

export default WhatsAppSettings
