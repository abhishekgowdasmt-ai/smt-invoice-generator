# WhatsApp Integration Setup Guide

This guide explains how to configure WhatsApp messaging for automatic driver notifications when bookings are assigned.

## Overview

The system supports two WhatsApp providers:
- **Gupshup** (Recommended for India) - Lower cost, simpler setup, designed for Indian businesses
- **Twilio** (Global) - More expensive, reliable worldwide coverage, excellent support

## Option 1: Gupshup Setup (Recommended for India 🇮🇳)

### 1. Create Gupshup Account

1. Visit https://www.gupshup.io/
2. Click "Get Started" and sign up for a free account
3. Verify your email address
4. Complete KYC verification (required for India)

### 2. Create WhatsApp Business Account

1. Login to Gupshup dashboard
2. Navigate to **Settings → WhatsApp Business**
3. Click "Create WhatsApp Business Account" or "Add New Account"
4. Fill in business details:
   - Business name: Your dispatch company name
   - Business phone: Your WhatsApp Business number (9019933599 or similar)
   - Industry: Transportation/Logistics
5. Upload business documents as needed
6. Wait for account approval (usually 24-48 hours)

### 3. Configure API Credentials

1. Go to **Developers → API Credentials**
2. Create new API credentials:
   - Select WhatsApp API
   - Copy your **API Key** (save this)
   - Copy your **App ID** (save this)
3. Note your WhatsApp sender phone number (this is the number customers see)

### 4. Update Environment Variables

Add to `backend/.env`:

```env
WHATSAPP_PROVIDER=gupshup
GUPSHUP_API_KEY=YOUR_API_KEY_HERE
GUPSHUP_APP_ID=YOUR_APP_ID_HERE
GUPSHUP_PHONE_NUMBER=9019933599
```

Replace:
- `YOUR_API_KEY_HERE` - Your API key from step 3
- `YOUR_APP_ID_HERE` - Your App ID from step 3
- `9019933599` - Your WhatsApp Business number

### 5. Test the Integration

```bash
# Restart backend
npm run dev
```

Then:
1. Open the app and login
2. Assign a booking to a driver
3. Check that driver gets WhatsApp message
4. Verify message appears in message logs

---

## Option 2: Twilio Setup (Global Coverage)

### 1. Create Twilio Account

1. Visit https://www.twilio.com/try-twilio
2. Sign up with email and phone number
3. Verify phone number via SMS
4. Complete setup wizard

### 2. Set Up WhatsApp on Twilio

1. In Twilio Console, go to **Messaging → Try it out → Send an SMS**
2. In left sidebar, click **WhatsApp** (under Messaging)
3. Click **Try WhatsApp** or **Get Started**
4. Follow setup wizard:
   - For testing: Use sandbox option (messages go to approved test number)
   - For production: Connect your WhatsApp Business Account

### 3. Get Credentials

1. Go to **Account → Account SID** (save this)
2. Go to **Auth Tokens** (save this, shown as Auth Token)
3. Go to **Messaging → WhatsApp** → note your sandbox/production number

For sandbox testing, the number is: `whatsapp:+14155238886` (Twilio sandbox)

For production, obtain your business WhatsApp number. Format: `whatsapp:+919019933599`

### 4. Update Environment Variables

Add to `backend/.env`:

```env
WHATSAPP_PROVIDER=twilio
TWILIO_ACCOUNT_SID=AC1234567890...
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_WHATSAPP_NUMBER=whatsapp:+919019933599
```

Replace:
- `AC1234567890...` - Your Account SID
- `your_auth_token_here` - Your Auth Token
- `whatsapp:+919019933599` - Your WhatsApp number (format must start with `whatsapp:+`)

### 5. Test with Sandbox (Optional)

For testing without production setup:

```env
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
# Messages will go to your registered test number
```

---

## Configuration Files

### Backend `.env` File Location
`backend/.env`

### Example Complete .env

```env
# Database
DB_HOST=postgres
DB_USER=postgres
DB_PASSWORD=postgres123
DB_NAME=dispatch_db
DB_PORT=5432

# JWT
JWT_SECRET=your_jwt_secret_key_here

# WhatsApp - Gupshup Option (Uncomment to use)
# WHATSAPP_PROVIDER=gupshup
# GUPSHUP_API_KEY=abcd1234efgh5678
# GUPSHUP_APP_ID=12345
# GUPSHUP_PHONE_NUMBER=9019933599

# WhatsApp - Twilio Option (Uncomment to use)
WHATSAPP_PROVIDER=twilio
TWILIO_ACCOUNT_SID=ACabcd1234efgh5678
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_WHATSAPP_NUMBER=whatsapp:+919019933599
```

---

## Testing the Integration

### 1. Manual Test via API

```bash
curl -X POST http://localhost:3000/api/v1/assignments \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "booking_id": 1,
    "driver_id": 2,
    "assignment_notes": "Test assignment",
    "send_message_now": true
  }'
```

### 2. Via Web UI

1. Login to the application
2. Go to Bookings → select an unassigned booking
3. Click "Assign Now"
4. Select a driver with WhatsApp number
5. Check "Send WhatsApp" (should be checked by default)
6. Click "Assign"
7. Driver receives message on WhatsApp

### 3. Verify Message in Logs

1. Go to **Messages** tab
2. You should see the sent message with:
   - Status: `sent` (green)
   - Provider: `gupshup` or `twilio`
   - Timestamp: When message was sent
   - Driver phone: Recipient number
   - Message body: Full message text

---

## Message Format

When a booking is assigned, the driver receives:

```
New Ride Assigned

Booking ID: TRK-001
Date: 18-Dec-25
Employee: John Smith
Pickup: Downtown Station
Route: Downtown → Airport (150km)
Pickup Time: 09:00 AM
End Time: 11:30 PM
Duty Type: Airport Drop
Cab Type: Sedan
Amount: ₹2500

Please confirm this trip.
```

---

## Troubleshooting

### Message Not Sending

1. **Check driver phone number**
   - Verify driver has WhatsApp number in their profile
   - Ensure phone number format is correct (10 digits or international)
   - Test number format manually with provider's API

2. **Check credentials**
   ```bash
   # Verify .env file is loaded
   echo $GUPSHUP_API_KEY  # or TWILIO_ACCOUNT_SID for Twilio
   ```

3. **Check logs**
   - Backend server logs should show `[WHATSAPP]` messages
   - Look for success/failure status
   - Note any error messages

4. **Provider Issues**
   - Gupshup: Account might not be approved yet (wait 24-48 hours)
   - Twilio: Check if account has sufficient balance
   - Both: Verify API credentials are correct

### Message Stuck in "Queued"

1. Check backend server is running
2. Verify WhatsApp provider credentials are valid
3. Check provider dashboard for rate limiting
4. Restart backend service

### "Provider not configured" Error

1. Verify .env file exists at `backend/.env`
2. Check WHATSAPP_PROVIDER value is exactly `gupshup` or `twilio`
3. Verify backend was restarted after .env changes
4. Backend needs full restart (not just reload) after .env changes

---

## Switching Providers

To switch from Gupshup to Twilio or vice versa:

1. Stop backend server
2. Edit `backend/.env`:
   - Change `WHATSAPP_PROVIDER` to new provider
   - Add new provider's credentials
   - Remove old provider credentials (optional)

3. Restart backend:
   ```bash
   npm run dev
   ```

4. Test with a new assignment

---

## Cost Comparison

### Gupshup (Recommended)
- **Setup**: 24-48 hours
- **Cost**: ₹0.50 - ₹2 per message (India)
- **Requirements**: KYC verification required
- **Best for**: India-focused dispatch business

### Twilio
- **Setup**: Immediate (sandbox) or 1-2 days (production)
- **Cost**: Starting at $0.005/message (global rates vary)
- **Requirements**: Credit card required
- **Best for**: Global coverage, multi-country operations

---

## API Response Format

### Successful Message Send
```json
{
  "success": true,
  "message": "Booking assigned successfully",
  "assignment_id": 123,
  "whatsapp_status": "sent"
}
```

### Failed Message Send
```json
{
  "success": true,
  "message": "Booking assigned successfully",
  "assignment_id": 123,
  "whatsapp_status": "failed"
}
```

Note: Assignment succeeds even if message fails. Check MessageLog table for details.

---

## Database Schema for Messages

Messages are stored in the `message_logs` table with:
- `message_id`: Unique message identifier
- `booking_id`: Associated booking
- `driver_id`: Recipient driver
- `phone_number`: Recipient WhatsApp number
- `message_body`: Full message text
- `provider_name`: `gupshup` or `twilio`
- `provider_message_id`: ID from WhatsApp provider
- `send_status`: `queued`, `sent`, `failed`, `delivered`
- `sent_at`: Timestamp when sent
- `error_message`: Error details if failed

---

## Production Deployment

### Docker Deployment

1. Update `backend/.env` in the repository
2. Ensure credentials are in .env (gitignore protects it)
3. Run: `docker-compose up --build`
4. Backend service will pick up WhatsApp config

### Environment Variable Security

**Never commit credentials to Git:**
```bash
# .gitignore should include:
backend/.env
backend/.env.local
backend/.env.*.local
```

---

## Next Steps

1. Choose provider: Gupshup (India) or Twilio (Global)
2. Create account and obtain API credentials
3. Update `backend/.env` with credentials
4. Restart backend server
5. Test with a booking assignment
6. Monitor message logs for delivery tracking

---

## Support & Resources

- **Gupshup Docs**: https://docs.gupshup.io/
- **Twilio Docs**: https://www.twilio.com/docs/whatsapp
- **Dashboard Metrics**: Visit Messages tab to see all sent messages
- **Error Logs**: Backend server logs show detailed WhatsApp send attempts

---

**Status**: ✅ WhatsApp integration fully configured and ready for deployment
