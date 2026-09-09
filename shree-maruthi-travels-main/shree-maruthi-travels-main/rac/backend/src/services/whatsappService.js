/**
 * WhatsApp Service Router
 * Routes messages to the configured WhatsApp provider
 */

import { sendWhatsAppMessageGupshup, getWhatsAppMessageStatusGupshup } from './whatsappGupshup.js';
import { sendWhatsAppMessageTwilio, getWhatsAppMessageStatusTwilio } from './whatsappTwilio.js';
import { sendWhatsAppMessageWWeb, getWhatsAppMessageStatusWWeb } from './whatsappWebJs.js';

const provider = process.env.WHATSAPP_PROVIDER || 'twilio';

export const sendWhatsAppMessage = async (phoneNumber, messageBody, messageId) => {
  console.log(`[WHATSAPP] Sending via ${provider}:`, { phoneNumber, messageId });

  try {
    if (provider === 'gupshup') {
      return await sendWhatsAppMessageGupshup(phoneNumber, messageBody, messageId);
    } else if (provider === 'twilio') {
      return await sendWhatsAppMessageTwilio(phoneNumber, messageBody, messageId);
    } else if (provider === 'wwebjs') {
      return await sendWhatsAppMessageWWeb(phoneNumber, messageBody, messageId);
    } else if (provider === 'none') {
      return {
        success: false,
        provider,
        error: 'WhatsApp is not configured on this server',
        status: 'failed',
        timestamp: new Date()
      };
    } else {
      throw new Error(`Unknown WhatsApp provider: ${provider}`);
    }
  } catch (err) {
    console.error('[WHATSAPP] Error:', err.message);
    return {
      success: false,
      provider,
      error: err.message,
      status: 'failed',
      timestamp: new Date()
    };
  }
};

export const getWhatsAppMessageStatus = async (messageId) => {
  try {
    if (provider === 'gupshup') {
      return await getWhatsAppMessageStatusGupshup(messageId);
    } else if (provider === 'twilio') {
      return await getWhatsAppMessageStatusTwilio(messageId);
    } else if (provider === 'wwebjs') {
      return await getWhatsAppMessageStatusWWeb(messageId);
    } else {
      return 'unknown';
    }
  } catch (err) {
    console.error('[WHATSAPP] Error getting status:', err.message);
    return 'unknown';
  }
};
