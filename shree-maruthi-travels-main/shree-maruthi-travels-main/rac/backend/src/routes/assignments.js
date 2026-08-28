import express from 'express';
import { createAssignment, getAssignment, resendMessage } from '../controllers/assignmentController.js';
import { authenticateToken } from '../middleware/auth.js';

const router = express.Router();

router.post('/', authenticateToken, createAssignment);
router.get('/:assignment_id', authenticateToken, getAssignment);
router.post('/:assignment_id/resend-message', authenticateToken, resendMessage);

export default router;
