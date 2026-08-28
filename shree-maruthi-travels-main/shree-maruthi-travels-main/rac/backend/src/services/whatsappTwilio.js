/**
 * Twilio WhatsApp API Integration
 * Global coverage, good for testing and production
 * 
 * Setup:
 * 1. Create account at https://www.twilio.com/
 * 2. Set up WhatsApp sandbox or production number
 * 3. Add to .env:
 *    WHATSAPP_PROVIDER=twilio
 *    TWILIO_ACCOUNT_SID=your_account_sid
 *    TWILIO_AUTH_TOKEN=your_auth_token
 *    TWILIO_WHATSAPP_NUMBER=whatsapp:+91XXXXXXXXXX
 */

import axios from 'axios';

const formatPhoneNumber = (phoneNumber) => {
  let formatted = phoneNumber.replace(/\D/g, '');
  if (!formatted.startsWith('91')) {
    formatted = '91' + formatted.slice(-10);
  }
  return `whatsapp:+${formatted}`;
};

export const sendWhatsAppMessageTwilio = async (phoneNumber, messageBody, messageId) => {
  try {
    const accountSid = process.env.TWILIO_ACCOUNT_SID;
    const authToken = process.env.TWILIO_AUTH_TOKEN;
    const fromNumber = process.env.TWILIO_WHATSAPP_NUMBER;

    if (!accountSid || !authToken || !fromNumber) {
      throw new Error('Twilio credentials not configured (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_NUMBER)');
    }

    const toNumber = formatPhoneNumber(phoneNumber);
    const auth = Buffer.from(`${accountSid}:${authToken}`).toString('base64');

    const response = await axios.post(
      `https://api.twilio.com/2010-04-01/Accounts/${accountSid}/Messages.json`,
      new URLSearchParams({
        From: fromNumber,
        To: toNumber,
        Body: messageBody
      }),
      {
        headers: {
          Authorization: `Basic ${auth}`,
          'Content-Type': 'application/x-www-form-urlencoded'
        }
      }
    );

    console.log('[TWILIO] Message sent:', response.data.sid);

    return {
      success: true,
      provider: 'twilio',
      providerId: response.data.sid,
      messageId: response.data.sid,
      status: 'sent',
      timestamp: new Date()
    };
  } catch (err) {
    console.error('[TWILIO] Error sending message:', err.response?.data || err.message);
    return {
      success: false,
      provider: 'twilio',
      error: err.response?.data?.message || err.message,
      status: 'failed',
      timestamp: new Date()
    };
  }
};

export const getWhatsAppMessageStatusTwilio = async (messageSid) => {
  try {
    const accountSid = process.env.TWILIO_ACCOUNT_SID;
    const authToken = process.env.TWILIO_AUTH_TOKEN;

    if (!accountSid || !authToken) {
      throw new Error('Twilio credentials not configured');
    }

    const auth = Buffer.from(`${accountSid}:${authToken}`).toString('base64');

    const response = await axios.get(
      `https://api.twilio.com/2010-04-01/Accounts/${accountSid}/Messages/${messageSid}.json`,
      {
        headers: {
          Authorization: `Basic ${auth}`
        }
      }
    );

    return response.data.status;
  } catch (err) {
    console.error('[TWILIO] Error getting message status:', err.message);
    return 'unknown';
  }
};
