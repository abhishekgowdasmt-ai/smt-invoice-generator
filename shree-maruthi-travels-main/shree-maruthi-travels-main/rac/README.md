# Dispatch Management System - Phase 1 MVP

A full-stack web application for managing ride bookings, driver assignments, and WhatsApp notifications.

**Technologies:**
- Frontend: React.js (Vite)
- Backend: Node.js/Express.js
- Database: PostgreSQL
- Message Queue: Redis
- Containerization: Docker

## Project Structure

```
├── backend/              # Node.js API server
│   ├── src/
│   │   ├── controllers/  # Business logic
│   │   ├── routes/       # API routes
│   │   ├── models/       # Sequelize models
│   │   ├── middleware/   # Auth, error handling
│   │   ├── services/     # External services
│   │   ├── utils/        # Helpers
│   │   └── server.js     # Entry point
│   ├── db/
│   │   ├── schema.sql    # Database schema
│   │   ├── migrations/   # Schema migrations
│   │   └── seeds/        # Seed data
│   ├── package.json
│   └── Dockerfile
├── frontend/             # React app
│   ├── src/
│   │   ├── components/   # React components
│   │   ├── pages/        # Page components
│   │   ├── services/     # API calls
│   │   ├── contexts/     # React contexts
│   │   ├── App.jsx
│   │   └── main.jsx
│   ├── index.html
│   ├── vite.config.js
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml
├── README.md
└── .gitignore
```

## Setup & Development

### Prerequisites
- Docker & Docker Compose (recommended)
- Or: Node.js 18+, PostgreSQL 14+

### Quick Start with Docker

1. **Clone and setup:**
```bash
cd dispatch-mvp
docker-compose up --build
```

2. **Access the application:**
- Frontend: http://localhost:5173
- Backend API: http://localhost:3000
- Database: localhost:5432

### Manual Setup

#### Backend
```bash
cd backend
npm install
cp .env.example .env  # Update with your database credentials
npm run migrate       # Create database schema
npm run dev           # Start dev server on :3000
```

#### Frontend
```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev           # Start dev server on :5173
```

## API Documentation

All endpoints require JWT authentication except `/auth/login`.

### Authentication
- `POST /api/v1/auth/login` - Login
- `GET /api/v1/auth/user` - Get current user
- `POST /api/v1/auth/logout` - Logout

### Dashboard
- `GET /api/v1/dashboard/summary` - Get KPI summary

### Drivers
- `POST /api/v1/drivers` - Create driver
- `GET /api/v1/drivers` - List drivers
- `GET /api/v1/drivers/:id` - Get driver
- `PUT /api/v1/drivers/:id` - Update driver
- `PATCH /api/v1/drivers/:id/status` - Toggle active status

### Bookings
- `GET /api/v1/bookings` - List bookings
- `GET /api/v1/bookings/:id` - Get booking details
- `PATCH /api/v1/bookings/:id/status` - Update booking status

### Excel Upload
- `POST /api/v1/uploads/excel` - Upload Excel file
- `GET /api/v1/uploads/:batch_id/status` - Check upload status
- `GET /api/v1/uploads/history` - View upload history

### Assignments
- `POST /api/v1/assignments` - Assign booking to driver
- `GET /api/v1/assignments/:id` - Get assignment details
- `POST /api/v1/assignments/:id/resend-message` - Resend WhatsApp message

### Messages
- `GET /api/v1/messages` - List message logs
- `GET /api/v1/messages/:id` - Get message details

## Default Test Credentials

- Email: `admin@dispatch.local`
- Password: `Admin@12345`

(Create this user by running seed script or manually)

## Development Checklist - Phase 1

### Backend ✅ Completed
- [x] Project structure & scaffolding
- [x] Backend API setup
- [x] Database schema (7 tables)
- [x] Authentication (JWT + bcrypt)
- [x] Excel upload processing
- [x] Driver CRUD operations
- [x] Booking management
- [x] Assignment workflow
- [x] Message logging
- [x] Dashboard KPI summary
- [x] Error handling & validation

### Frontend ✅ Completed
- [x] Authentication context & login page
- [x] Protected routes setup
- [x] Dashboard with KPI cards
- [x] Navigation bar component
- [x] Upload Excel page
- [x] Bookings list page with filters
- [x] Booking detail page
- [x] Drivers management page
- [x] Assignment/dispatch page
- [x] Message log page
- [x] API service layer
- [x] Comprehensive CSS styling

### Remaining Tasks
- [ ] WhatsApp API integration (Twilio/Gupshup/Interakt/360Dialog)
- [ ] Message queue implementation (Bull + Redis)
- [ ] Form validation library
- [ ] Toast notifications
- [ ] Batch operations (assign multiple bookings)
- [ ] Export to Excel
- [ ] Real-time updates (WebSocket)
- [ ] Unit & E2E testing
- [ ] Production deployment guide
- [ ] Performance optimization
- [ ] Accessibility (WCAG) improvements

## Environment Variables

See `.env.example` in backend/ and frontend/ folders.

**Key variables:**
- `JWT_SECRET` - JWT signing key
- `DATABASE_URL` - PostgreSQL connection string
- `WHATSAPP_PROVIDER` - Provider (twilio, gupshup, interakt, 360dialog)
- `VITE_API_URL` - Backend API URL (frontend)

## Deployment

### Docker

Build and run:
```bash
docker-compose -f docker-compose.yml up -d
```

### Production

1. Update `.env` with production values
2. Set `NODE_ENV=production`
3. Run database migrations
4. Deploy using your preferred hosting (AWS, GCP, DigitalOcean, etc.)

## Support

For issues and questions, refer to the [SRD documentation](./Dispatch_MVP_SRD_Phase1.md)

## License

ISC
