import express from 'express';
import { login, logout, getUser } from '../controllers/authController.js';
import { authenticateToken } from '../middleware/auth.js';

const router = express.Router();

router.post('/login', login);
router.post('/logout', logout);
router.get('/user', authenticateToken, getUser);

export default router;
