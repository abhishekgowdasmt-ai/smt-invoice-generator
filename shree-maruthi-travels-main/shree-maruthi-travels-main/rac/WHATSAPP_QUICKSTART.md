# ⚡ WhatsApp Integration - Quick Start

## 🎯 What You Get

✅ Automatic WhatsApp messages sent to drivers when bookings are assigned
✅ Message tracking and delivery status in the UI
✅ Support for Gupshup (India) and Twilio (Global)
✅ Zero additional npm dependencies needed

## 🚀 Quick Setup (5 minutes)

### 1. Choose Your Provider

**India (Recommended)**: Gupshup 🇮🇳
- Faster setup, cheaper
- Visit: https://www.gupshup.io/

**Global**: Twilio
- Worldwide coverage
- Visit: https://www.twilio.com/try-twilio

**Free / Developer**: WhatsApp Web JS
- 100% Free, unofficial
- Requires scanning a QR code from the server console.

### 2. Get Credentials

#### For Gupshup:
1. Create account → Verify email
2. Setup WhatsApp Business (wait 24-48 hours)
3. Get API Key from: Developers → API Credentials
4. Get App ID from same page
5. Note your WhatsApp number: 9019933599

#### For Twilio:
1. Create account → Verify phone
2. Go to Messaging → WhatsApp → Get Started
3. Copy Account SID
4. Copy Auth Token
5. Note your WhatsApp sandbox or production number

### 3. Update Configuration

Edit `backend/.env`:

**For Gupshup**:
```env
WHATSAPP_PROVIDER=gupshup
GUPSHUP_API_KEY=your_api_key_here
GUPSHUP_APP_ID=your_app_id_here
GUPSHUP_PHONE_NUMBER=9019933599
```

**For Twilio**:
```env
WHATSAPP_PROVIDER=twilio
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_WHATSAPP_NUMBER=whatsapp:+919019933599
```

**For Free Web JS (Unofficial)**:
```env
WHATSAPP_PROVIDER=wwebjs
# No other API keys needed! 
# You will scan a QR code in the terminal instead.
```

### 4. Restart Backend

```bash
cd backend
npm run dev
```

### 5. Test It! ✅

1. Open app → Login
2. Go to Bookings
3. Select unassigned booking → "Assign Now"
4. Pick a driver (must have WhatsApp number)
5. Click "Assign"
6. Driver gets WhatsApp message! 🎉

---

## 📱 What The Driver Sees

```
New Ride Assigned

Booking ID: TRK-12345
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

## 🔍 Verify It Works

### In Web UI:
- Go to **Messages** tab
- You should see your message
- Status should be: ✅ **sent**

### In Backend Logs:
```
[WHATSAPP] Sending via gupshup: { phoneNumber: '...', messageId: '...' }
[ASSIGNMENT] WhatsApp sent to +919876543210
```

### In Database:
```sql
SELECT * FROM message_logs ORDER BY created_at DESC LIMIT 1;
```

---

## ❌ Troubleshooting

| Problem | Solution |
|---------|----------|
| "Provider not configured" | Restart backend after updating `.env` |
| Message shows "failed" | Check driver's WhatsApp number format |
| No credentials error | Verify ALL required env vars are set |
| Message stuck "queued" | Check backend logs for errors |

---

## 📄 Full Documentation

- **Detailed Setup**: [WHATSAPP_SETUP.md](./WHATSAPP_SETUP.md)
- **Implementation Details**: [WHATSAPP_INTEGRATION_COMPLETE.md](./WHATSAPP_INTEGRATION_COMPLETE.md)
- **Config Template**: [backend/.env.example](./backend/.env.example)

---

## 🛠️ What Was Built

✅ **whatsappService.js** - Smart router (picks Gupshup, Twilio, or WWebJs)
✅ **whatsappGupshup.js** - Gupshup integration
✅ **whatsappTwilio.js** - Twilio integration (no SDK needed)
✅ **whatsappWebJs.js** - Free Web integration (QR Code login)
✅ **Integration** - Hooked into assignment workflow
✅ **Error Handling** - Graceful failures, assignment succeeds even if message fails
✅ **Message Logging** - Every message tracked in database

---

## 🎓 How It Works

```
User Assigns Booking to Driver
           ↓
System checks send_message_now (default: true)
           ↓
Generate formatted WhatsApp message
           ↓
Create MessageLog entry (for tracking)
           ↓
Send via Gupshup or Twilio API
           ↓
Update status (sent/failed)
           ↓
Driver receives WhatsApp ✅
```

---

## 📊 Message Tracking

Every message is logged with:
- ✅ Sent timestamp
- ✅ Provider (Gupshup/Twilio)
- ✅ Driver phone number
- ✅ Full message body
- ✅ Delivery status (sent/failed)
- ✅ Error details if failed

View in **Messages** tab → Sort by date → See all sends

---

## 🔐 Security

- Credentials stored in `.env` (not in code)
- `.gitignore` prevents credential exposure
- No sensitive data logged
- Secure API connections (HTTPS)

---

## 💰 Cost Estimation

### Gupshup (India)
- Setup cost: ₹0 (free approval)
- Per message: ₹0.50 - ₹2
- For 100 bookings/day: ₹50-200/day

### Twilio (Global)
- Setup cost: ₹0 (immediate with credit card)
- Per message: $0.005 - $0.01+
- For 100 bookings/day: $0.50-1+/day

---

## ✨ Advanced Features (Optional)

- Message templates per duty type
- Delivery confirmation tracking
- Automatic retries for failed messages
- Custom message personalization
- Message scheduling

---

## ❓ Need Help?

1. Check backend logs: `npm run dev`
2. Verify `.env` configuration
3. Test provider credentials in their dashboard
4. See [WHATSAPP_SETUP.md](./WHATSAPP_SETUP.md) for detailed guides

---

**Status**: ✅ **Ready to Use**

Your WhatsApp integration is fully configured and operational. Just add credentials and you're good to go!

