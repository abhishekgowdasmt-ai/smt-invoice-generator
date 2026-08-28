import express from 'express';
import { uploadExcel, getUploadStatus, getUploadHistory, upload } from '../controllers/uploadController.js';
import { authenticateToken } from '../middleware/auth.js';

const router = express.Router();

router.post('/excel', authenticateToken, (req, res, next) => {
  console.log('[UPLOAD] Processing file upload');
  upload.single('file')(req, res, (err) => {
    console.log('[UPLOAD] Multer completed. File:', req.file ? req.file.originalname : 'NOT FOUND');
    if (err) {
      console.error('[UPLOAD] Multer error:', err.message);
      return res.status(400).json({ 
        success: false, 
        message: err.message || 'File upload failed'
      });
    }
    next();
  });
}, uploadExcel);

router.get('/:batch_id/status', authenticateToken, getUploadStatus);
router.get('/history', authenticateToken, getUploadHistory);

export default router;
