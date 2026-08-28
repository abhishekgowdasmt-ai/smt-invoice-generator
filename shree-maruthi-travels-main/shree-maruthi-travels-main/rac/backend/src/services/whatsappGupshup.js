/**
 * Gupshup WhatsApp API Integration
 * Recommended for India-based businesses
 * 
 * Setup:
 * 1. Create account at https://www.gupshup.io/
 * 2. Get API key from dashboard
 * 3. Add to .env:
 *    WHATSAPP_PROVIDER=gupshup
 *    GUPSHUP_API_KEY=your_api_key
 *    GUPSHUP_APP_ID=your_app_id
 *    GUPSHUP_PHONE_NUMBER=9019933599
 */

import axios from 'axios';

const GUPSHUP_BASE_URL = 'https://api.gupshup.io/sm/api/v1';

export const sendWhatsAppMessageGupshup = async (phoneNumber, messageBody, messageId) => {
  try {
    const apiKey = process.env.GUPSHUP_API_KEY;
    const appId = process.env.GUPSHUP_APP_ID;
    const senderPhone = process.env.GUPSHUP_PHONE_NUMBER;

    if (!apiKey || !appId) {
      throw new Error('Gupshup API key or App ID not configured');
    }

    // Format phone number to international format (91 is India country code)
    let formattedPhone = phoneNumber.replace(/\D/g, '');
    if (!formattedPhone.startsWith('91')) {
      formattedPhone = '91' + formattedPhone.slice(-10);
    }

    const response = await axios.post(
      `${GUPSHUP_BASE_URL}/msg/send/whatapp`,
      {
        channel: 'whatsapp',
        source: senderPhone,
        destination: formattedPhone,
        message: messageBody,
        'message-id': messageId
      },
      {
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${apiKey}`,
          'X-Gupshup-App-Id': appId
        }
      }
    );

    console.log('[GUPSHUP] Message sent:', response.data);

    return {
      success: true,
      provider: 'gupshup',
      providerId: response.data?.messageId || messageId,
      status: 'sent',
      timestamp: new Date()
    };
  } catch (err) {
    console.error('[GUPSHUP] Error sending message:', err.message);
    return {
      success: false,
      provider: 'gupshup',
      error: err.message,
      status: 'failed',
      timestamp: new Date()
    };
  }
};

export const getWhatsAppMessageStatusGupshup = async (messageId) => {
  try {
    const apiKey = process.env.GUPSHUP_API_KEY;
    const appId = process.env.GUPSHUP_APP_ID;

    const response = await axios.get(
      `${GUPSHUP_BASE_URL}/msg/status/${messageId}`,
      {
        headers: {
          'Authorization': `Bearer ${apiKey}`,
          'X-Gupshup-App-Id': appId
        }
      }
    );

    return response.data?.status || 'unknown';
  } catch (err) {
    console.error('[GUPSHUP] Error getting message status:', err.message);
    return 'unknown';
  }
};
