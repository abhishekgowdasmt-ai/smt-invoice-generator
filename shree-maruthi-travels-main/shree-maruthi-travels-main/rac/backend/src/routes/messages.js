import express from 'express';
import { getMessages, getMessage } from '../controllers/messageController.js';
import { authenticateToken } from '../middleware/auth.js';

const router = express.Router();

router.get('/', authenticateToken, getMessages);
router.get('/:message_id', authenticateToken, getMessage);

export default router;
