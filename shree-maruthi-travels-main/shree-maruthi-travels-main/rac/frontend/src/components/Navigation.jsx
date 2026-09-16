import { useAuth } from '../App'
import { NavLink } from 'react-router-dom'

const Navigation = () => {
  const { logout } = useAuth()

  const handleLogout = () => {
    logout()
    window.location.href = '/admin'
  }

  return (
    <nav className="navbar">
      <div className="nav-brand">
        <a href="/admin">SMT Portal</a>
        <h2>RAC Management</h2>
      </div>
      <div className="nav-links">
        <NavLink to="/dashboard">Dashboard</NavLink>
        <NavLink to="/insights">Insights</NavLink>
        <NavLink to="/bookings">Bookings</NavLink>
        <NavLink to="/drivers">Drivers</NavLink>
        <NavLink to="/assignment">Assign</NavLink>
        <NavLink to="/upload">Upload</NavLink>
        <NavLink to="/messages">Messages</NavLink>
        <NavLink to="/whatsapp-qr">WhatsApp</NavLink>
      </div>
      <div className="nav-user">
        <button onClick={handleLogout}>Logout</button>
      </div>
    </nav>
  )
}

export default Navigation
