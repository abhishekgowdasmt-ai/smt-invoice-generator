import express from 'express';
import cors from 'cors';
import helmet from 'helmet';
import morgan from 'morgan';
import 'express-async-errors';
import dotenv from 'dotenv';
import path from 'path';
import { fileURLToPath } from 'url';

import db from './config/database.js';
import authRoutes from './routes/auth.js';
import dashboardRoutes from './routes/dashboard.js';
import uploadRoutes from './routes/upload.js';
import bookingRoutes from './routes/bookings.js';
import driverRoutes from './routes/drivers.js';
import assignmentRoutes from './routes/assignments.js';
import messageRoutes from './routes/messages.js';
import whatsappRoutes from './routes/whatsapp.js';

dotenv.config();

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = process.env.PORT || 3000;

// Middleware
app.use(helmet());
app.use(cors({
  origin: process.env.CORS_ORIGIN?.split(',') || [
    'http://localhost:5173',
    'http://localhost:5000',
    'http://127.0.0.1:5000',
    'http://localhost:8080'
  ],
  credentials: true
}));
app.use(morgan('combined'));

// Static files
app.use('/uploads', express.static(path.join(__dirname, '../uploads')));

// Custom middleware to skip JSON parser for multipart requests
app.use((req, res, next) => {
  // If it's a multipart/form-data request, skip the JSON parser
  if (req.is('multipart/form-data')) {
    console.log('[MIDDLEWARE] Skipping JSON parser for multipart request:', req.method, req.path);
    return next();
  }
  // Otherwise, apply JSON parser
  express.json()(req, res, next);
});

app.use(express.urlencoded({ limit: '10mb', extended: true }));

// API Routes
app.use('/api/v1/auth', authRoutes);
app.use('/api/v1/dashboard', dashboardRoutes);
app.use('/api/v1/uploads', uploadRoutes);
app.use('/api/v1/bookings', bookingRoutes);
app.use('/api/v1/drivers', driverRoutes);
app.use('/api/v1/assignments', assignmentRoutes);
app.use('/api/v1/messages', messageRoutes);
app.use('/api/v1/whatsapp', whatsappRoutes);

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'OK', timestamp: new Date().toISOString() });
});

// Error handling middleware
app.use((err, req, res, next) => {
  console.error(err.stack);
  const status = err.status || 500;
  const message = err.message || 'Internal Server Error';
  res.status(status).json({
    success: false,
    message,
    ...(process.env.NODE_ENV === 'development' && { error: err })
  });
});

// 404 handler
app.use((req, res) => {
  res.status(404).json({
    success: false,
    message: 'Route not found'
  });
});

app.listen(PORT, async () => {
  try {
    // Sync database
    await db.sync({ alter: false });
    console.log(`✅ Database synced`);
  } catch (err) {
    console.error('❌ Database sync failed:', err.message);
  }
  
  console.log(`✅ Dispatch API running on http://localhost:${PORT}`);
  console.log(`📝 Environment: ${process.env.NODE_ENV || 'development'}`);
});

export default app;
