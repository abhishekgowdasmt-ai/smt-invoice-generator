import { useEffect, useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../App'
import { API } from '../services/api'

const Icon = ({ children }) => (
  <svg viewBox="0 0 24 24" className="rac-ico" aria-hidden="true">{children}</svg>
)

const links = [
  { to: '/dashboard', label: 'Dashboard', icon: <><path d="M4 11l8-8 8 8"/><path d="M6 10v9h12v-9"/></> },
  { to: '/insights', label: 'Insights', icon: <><path d="M4 19h16M7 16V9M12 16V5M17 16v-6"/></> },
  { to: '/bookings', label: 'Bookings', icon: <><rect x="5" y="4" width="14" height="16" rx="2"/><path d="M8 8h8M8 12h8M8 16h5"/></> },
  { to: '/drivers', label: 'Drivers', icon: <><circle cx="12" cy="8" r="3"/><path d="M5 19a7 7 0 0 1 14 0"/></> },
  { to: '/assignment', label: 'Assign', icon: <><circle cx="8" cy="8" r="3"/><path d="M2.5 19a6 6 0 0 1 11 0M16 11l2 2 4-4"/></> },
  { to: '/upload', label: 'Upload', icon: <><path d="M12 16V5M8 9l4-4 4 4"/><path d="M5 19h14"/></> },
  { to: '/booking-ocr', label: 'Booking OCR', icon: <><rect x="5" y="4" width="14" height="16" rx="2"/><path d="M8 8h8M8 12h5"/></> },
  { to: '/messages', label: 'Messages', icon: <><path d="M5 5h14v10H8l-3 4z"/></> },
  { to: '/whatsapp-qr', label: 'WhatsApp', icon: <><path d="M7 17l-2 4 4-2"/><path d="M12 19a7 7 0 1 0-6.3-4"/></> },
]

const Navigation = () => {
  const { logout, user } = useAuth()
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [waReady, setWaReady] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const email = user?.email || 'Admin'
  const initial = email.trim().charAt(0).toUpperCase() || 'A'
  const today = new Date().toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })

  useEffect(() => {
    API.getWhatsappStatus()
      .then((data) => setWaReady(!!data.isReady))
      .catch(() => setWaReady(false))
  }, [])

  const handleLogout = () => {
    logout()
    window.location.href = '/admin'
  }

  const submitSearch = (event) => {
    event.preventDefault()
    const text = query.trim()
    navigate(text ? `/bookings?search=${encodeURIComponent(text)}` : '/bookings')
  }

  return (
    <>
      <aside className={`rac-sidebar${menuOpen ? ' is-open' : ''}`}>
        <a className="rac-brand" href="/admin">
          <img src="/static/images/logo.png" alt="" />
          <span>
            <small>SMT Portal</small>
            <strong>RAC Management</strong>
          </span>
        </a>
        <nav className="rac-side-links">
          {links.map((item) => (
            <NavLink key={item.to} to={item.to} onClick={() => setMenuOpen(false)}>
              <Icon>{item.icon}</Icon>
              {item.label}
            </NavLink>
          ))}
        </nav>
        <button type="button" className="rac-side-logout" onClick={handleLogout}>
          <Icon><path d="M10 17H6V7h4M14 12H8M14 12l3-3M14 12l3 3"/></Icon>
          Logout
        </button>
      </aside>
      <header className="rac-topbar">
        <button type="button" className="rac-menu-btn" onClick={() => setMenuOpen((open) => !open)} aria-label="Menu">☰</button>
        <form className="rac-search" onSubmit={submitSearch}>
          <Icon><circle cx="11" cy="11" r="7"/><path d="M20 20l-3-3"/></Icon>
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search bookings, drivers, or WhatsApp messages..."
          />
        </form>
        <div className="rac-top-actions">
          <Linkish ready={waReady} />
          <button type="button" className="rac-bell" onClick={() => navigate('/messages')} title="Messages">
            <Icon><path d="M15 17h5l-1.4-1.4A2 2 0 0 1 18 14.2V11a6 6 0 1 0-12 0v3.2c0 .5-.2 1-.6 1.4L4 17h5"/><path d="M9 17a3 3 0 0 0 6 0"/></Icon>
          </button>
          <div className="rac-userchip" title={email}>
            <span className="rac-avatar">{initial}</span>
            <span>{email.split('@')[0]}</span>
          </div>
          <div className="rac-today">Today, {today}</div>
        </div>
      </header>
    </>
  )
}

const Linkish = ({ ready }) => (
  <NavLink to="/whatsapp-qr" className={`rac-wa ${ready ? 'is-on' : 'is-off'}`}>
    <Icon><path d="M7 17l-2 4 4-2"/><path d="M12 19a7 7 0 1 0-6.3-4"/></Icon>
    {ready ? 'WA Active' : 'WA Offline'}
  </NavLink>
)

export default Navigation
