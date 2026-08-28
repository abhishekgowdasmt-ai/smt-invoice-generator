import express from 'express';
import { createDriver, getDrivers, getDriver, updateDriver, updateDriverStatus } from '../controllers/driverController.js';
import { authenticateToken, authorizeRole } from '../middleware/auth.js';

const router = express.Router();

router.post('/', authenticateToken, createDriver);
router.get('/', authenticateToken, getDrivers);
router.get('/:driver_id', authenticateToken, getDriver);
router.put('/:driver_id', authenticateToken, updateDriver);
router.patch('/:driver_id/status', authenticateToken, updateDriverStatus);

export default router;
