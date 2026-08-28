import { useAuth } from '../App'
import { Link, useNavigate } from 'react-router-dom'

const Navigation = () => {
  const { logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/')
  }

  return (
    <nav className="navbar">
      <div className="nav-brand">
        <h2>Dispatch System</h2>
      </div>
      <div className="nav-links">
        <a href="/admin">SMT Portal</a>
        <Link to="/whatsapp-qr">WhatsApp QR</Link>
        <Link to="/dashboard">Dashboard</Link>
        <Link to="/drivers">Drivers</Link>
        <Link to="/bookings">Bookings</Link>
        <Link to="/upload">Upload</Link>
        <Link to="/assignment">Assign</Link>
        <Link to="/messages">Messages</Link>
      </div>
      <div className="nav-user">
        <button onClick={handleLogout}>Logout</button>
      </div>
    </nav>
  )
}

export default Navigation
