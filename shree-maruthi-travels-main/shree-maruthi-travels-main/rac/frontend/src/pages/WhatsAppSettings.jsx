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
            setError('Could not connect to the WhatsApp service.')
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        fetchStatus()
        // Refresh status every 10 seconds to catch QR code generation
        const interval = setInterval(fetchStatus, 10000)
        return () => clearInterval(interval)
    }, [])

    return (
        <div>
            <Navigation />
            <div className="container">
                <div className="page-header">
                    <h1>📱 WhatsApp Configuration</h1>
                    <p className="subtitle">Manage your WhatsApp connection and authentication</p>
                </div>

                {loading && !status ? (
                    <div className="card text-center">
                        <p className="loading">Checking WhatsApp status...</p>
                    </div>
                ) : error ? (
                    <div className="card" style={{ backgroundColor: '#f8d7da', color: '#721c24' }}>
                        <h3>⚠️ Connection Error</h3>
                        <p>{error}</p>
                        <button onClick={fetchStatus} className="btn-secondary" style={{ marginTop: '10px' }}>Retry</button>
                    </div>
                ) : (
                    <div className="settings-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '20px' }}>
                        
                        <div className="card">
                            <h3>Connection Status</h3>
                            <div style={{ margin: '20px 0' }}>
                                <div style={{ display: 'flex', alignItems: 'center', marginBottom: '10px' }}>
                                    <span style={{ 
                                        display: 'inline-block', 
                                        width: '12px', 
                                        height: '12px', 
                                        borderRadius: '50%', 
                                        backgroundColor: status?.isReady ? '#2ecc71' : '#95a5a6',
                                        marginRight: '10px'
                                    }}></span>
                                    <strong style={{ fontSize: '1.2rem' }}>
                                        {status?.isReady ? 'Connected & Ready' : (status?.provider === 'none' ? 'Not connected' : 'Authentication Required')}
                                    </strong>
                                </div>
                                <p><strong>Current Provider:</strong> <code style={{ background: '#f0f0f0', padding: '2px 6px', borderRadius: '4px' }}>{status?.provider}</code></p>
                            </div>

                            {status?.isReady ? (
                                <div style={{ padding: '15px', backgroundColor: '#d4edda', borderRadius: '8px', border: '1px solid #c3e6cb', color: '#155724' }}>
                                    <p>✅ WhatsApp is successfully linked. Messages will be sent automatically to drivers when assigned.</p>
                                </div>
                            ) : status?.provider === 'none' ? (
                                <div style={{ padding: '15px', backgroundColor: '#eef2f7', borderRadius: '8px', border: '1px solid #d6dce5', color: '#334155' }}>
                                    <p>WhatsApp is turned off on this site. There is no QR code because no WhatsApp account is linked.</p>
                                    <p style={{ marginTop: '8px' }}>You can still assign drivers. Records save in Zoho Sheet. Message the driver from your phone if you need to notify them.</p>
                                </div>
                            ) : (
                                <div style={{ padding: '15px', backgroundColor: '#fff3cd', borderRadius: '8px', border: '1px solid #ffeeba', color: '#856404' }}>
                                    <p>⚠️ Device not linked. You need to scan the QR code to enable messaging.</p>
                                </div>
                            )}
                        </div>

                        {status?.provider === 'wwebjs' && !status?.isReady && (
                            <div className="card text-center" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                                <h3>Scan QR Code</h3>
                                <p style={{ marginBottom: '15px' }}>Open WhatsApp on your phone, go to <strong>Linked Devices</strong>, and scan this code:</p>
                                
                                {status?.qr ? (
                                    <div style={{ background: 'white', padding: '20px', borderRadius: '12px', boxShadow: '0 4px 12px rgba(0,0,0,0.1)', border: '1px solid #eee' }}>
                                        <QRCodeSVG value={status.qr} size={256} />
                                    </div>
                                ) : (
                                    <div style={{ padding: '40px', background: '#f9f9f9', borderRadius: '8px', border: '1px dashed #ccc' }}>
                                        <p>Generating QR code...</p>
                                        <small>This may take a minute on initial startup.</small>
                                    </div>
                                )}
                                
                                <p style={{ marginTop: '15px', fontSize: '0.9rem', color: '#666' }}>
                                    The status will update automatically once scanned.
                                </p>
                            </div>
                        )}

                        <div className="card">
                            <h3>Help & Troubleshooting</h3>
                            <ul style={{ paddingLeft: '20px', lineHeight: '1.6' }}>
                                <li>Automatic WhatsApp from this portal is not enabled (it needs extra paid services and a phone always online).</li>
                                <li>Assigning a booking still works and is stored in Zoho Sheet.</li>
                                <li>To notify a driver, open WhatsApp on your phone and message their number from the Drivers page.</li>
                            </ul>
                        </div>
                    </div>
                )}
            </div>
        </div>
    )
}

export default WhatsAppSettings
