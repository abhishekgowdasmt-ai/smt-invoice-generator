# Dispatch Management System - Development Guide

This is a full-stack dispatch management system with React frontend, Node.js backend, and PostgreSQL database.

## Project Overview

**Phase 1 MVP Features:**
- User authentication (JWT)
- Excel booking import with validation
- Driver master management
- Booking/ride management with filtering
- Driver assignment workflow
- WhatsApp message automation (integrated via provider API)
- Dashboard with KPI analytics
- Message delivery tracking

**Tech Stack:**
- Frontend: React 18 + Vite 5 + React Router
- Backend: Express.js + Sequelize ORM
- Database: PostgreSQL 14
- Message Queue: Redis (for async tasks)
- Deployment: Docker & Docker Compose

## Getting Started

### Prerequisites
- Node.js 18+ (for local development)
- Docker & Docker Compose (recommended for database services)
- PostgreSQL 14+

### Setup Steps

#### 1. Install Dependencies
```bash
# Backend
cd backend
npm install

# Frontend
cd ../frontend
npm install
cd ..
```

#### 2. Database Setup
```bash
# Option A: Using Docker Compose
docker-compose up postgres redis

# Option B: Manual PostgreSQL
psql -U postgres -c "CREATE DATABASE dispatch_db;"
psql -U dispatch_user -d dispatch_db -f backend/db/schema.sql
```

#### 3. Environment Configuration
Backend `.env` file is already created at `backend/.env`
Frontend `.env.local` file is already created at `frontend/.env.local`

Update if needed with your database credentials and API keys.

#### 4. Start Development Servers

```bash
# Terminal 1: Backend
cd backend
npm run dev
# Runs on http://localhost:3000

# Terminal 2: Frontend
cd frontend
npm run dev
# Runs on http://localhost:5173
```

### Using Docker Compose

```bash
# Build and start all services
docker-compose up --build

# Services available at:
# - Frontend: http://localhost:5173
# - Backend: http://localhost:3000
# - Database: localhost:5432
# - Redis: localhost:6379
```

## Project Structure

```
dispatch-mvp/
├── backend/
│   ├── src/
│   │   ├── server.js              # Express setup
│   │   ├── config/
│   │   │   └── database.js        # Sequelize config
│   │   ├── models/                # Sequelize models
│   │   │   ├── User.js
│   │   │   ├── Driver.js
│   │   │   ├── Booking.js
│   │   │   ├── Assignment.js
│   │   │   ├── UploadBatch.js
│   │   │   └── MessageLog.js
│   │   ├── routes/                # API routes
│   │   │   ├── auth.js
│   │   │   ├── drivers.js
│   │   │   ├── bookings.js
│   │   │   ├── assignments.js
│   │   │   ├── messages.js
│   │   │   ├── upload.js
│   │   │   └── dashboard.js
│   │   ├── controllers/           # Business logic
│   │   ├── middleware/            # Auth, errors
│   │   ├── services/              # External services
│   │   └── utils/
│   ├── db/
│   │   ├── schema.sql             # Database schema
│   │   ├── seeds/
│   │   └── migrations/
│   ├── package.json
│   ├── .env                       # Configuration
│   └── Dockerfile
│
├── frontend/
│   ├── src/
│   │   ├── main.jsx               # ReactDOM entry
│   │   ├── App.jsx                # Main component
│   │   ├── index.css
│   │   ├── pages/                 # Page components
│   │   ├── components/            # Reusable components
│   │   ├── services/              # API client
│   │   └── contexts/              # React contexts
│   ├── index.html
│   ├── vite.config.js
│   ├── package.json
│   ├── .env.local
│   └── Dockerfile
│
├── docker-compose.yml
├── README.md
└── Dispatch_MVP_SRD_Phase1.md     # Full specification
```

## API Endpoints

All backend endpoints are prefixed with `/api/v1` and require JWT authentication (except `/auth/login`).

### Authentication
- `POST /api/v1/auth/login` - Authenticate user
- `GET /api/v1/auth/user` - Get current user info
- `POST /api/v1/auth/logout` - Logout

### Dashboard
- `GET /api/v1/dashboard/summary` - Get dashboard KPIs

### Drivers
- `POST /api/v1/drivers` - Create driver
- `GET /api/v1/drivers` - List drivers (with pagination & search)
- `GET /api/v1/drivers/:driver_id` - Get driver details
- `PUT /api/v1/drivers/:driver_id` - Update driver
- `PATCH /api/v1/drivers/:driver_id/status` - Toggle active status

### Bookings
- `GET /api/v1/bookings` - List bookings (with filters)
- `GET /api/v1/bookings/:booking_id` - Get booking details
- `PATCH /api/v1/bookings/:booking_id/status` - Update booking status

### Excel Upload
- `POST /api/v1/uploads/excel` - Upload Excel file
- `GET /api/v1/uploads/:batch_id/status` - Check upload progress
- `GET /api/v1/uploads/history` - View upload history

### Assignments
- `POST /api/v1/assignments` - Assign booking to driver
- `GET /api/v1/assignments/:assignment_id` - Get assignment
- `POST /api/v1/assignments/:assignment_id/resend-message` - Resend WhatsApp

### Messages
- `GET /api/v1/messages` - List message logs
- `GET /api/v1/messages/:message_id` - Get message details

## Key Development Tasks - Phase 1

### Completed ✅
- Project scaffolding with proper directory structure
- Backend API setup (Express + Sequelize)
- Database schema with 7 tables
- User authentication (JWT-based)
- Driver CRUD endpoints
- Booking list/search/filter endpoints
- Excel import with validation & error handling
- Assignment workflow with message queuing
- Dashboard KPI summary
- Message log tracking
- Frontend starter with login & auth context
- Docker setup for local development

### In Progress / To-Do
- [ ] Complete React components for all 8 screens
- [ ] Upload Excel screen with file preview
- [ ] Booking list with advanced filters
- [ ] Booking detail view
- [ ] Driver management UI
- [ ] Assignment/dispatch screen
- [ ] Message log viewer
- [ ] WhatsApp API integration (Twilio/Gupshup)
- [ ] Error boundaries & toast notifications
- [ ] Responsive design & accessibility
- [ ] Unit & E2E testing
- [ ] Performance optimization
- [ ] Production deployment guide

## Common Development Commands

```bash
# Backend
cd backend
npm run dev              # Start dev server with hot reload
npm run migrate          # Run database migrations
npm run seed             # Populate test data
npm test                 # Run tests

# Frontend
cd frontend
npm run dev              # Start dev server
npm run build            # Production build
npm run preview          # Preview production build
npm run lint             # Run ESLint

# Docker
docker-compose up       # Start all services
docker-compose down     # Stop all services
docker-compose logs -f  # View logs
```

## Testing Locally

### Test Credentials
- Email: `admin@dispatch.local`
- Password: `Admin@12345`

(Create this user manually or run seed script)

### Sample Excel File Format

See the SRD document for Excel column mapping and validation rules.

## Troubleshooting

### Database Connection Issues
```bash
# Check if PostgreSQL is running
docker ps | grep postgres

# View database logs
docker-compose logs postgres

# Recreate database
docker-compose down -v
docker-compose up postgres
```

### Port Already in Use
```bash
# Backend (3000)
lsof -i :3000

# Frontend (5173)
lsof -i :5173
```

### Module Not Found
```bash
# Clear node_modules and reinstall
rm -rf backend/node_modules frontend/node_modules
npm install --prefix backend
npm install --prefix frontend
```

## Additional Resources

- Full Specification: [Dispatch_MVP_SRD_Phase1.md](./Dispatch_MVP_SRD_Phase1.md)
- Express API Docs: https://expressjs.com
- React Docs: https://react.dev
- Sequelize ORM: https://sequelize.org
- Vite Docs: https://vitejs.dev

## Performance Considerations

- Use database indexing on frequently queried fields (already done in schema)
- Implement pagination for large datasets (implemented)
- Cache dashboard summary results
- Use Redis for message queuing
- Lazy load React components
- Compress assets in production

## Security Checklist

- [x] Use JWT for stateless authentication
- [x] Hash passwords with bcrypt
- [x] CORS configured to whitelist allowed origins
- [x] Helmet.js headers for security
- [x] Input validation on all endpoints
- [x] Environment variables for sensitive data
- [ ] SQL injection prevention (using ORM)
- [ ] Rate limiting on auth endpoints
- [ ] HTTPS in production
- [ ] Audit logging for sensitive operations

## Next Phase (Phase 2+)

- Analytics & reporting dashboard
- Driver confirmation feedback
- Trip completion tracking
- Billing & invoice generation
- Driver performance ratings
- Notifications & alerts
- Mobile app for drivers

---

For questions or issues, refer to the SRD document or create an issue in the repository.
