import express from 'express';
import { getWhatsAppWebStatus } from '../services/whatsappWebJs.js';

const router = express.Router();

// Public endpoint - no auth required (QR must be accessible before scanning)
router.get('/status', (req, res) => {
  try {
    const provider = process.env.WHATSAPP_PROVIDER || 'twilio';
    
    res.set('Cache-Control', 'no-store');

    if (provider !== 'wwebjs') {
      return res.json({
        success: true,
        provider,
        isReady: true,
        qr: null,
        message: `Using external provider: ${provider}`
      });
    }

    const status = getWhatsAppWebStatus();
    
    res.json({
      success: true,
      provider: 'wwebjs',
      isReady: status.isReady,
      qr: status.qr || null
    });
  } catch (error) {
    console.error('[WHATSAPP API] Error getting status:', error);
    res.status(500).json({ success: false, message: 'Server error retrieving status' });
  }
});

export default router;
