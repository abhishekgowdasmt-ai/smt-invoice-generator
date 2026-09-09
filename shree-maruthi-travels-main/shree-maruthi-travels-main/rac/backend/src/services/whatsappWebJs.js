/**
 * WhatsApp integration using whatsapp-web.js (Unofficial / Free)
 * 
 * Note: This requires scanning a QR code from the server console on startup!
 */

import pkg from 'whatsapp-web.js';
import qrcode from 'qrcode-terminal';

const { Client, LocalAuth } = pkg;

const whatsappWebEnabled = process.env.WHATSAPP_PROVIDER === 'wwebjs';

let client = null;
let isReady = false;
let currentQR = null;

if (whatsappWebEnabled) {
  client = new Client({
    authStrategy: new LocalAuth(),
    puppeteer: {
      executablePath: process.env.PUPPETEER_EXECUTABLE_PATH || null,
      args: [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',
        '--disable-gpu',
        '--disable-extensions',
        '--remote-debugging-port=9222'
      ],
      headless: true
    }
  });
}

if (client) {
  client.on('qr', (qr) => {
    currentQR = qr;
    isReady = false;
    console.log('====================================================');
    console.log('📱 WHATSAPP AUTHENTICATION REQUIRED');
    console.log('Please scan this QR code with your WhatsApp mobile app');
    console.log('Open WhatsApp -> Menu -> Linked Devices -> Link a Device');
    console.log('====================================================');
  });

  client.on('ready', () => {
    console.log('✅ WhatsApp Web Client is ready!');
    currentQR = null;
    isReady = true;
  });

  client.on('disconnected', (reason) => {
    console.log('❌ WhatsApp Client was disconnected', reason);
    currentQR = null;
    isReady = false;
  });
}

// Initialize the client explicitly in a non-blocking way
const initializeWhatsApp = async (retries = 3) => {
  try {
    console.log(`Starting WhatsApp Web client initialization (Attempt ${4 - retries}/3)...`);
    
    // We add a delay to let the rest of the server start first
    if (retries === 3) await new Promise(resolve => setTimeout(resolve, 5000));
    
    await client.initialize();
    console.log('WhatsApp client.initialize() call completed.');
  } catch (error) {
    console.error('❌ Failed to initialize WhatsApp Web client:', error.message);
    isReady = false;
    
    if (retries > 0) {
      console.log(`Retrying in 10 seconds... (${retries} retries left)`);
      setTimeout(() => initializeWhatsApp(retries - 1), 10000);
    } else {
      console.error('❌ All WhatsApp initialization attempts failed.');
    }
  }
};

if (whatsappWebEnabled) {
  initializeWhatsApp().catch(err => {
    console.error('🔥 Fatal error in WhatsApp init background task:', err);
  });
} else {
  console.log('WhatsApp Web client is disabled (set WHATSAPP_PROVIDER=wwebjs to enable).');
}

/**
 * Sends a message via whatsapp-web.js
 * @param {string} phoneNumber - Recipient phone number (e.g., 919876543210)
 * @param {string} messageBody - The message string
 * @param {string} messageId - Unique ID for tracking
 * @returns {object} Status object
 */
export const sendWhatsAppMessageWWeb = async (phoneNumber, messageBody, messageId) => {
  try {
    if (!client || !isReady) {
      console.warn('[WHATSAPP-WEB] Cannot send message - client is not ready. Please scan QR code in console.');
      return {
        success: false,
        provider: 'wwebjs',
        error: 'Client not authenticated/ready',
        status: 'failed',
        timestamp: new Date()
      };
    }

    // Format phone number: remove non-digits and append @c.us suffix
    // Typical format required by whatsapp-web.js: 919876543210@c.us
    let cleanNumber = phoneNumber.replace(/\D/g, '');
    
    // Ensure it has a country code, defaulting to India (91) if 10 digits
    if (cleanNumber.length === 10) {
      cleanNumber = '91' + cleanNumber; 
    }
    
    const formattedNumber = `${cleanNumber}@c.us`;

    // Send the message
    await client.sendMessage(formattedNumber, messageBody);

    return {
      success: true,
      provider: 'wwebjs',
      provider_message_id: messageId, // wwebjs doesn't return a simple message ID reliably that matches DB
      status: 'sent',
      timestamp: new Date()
    };
  } catch (err) {
    console.error('[WHATSAPP-WEB] Error sending message:', err.message);
    return {
      success: false,
      provider: 'wwebjs',
      error: err.message,
      status: 'failed',
      timestamp: new Date()
    };
  }
};

/**
 * Gets message status (mock for compatibility)
 */
export const getWhatsAppMessageStatusWWeb = async (messageId) => {
  // whatsapp-web.js uses events for delivery receipts rather than polling.
  // For the MVP, we just assume "sent" if no error was thrown.
  return 'sent';
};

/**
 * Gets the current connection status and QR code
 */
export const getWhatsAppWebStatus = () => {
  return {
    isReady,
    qr: currentQR
  };
};
