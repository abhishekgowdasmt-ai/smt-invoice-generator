import http from 'http'
import path from 'path'
import { fileURLToPath } from 'url'
import makeWASocket, {
  Browsers,
  DisconnectReason,
  fetchLatestBaileysVersion,
  useMultiFileAuthState,
} from '@whiskeysockets/baileys'
import { Boom } from '@hapi/boom'
import pino from 'pino'

const PORT = Number(process.env.WA_BRIDGE_PORT || 3100)
const AUTH_DIR = process.env.WA_AUTH_DIR || path.join(path.dirname(fileURLToPath(import.meta.url)), 'auth')

let sock = null
let qr = null
let ready = false
let lastError = ''
let starting = false
let lastQrLog = 0

function digitsPhone(phone) {
  let digits = String(phone || '').replace(/\D/g, '')
  if (digits.length === 10) digits = `91${digits}`
  return digits
}

async function connect() {
  if (starting) return
  starting = true
  try {
    const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR)
    const { version } = await fetchLatestBaileysVersion()
    sock = makeWASocket({
      version,
      auth: state,
      logger: pino({ level: 'silent' }),
      browser: Browsers.ubuntu('Chrome'),
    })
    sock.ev.on('creds.update', saveCreds)
    sock.ev.on('connection.update', (update) => {
      const { connection, lastDisconnect, qr: nextQr } = update
      if (nextQr) {
        qr = nextQr
        ready = false
        lastError = ''
        const now = Date.now()
        if (now - lastQrLog > 60000) {
          lastQrLog = now
          console.log('[wa-bridge] waiting for a scan — RAC Management → WhatsApp → Linked devices')
        }
      }
      if (connection === 'open') {
        ready = true
        qr = null
        lastError = ''
        console.log('[wa-bridge] WhatsApp linked')
      }
      if (connection === 'close') {
        ready = false
        const err = lastDisconnect?.error
        const statusCode = err instanceof Boom ? err.output?.statusCode : 0
        const message = String(err?.message || err || 'disconnected')
        const loggedOut = statusCode === DisconnectReason.loggedOut
        const qrExpired = /QR refs/i.test(message)
        lastError = loggedOut ? 'logged_out' : (qrExpired ? 'qr_expired' : message)
        sock = null
        starting = false
        if (loggedOut) {
          qr = null
          console.log('[wa-bridge] logged out — open RAC → WhatsApp to link again')
          return
        }
        const waitMs = qrExpired ? 30000 : 8000
        if (qrExpired) {
          console.log('[wa-bridge] QR expired. Open RAC → WhatsApp and scan the new code.')
        } else {
          console.log('[wa-bridge] disconnected', lastError)
        }
        setTimeout(() => connect().catch((retryErr) => console.error(retryErr)), waitMs)
      }
    })
  } catch (err) {
    lastError = err.message
    console.error('[wa-bridge] connect failed', err)
    starting = false
    setTimeout(() => connect().catch((e) => console.error(e)), 8000)
    return
  }
  starting = false
}

async function sendMessage(phone, message) {
  if (!sock || !ready) {
    return { success: false, error: 'WhatsApp is not linked yet. Scan the QR on WhatsApp.' }
  }
  const digits = digitsPhone(phone)
  if (!digits) {
    return { success: false, error: 'Missing driver WhatsApp number' }
  }
  await sock.sendMessage(`${digits}@s.whatsapp.net`, { text: String(message || '') })
  return { success: true }
}

function json(res, status, body) {
  res.writeHead(status, { 'Content-Type': 'application/json' })
  res.end(JSON.stringify(body))
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = []
    req.on('data', (chunk) => chunks.push(chunk))
    req.on('end', () => {
      try {
        resolve(JSON.parse(Buffer.concat(chunks).toString() || '{}'))
      } catch (err) {
        reject(err)
      }
    })
    req.on('error', reject)
  })
}

const server = http.createServer(async (req, res) => {
  try {
    if (req.method === 'GET' && req.url === '/status') {
      return json(res, 200, {
        success: true,
        provider: 'wwebjs',
        isReady: ready,
        qr,
        message: ready
          ? 'WhatsApp is linked. Assignments will send from this account.'
          : qr
            ? 'Scan this QR in WhatsApp → Linked devices.'
            : lastError === 'logged_out'
              ? 'Logged out. Restart the site or wait for a new QR.'
              : lastError === 'qr_expired'
                ? 'QR expired. Keep this page open and scan the new code.'
                : 'Generating a login QR…',
      })
    }
    if (req.method === 'POST' && req.url === '/send') {
      const payload = await readBody(req)
      const result = await sendMessage(payload.phone, payload.message)
      return json(res, result.success ? 200 : 409, result)
    }
    return json(res, 404, { success: false, error: 'not found' })
  } catch (err) {
    console.error('[wa-bridge]', err)
    return json(res, 500, { success: false, error: err.message })
  }
})

server.listen(PORT, '127.0.0.1', () => {
  console.log(`[wa-bridge] listening on 127.0.0.1:${PORT}`)
  connect().catch((err) => console.error(err))
})
