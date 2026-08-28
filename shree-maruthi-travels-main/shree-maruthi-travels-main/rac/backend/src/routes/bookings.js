import express from 'express';
import { getBookings, getBooking, updateBookingStatus } from '../controllers/bookingController.js';
import { authenticateToken } from '../middleware/auth.js';

const router = express.Router();

router.get('/', authenticateToken, getBookings);
router.get('/:booking_id', authenticateToken, getBooking);
router.patch('/:booking_id/status', authenticateToken, updateBookingStatus);

export default router;
