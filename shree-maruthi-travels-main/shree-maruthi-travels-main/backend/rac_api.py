"""RAC dispatch API backed by Zoho Sheets (JSON fallback)."""
import io
import os
import re
import hmac
from datetime import datetime, timedelta
from functools import wraps
from urllib.parse import quote

from flask import Blueprint, jsonify, request, send_file
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
import requests

import rac_store

rac_bp = Blueprint('rac', __name__)
RAC_EMAIL = os.environ.get('RAC_EMAIL') or 'admin@dispatch.local'
RAC_PASSWORD = os.environ.get('RAC_PASSWORD') or 'Admin@12345'
RAC_USER = {
    'user_id': 'rac-admin-1',
    'email': RAC_EMAIL,
    'first_name': 'Admin',
    'last_name': 'User',
    'role': 'admin',
    'active': True,
}
TOKEN = URLSafeTimedSerializer(os.environ.get('RAC_JWT_SECRET') or os.environ.get('STAFF_TOKEN') or 'smt-rac-zoho-secret', salt='rac-dispatch')

COLUMN_MAPPING = {
    'SL NO': 'sl_no',
    'BOOKING ID': 'source_booking_id',
    'DATE': 'trip_date',
    'NAME': 'source_name',
    'CAB REG NO': 'source_vehicle_no',
    'MOBIL NO': 'source_mobile',
    'PLAND START': 'planned_start',
    'END LOACTION': 'route_text',
    'END LOCATION': 'route_text',
    'PICKUP TIME': 'pickup_time',
    'END TIME': 'end_time',
    'TOTAL HRS SMT': 'total_hours_text',
    'CAB TYPE': 'cab_type',
    'EMP NAME': 'employee_name',
    'START KM': 'start_km',
    'END KM': 'end_km',
    'SMT TOTAL KM': 'total_km',
    'DUTY TYPE': 'duty_type',
    'DRIVER HRS': 'driver_hours',
    'DRIVER KM': 'driver_km',
    'TOLL': 'toll',
    'PARKING': 'parking',
    'AMOUNT': 'amount',
    'REMARKS': 'remarks',
    'DRIVER PAID': 'driver_payment_status',
    'PAYMENT STATUS': 'driver_payment_status',
    'DRIVER PAYMENT': 'driver_payment_status',
}


def _truthy(value):
    return str(value or '').strip().lower() in ('1', 'true', 'yes', 'on')


def _title_label(value, fallback='Unknown'):
    text = str(value or '').strip()
    if not text:
        return fallback
    return text.title()


def _person_label(value, fallback='Unknown'):
    text = re.sub(r'\s+', ' ', str(value or '').strip())
    return text.title() if text else fallback


def _month_key(value):
    text = str(value or '').strip()
    match = re.match(r'^(\d{4})-(\d{2})', text)
    if not match:
        return None
    year, month = int(match.group(1)), int(match.group(2))
    if year < 2024 or year > 2027 or month < 1 or month > 12:
        return None
    return f'{year:04d}-{month:02d}'


def _cab_group(value):
    raw = str(value or '').strip()
    key = re.sub(r'[^a-z0-9]+', '', raw.lower())
    if not key:
        return 'Unknown'
    if 'sedan' in key:
        return 'Sedan'
    if 'ertiga' in key or key in ('ertga', 'ertig'):
        return 'Ertiga'
    if 'cryst' in key or 'creyst' in key or 'innova' in key:
        return 'Crysta'
    if 'ciaz' in key:
        return 'Ciaz'
    if 'etios' in key:
        return 'Etios'
    if 'dzire' in key or 'swift' in key:
        return 'Dzire'
    if 'tempo' in key or 'traveller' in key:
        return 'Tempo Traveller'
    return raw.title()


def _duty_group(value):
    raw = str(value or '').strip()
    key = re.sub(r'[^a-z0-9]+', '', raw.lower())
    if not key:
        return 'Unknown'
    if 'airport' in key:
        return 'Airport'
    if 'outstation' in key or key.startswith('outst'):
        return 'Outstation'
    if key in ('drop', 'dropt', 'localdrop'):
        return 'Drop'
    if '120' in key:
        return '12 Hrs / 120 Km'
    if '80' in key:
        return '8 Hrs / 80 Km'
    return re.sub(r'\s+', ' ', raw).title()


def _area_label(value):
    text = re.sub(r'\s+', ' ', str(value or '').strip())
    if not text:
        return 'Unknown'
    part = re.split(r'\s+(?:TO|-|–)\s+|/', text, maxsplit=1)[0]
    return part.title()[:42] or 'Unknown'


def _fill_months(by_month):
    if not by_month:
        return []
    keys = sorted(by_month)
    start_y, start_m = (int(part) for part in keys[0].split('-'))
    end_y, end_m = (int(part) for part in keys[-1].split('-'))
    filled = []
    year, month = start_y, start_m
    while (year, month) <= (end_y, end_m):
        key = f'{year:04d}-{month:02d}'
        item = by_month.get(key) or {'count': 0, 'km': 0.0}
        filled.append({'month': key, 'count': item['count'], 'km': round(item['km'], 1)})
        month += 1
        if month > 12:
            month = 1
            year += 1
    return filled


def _ranked(mapping, n=10, value_key='count'):
    return [
        {'name': key, value_key: mapping[key]}
        for key in sorted(mapping, key=mapping.get, reverse=True)[:n]
    ]


def _driver_payment_status(value):
    text = str(value or '').strip().lower()
    if text in ('paid', 'yes', 'y', '1', 'true', 'done'):
        return 'Paid'
    return 'Unpaid'


def _paginate(rows, page, limit):
    page = max(int(page or 1), 1)
    limit = max(min(int(limit or 50), 200), 1)
    start = (page - 1) * limit
    return rows[start:start + limit], page, limit, len(rows)


def _auth_user():
    header = request.headers.get('Authorization') or ''
    if header.startswith('Bearer '):
        token = header.split(' ', 1)[1].strip()
        if token:
            try:
                return TOKEN.loads(token, max_age=60 * 60 * 24 * 7)
            except (BadSignature, SignatureExpired):
                pass
    try:
        import staff_auth
        staff = staff_auth.current_staff()
    except Exception:
        staff = None
    if staff and staff.get('email'):
        user = dict(RAC_USER)
        user['email'] = staff['email']
        user['first_name'] = staff['email'].split('@')[0]
        user['role'] = 'admin' if staff.get('role') == 'od' else 'staff'
        return user
    return None


def require_rac(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        user = _auth_user()
        if not user:
            return jsonify({'success': False, 'message': 'Unauthorized - Sign in on the SMT portal first'}), 401
        request.rac_user = user
        return fn(*args, **kwargs)
    return wrapped


def _ingest_key_ok():
    expected = (os.environ.get('RAC_INGEST_KEY') or '').strip()
    provided = (request.headers.get('X-Ingest-Key') or '').strip()
    return bool(expected) and bool(provided) and hmac.compare_digest(expected, provided)


def require_rac_or_ingest(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if _ingest_key_ok():
            user = dict(RAC_USER)
            user['role'] = 'ingest'
            request.rac_user = user
            return fn(*args, **kwargs)
        user = _auth_user()
        if not user:
            return jsonify({'success': False, 'message': 'Unauthorized - Sign in on the SMT portal first'}), 401
        request.rac_user = user
        return fn(*args, **kwargs)
    return wrapped


def _ist_today():
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo('Asia/Kolkata')).date()
    except Exception:
        return datetime.utcnow().date()


def _payment_update(booking, status, notes=None, amount=None):
    return {
        'driver_payment_status': status,
        'driver_paid_at': datetime.utcnow().isoformat() + 'Z' if status == 'Paid' else '',
        'driver_payment_notes': (notes if notes is not None else booking.get('driver_payment_notes') or '')[:500],
        'driver_paid_amount': amount if amount is not None else booking.get('amount') or booking.get('driver_paid_amount') or '',
    }


def _norm_header(value):
    return re.sub(r'\s+', ' ', str(value or '').strip().upper())


def _parse_excel_date(value):
    if value is None or value == '':
        return None
    if hasattr(value, 'strftime'):
        year = value.year + 100 if value.year < 2000 else value.year
        return f'{year:04d}-{value.month:02d}-{value.day:02d}'
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            base = datetime(1899, 12, 30)
            parsed = base + timedelta(days=float(value))
            year = parsed.year + 100 if parsed.year < 2000 else parsed.year
            return f'{year:04d}-{parsed.month:02d}-{parsed.day:02d}'
        except (ValueError, OverflowError):
            return None
    text = str(value).strip().replace(' 00:00:00', '')
    if text.lower() in ('', 'nan', 'nat', 'none'):
        return None
    text = text.replace('.', '-')
    for fmt in ('%Y-%m-%d', '%d-%b-%y', '%d-%b-%Y', '%d/%m/%Y', '%d/%m/%y', '%d-%m-%Y', '%d-%m-%y', '%m/%d/%Y'):
        try:
            parsed = datetime.strptime(text[:20], fmt)
            year = parsed.year + 100 if parsed.year < 2000 else parsed.year
            iso = f'{year:04d}-{parsed.month:02d}-{parsed.day:02d}'
            if fmt == '%m/%d/%Y' and '/' in str(value):
                return _coerce_trip_date(iso)
            return iso
        except ValueError:
            continue
    if '/' in str(value):
        parts = re.split(r'[/-]', str(value).strip())
        if len(parts) >= 3:
            try:
                first, second, year = int(parts[0]), int(parts[1]), int(parts[2][:4])
                if year < 100:
                    year += 2000 if year < 50 else 1900
                return _coerce_trip_date(f'{year:04d}-{second:02d}-{first:02d}')
            except ValueError:
                pass
    return None


def _date_from_booking_id(booking_id):
    text = str(booking_id or '').strip()
    match = re.match(r'^(\d{2})(\d{2})(\d{2})(?:\D|$)', text)
    if not match:
        return None
    year = 2000 + int(match.group(1))
    month = int(match.group(2))
    day = int(match.group(3))
    try:
        return datetime(year, month, day).date()
    except ValueError:
        return None


def _coerce_trip_date(value, booking_id=None):
    text = str(value or '').strip()
    match = re.match(r'^(\d{4})-(\d{2})-(\d{2})', text)
    if not match:
        parsed = _parse_excel_date(value) if value and not text.startswith('20') else None
        match = re.match(r'^(\d{4})-(\d{2})-(\d{2})', str(parsed or ''))
        if not match:
            return text[:10] if text else ''
    year, month, day = (int(part) for part in match.groups())
    try:
        current = datetime(year, month, day).date()
    except ValueError:
        return f'{year:04d}-{month:02d}-{day:02d}'
    today = datetime.utcnow().date()
    horizon = today + timedelta(days=7)
    window_start = datetime(2025, 1, 1).date()

    def valid(yy, mm, dd):
        try:
            return datetime(yy, mm, dd).date()
        except ValueError:
            return None

    def in_window(dt):
        return dt is not None and window_start <= dt <= horizon

    swapped = valid(year, day, month) if day <= 12 and month <= 12 and day != month else None
    id_date = _date_from_booking_id(booking_id)
    if in_window(current):
        return current.strftime('%Y-%m-%d')
    if swapped and in_window(swapped):
        return swapped.strftime('%Y-%m-%d')
    if id_date and in_window(id_date):
        return id_date.strftime('%Y-%m-%d')
    return current.strftime('%Y-%m-%d')


def _format_clock(value):
    parsed = _parse_time(value)
    if not parsed:
        return str(value or '').strip()
    hour, minute = parsed.split(':')
    hour = int(hour)
    suffix = 'AM' if hour < 12 else 'PM'
    return f'{hour % 12 or 12}:{minute} {suffix}'


def _present_booking(row):
    item = dict(row)
    item['trip_date'] = _coerce_trip_date(item.get('trip_date'), item.get('source_booking_id'))
    duty = str(item.get('duty_type') or '').strip()
    if duty:
        grouped = _duty_group(duty)
        item['duty_type'] = duty if grouped == 'Unknown' else grouped
    name = item.get('employee_name') or item.get('source_name') or ''
    item['employee_name'] = _person_label(name, '')
    start = str(item.get('planned_start') or '').strip()
    item['planned_start'] = re.sub(r'\s+', ' ', start).title() if start else ''
    if item.get('pickup_time'):
        item['pickup_time'] = _format_clock(item.get('pickup_time'))
    if item.get('end_time'):
        item['end_time'] = _format_clock(item.get('end_time'))
    if item.get('cab_type'):
        item['cab_type'] = _cab_group(item.get('cab_type'))
    item['amount'] = _parse_number(item.get('amount'), 0)
    item['driver_payment_status'] = _driver_payment_status(item.get('driver_payment_status'))
    return item


def _parse_time(value):
    if not value:
        return None
    text = str(value).strip().upper()
    match = re.search(r'(\d{1,2})[:.](\d{2})', text)
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2))
    if 'PM' in text and hour < 12:
        hour += 12
    if 'AM' in text and hour == 12:
        hour = 0
    if hour > 23 or minute > 59:
        return None
    return f'{hour:02d}:{minute:02d}'


def _sort_value(row, field, kind):
    if '.' in field:
        current = row
        for part in field.split('.'):
            current = (current or {}).get(part) if isinstance(current, dict) else None
        raw = current
    else:
        raw = row.get(field)
    if kind == 'date':
        text = str(raw or '').strip()
        if re.match(r'^\d{4}-\d{2}-\d{2}', text):
            return text.replace('T', ' ')[:19]
        parsed = _parse_excel_date(raw)
        return parsed or '0000-00-00'
    if kind == 'number':
        return _parse_number(raw, 0)
    if kind == 'time':
        return _parse_time(raw) or '99:99'
    if kind == 'bool':
        return 1 if raw in (True, 'true', 'True', 1, '1', 'Paid', 'paid') else 0
    return str(raw or '').strip().lower()


def _sort_rows(rows, sort_by, sort_order, allowed):
    field = sort_by if sort_by in allowed else next(iter(allowed))
    kind = allowed[field]
    reverse = str(sort_order or 'DESC').upper() != 'ASC'
    rows.sort(key=lambda row: _sort_value(row, field, kind), reverse=reverse)
    return rows


def _parse_number(value, default=0):
    if value is None or value == '':
        return default
    if isinstance(value, (int, float)):
        return value
    matches = re.findall(r'\d+(?:\.\d+)?', str(value))
    if not matches:
        return default
    try:
        return float(matches[-1])
    except ValueError:
        return default


def _phone_digits(phone):
    digits = re.sub(r'\D', '', str(phone or ''))
    if len(digits) == 10:
        digits = '91' + digits
    return digits


def _wa_link(phone, body):
    digits = _phone_digits(phone)
    if not digits:
        return ''
    return f'https://wa.me/{digits}?text={quote(body or "")}'


WA_BRIDGE_URL = os.environ.get('WA_BRIDGE_URL') or 'http://127.0.0.1:3100'


def _wa_bridge_status():
    try:
        data = requests.get(f'{WA_BRIDGE_URL}/status', timeout=4).json()
        data.setdefault('success', True)
        data.setdefault('provider', 'wwebjs')
        return data
    except Exception:
        return {
            'success': True,
            'provider': 'wwebjs',
            'isReady': False,
            'qr': None,
            'message': 'WhatsApp linker is starting. Refresh in a few seconds.',
        }


def _wa_bridge_send(phone, body):
    try:
        data = requests.post(
            f'{WA_BRIDGE_URL}/send',
            json={'phone': phone, 'message': body},
            timeout=25,
        ).json()
        return bool(data.get('success')), data
    except Exception as exc:
        return False, {'error': str(exc)}


def _display_date(value):
    text = str(value or '').strip()
    match = re.match(r'^(\d{4})-(\d{2})-(\d{2})', text)
    if not match:
        return text or 'N/A'
    months = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')
    year, month, day = match.group(1), int(match.group(2)), int(match.group(3))
    if month < 1 or month > 12:
        return text
    return f'{int(day)} {months[month - 1]} {year}'


def _whatsapp_body(booking):
    booking = _present_booking(booking)
    pickup = (booking.get('pickup_time') or 'N/A')
    end = (booking.get('end_time') or 'N/A')
    route = booking.get('route_text') or 'N/A'
    if len(str(route)) > 100:
        route = str(route)[:100] + '...'
    return (
        'New Ride Assigned\n\n'
        f"Booking ID: {booking.get('source_booking_id')}\n"
        f"Date: {_display_date(booking.get('trip_date'))}\n"
        f"Employee: {booking.get('employee_name')}\n"
        f"Pickup: {booking.get('planned_start') or 'N/A'}\n"
        f"Route: {route}\n"
        f"Pickup Time: {pickup}\n"
        f"End Time: {end}\n"
        f"Duty Type: {booking.get('duty_type') or 'N/A'}\n"
        f"Cab Type: {booking.get('cab_type') or 'N/A'}\n"
        f"Amount: ₹{booking.get('amount') or 0}\n\n"
        'Please confirm this trip.'
    )


@rac_bp.route('/auth/staff', methods=['GET'])
def staff_session():
    import staff_auth
    staff = staff_auth.current_staff()
    user = dict(RAC_USER)
    if staff and staff.get('email'):
        user['email'] = staff['email']
        user['first_name'] = staff['email'].split('@')[0]
        user['role'] = 'admin' if staff.get('role') == 'od' else 'staff'
    return jsonify({'success': True, 'token': TOKEN.dumps(user), 'user': user})


@rac_bp.route('/auth/login', methods=['POST'])
def login():
    payload = request.get_json(silent=True) or {}
    email = (payload.get('email') or '').strip().lower()
    password = payload.get('password') or ''
    if email != RAC_EMAIL.strip().lower() or password != RAC_PASSWORD:
        return jsonify({'success': False, 'message': 'Invalid email or password'}), 401
    token = TOKEN.dumps(RAC_USER)
    return jsonify({'success': True, 'token': token, 'user': RAC_USER})


@rac_bp.route('/auth/logout', methods=['POST'])
def logout():
    return jsonify({'success': True, 'message': 'Logged out successfully'})


@rac_bp.route('/auth/user', methods=['GET'])
@require_rac
def current_user():
    return jsonify({'success': True, 'user': request.rac_user})


@rac_bp.route('/dashboard/summary', methods=['GET'])
@require_rac
def dashboard_summary():
    today = datetime.utcnow().strftime('%Y-%m-%d')
    bookings = rac_store.all_rows('bookings')
    uploads = rac_store.all_rows('uploads')
    messages = rac_store.all_rows('messages')
    uploaded_today = sum(1 for row in uploads if str(row.get('uploaded_at') or row.get('created_at') or '').startswith(today))

    def when(*values):
        for value in values:
            text = str(value or '').strip()
            if text:
                return text
        return ''

    activity = []
    for row in uploads[-8:]:
        activity.append({
            'kind': 'upload',
            'title': 'Booking uploaded',
            'detail': row.get('file_name') or 'Excel file added to the system',
            'at': when(row.get('uploaded_at'), row.get('created_at')),
        })
    for row in messages[-10:]:
        sent = row.get('send_status') == 'sent'
        activity.append({
            'kind': 'message' if sent else 'message-fail',
            'title': 'Message sent' if sent else 'Message failed',
            'detail': row.get('phone_number') or row.get('driver_name') or 'WhatsApp notification',
            'at': when(row.get('sent_at'), row.get('created_at'), row.get('updated_at')),
        })
    recent_bookings = sorted(
        bookings,
        key=lambda row: when(row.get('updated_at'), row.get('created_at'), row.get('trip_date')),
        reverse=True,
    )[:12]
    for row in recent_bookings:
        status = row.get('status') or ''
        bid = row.get('source_booking_id') or row.get('booking_id') or ''
        if status == 'Assigned':
            activity.append({
                'kind': 'assigned',
                'title': 'Driver assigned',
                'detail': f"{row.get('driver_name') or row.get('source_name') or 'Driver'} · {bid}",
                'at': when(row.get('updated_at'), row.get('created_at')),
            })
        elif status == 'Completed':
            activity.append({
                'kind': 'completed',
                'title': 'Trip completed',
                'detail': f"{bid} marked as completed",
                'at': when(row.get('updated_at'), row.get('created_at')),
            })
    activity = [item for item in activity if item['at']]
    activity.sort(key=lambda item: item['at'], reverse=True)

    return jsonify({
        'success': True,
        'data': {
            'total_uploaded_today': uploaded_today,
            'unassigned_rides': sum(1 for row in bookings if row.get('status') == 'Unassigned'),
            'assigned_rides': sum(1 for row in bookings if row.get('status') == 'Assigned'),
            'completed_rides': sum(1 for row in bookings if row.get('status') == 'Completed'),
            'cancelled_rides': sum(1 for row in bookings if row.get('status') == 'Cancelled'),
            'total_bookings': len(bookings),
            'unpaid_driver_payments': sum(
                1 for row in bookings
                if row.get('status') in ('Assigned', 'Completed')
                and _driver_payment_status(row.get('driver_payment_status')) != 'Paid'
            ),
            'message_sent_count': sum(1 for row in messages if row.get('send_status') == 'sent'),
            'message_failed_count': sum(1 for row in messages if row.get('send_status') in ('failed', 'skipped')),
            'upload_timestamp': datetime.utcnow().isoformat() + 'Z',
            'recent_activity': activity[:8],
        }
    })


@rac_bp.route('/dashboard/insights', methods=['GET'])
@require_rac
def dashboard_insights():
    try:
        bookings = rac_store.all_rows('bookings')
        by_month = {}
        by_driver = {}
        by_cab = {}
        by_area = {}
        by_duty = {}
        total_km = 0.0
        employees = set()
        for row in bookings:
            month = _month_key(_coerce_trip_date(row.get('trip_date'), row.get('source_booking_id')))
            try:
                km = float(row.get('total_km') or 0)
            except (TypeError, ValueError):
                km = 0.0
            total_km += km
            if month:
                bucket = by_month.setdefault(month, {'count': 0, 'km': 0.0})
                bucket['count'] += 1
                bucket['km'] += km
            driver = _person_label(row.get('driver_name') or row.get('source_name'))
            by_driver[driver] = by_driver.get(driver, 0) + 1
            cab = _cab_group(row.get('cab_type'))
            by_cab[cab] = by_cab.get(cab, 0) + 1
            area = _area_label(row.get('planned_start'))
            by_area[area] = by_area.get(area, 0) + 1
            duty = _duty_group(row.get('duty_type'))
            by_duty[duty] = by_duty.get(duty, 0) + 1
            emp = _person_label(row.get('employee_name'), '')
            if emp:
                employees.add(emp.upper())
        return jsonify({
            'success': True,
            'data': {
                'total_trips': len(bookings),
                'total_km': round(total_km, 1),
                'unique_drivers': len(by_driver),
                'unique_employees': len(employees),
                'by_month': _fill_months(by_month),
                'top_drivers': _ranked(by_driver, 10),
                'by_cab': _ranked(by_cab, 8),
                'by_duty': _ranked(by_duty, 8),
                'top_areas': _ranked(by_area, 10),
            },
        })
    except Exception as exc:
        return jsonify({'success': False, 'message': f'Could not build insights: {exc}'}), 500


@rac_bp.route('/whatsapp/status', methods=['GET'])
def whatsapp_status():
    return jsonify(_wa_bridge_status())


@rac_bp.route('/drivers', methods=['GET'])
@require_rac
def list_drivers():
    search = (request.args.get('search') or '').strip().lower()
    active_only = _truthy(request.args.get('active_only', 'true'))
    rows = rac_store.all_rows('drivers')
    if active_only:
        rows = [row for row in rows if row.get('active_status', True)]
    if search:
        rows = [
            row for row in rows
            if search in str(row.get('driver_name', '')).lower()
            or search in str(row.get('vehicle_number', '')).lower()
            or search in str(row.get('whatsapp_number', '')).lower()
        ]
    _sort_rows(rows, request.args.get('sort_by') or 'driver_name', request.args.get('sort_order') or 'ASC', {
        'driver_name': 'text',
        'whatsapp_number': 'text',
        'vehicle_number': 'text',
        'vehicle_type': 'text',
        'home_area': 'text',
        'total_assignments': 'number',
        'active_status': 'bool',
    })
    page_rows, page, limit, total = _paginate(rows, request.args.get('page'), request.args.get('limit'))
    return jsonify({
        'success': True,
        'data': page_rows,
        'pagination': {'page': page, 'limit': limit, 'total': total},
    })


@rac_bp.route('/drivers', methods=['POST'])
@require_rac
def create_driver():
    payload = request.get_json(silent=True) or {}
    name = (payload.get('driver_name') or '').strip()
    phone = (payload.get('whatsapp_number') or '').strip()
    if not name:
        return jsonify({'success': False, 'message': 'Driver name is required'}), 400
    existing_name = next(
        (row for row in rac_store.all_rows('drivers') if str(row.get('driver_name') or '').strip().lower() == name.lower()),
        None,
    )
    if existing_name:
        return jsonify({'success': False, 'message': 'Driver name already exists'}), 409
    if phone and rac_store.find_one('drivers', 'whatsapp_number', phone):
        return jsonify({'success': False, 'message': 'WhatsApp number already exists'}), 409
    driver = rac_store.insert('drivers', {
        'driver_id': rac_store.new_id('drv'),
        'driver_name': name,
        'whatsapp_number': phone,
        'alternate_number': payload.get('alternate_number') or '',
        'vehicle_number': payload.get('vehicle_number') or '',
        'vehicle_type': payload.get('vehicle_type') or '',
        'home_area': payload.get('home_area') or '',
        'notes': payload.get('notes') or '',
        'active_status': True,
        'total_assignments': 0,
    })
    return jsonify({'success': True, 'message': 'Driver created successfully', 'driver_id': driver['driver_id']}), 201


@rac_bp.route('/drivers/<driver_id>', methods=['GET'])
@require_rac
def get_driver(driver_id):
    driver = rac_store.find_one('drivers', 'driver_id', driver_id)
    if not driver:
        return jsonify({'success': False, 'message': 'Driver not found'}), 404
    return jsonify({'success': True, 'data': driver})


@rac_bp.route('/drivers/<driver_id>', methods=['PUT'])
@require_rac
def update_driver(driver_id):
    driver = rac_store.find_one('drivers', 'driver_id', driver_id)
    if not driver:
        return jsonify({'success': False, 'message': 'Driver not found'}), 404
    payload = request.get_json(silent=True) or {}
    phone = payload.get('whatsapp_number')
    if phone and phone != driver.get('whatsapp_number'):
        existing = rac_store.find_one('drivers', 'whatsapp_number', phone)
        if existing:
            return jsonify({'success': False, 'message': 'WhatsApp number already exists'}), 409
    rac_store.update_one('drivers', 'driver_id', driver_id, {
        'driver_name': payload.get('driver_name') or driver.get('driver_name'),
        'whatsapp_number': phone or driver.get('whatsapp_number'),
        'alternate_number': payload.get('alternate_number', driver.get('alternate_number')),
        'vehicle_number': payload.get('vehicle_number', driver.get('vehicle_number')),
        'vehicle_type': payload.get('vehicle_type', driver.get('vehicle_type')),
        'home_area': payload.get('home_area', driver.get('home_area')),
        'notes': payload.get('notes', driver.get('notes')),
    })
    return jsonify({'success': True, 'message': 'Driver updated successfully'})


@rac_bp.route('/drivers/<driver_id>/status', methods=['PATCH'])
@require_rac
def update_driver_status(driver_id):
    if not rac_store.find_one('drivers', 'driver_id', driver_id):
        return jsonify({'success': False, 'message': 'Driver not found'}), 404
    payload = request.get_json(silent=True) or {}
    rac_store.update_one('drivers', 'driver_id', driver_id, {'active_status': bool(payload.get('active_status'))})
    return jsonify({'success': True, 'message': 'Driver status updated'})


@rac_bp.route('/bookings', methods=['GET'])
@require_rac
def list_bookings():
    date = request.args.get('date') or ''
    month = request.args.get('month') or ''
    from_date = request.args.get('from_date') or ''
    to_date = request.args.get('to_date') or ''
    days = request.args.get('days') or ''
    status = request.args.get('status') or ''
    search = (request.args.get('search') or '').strip().lower()
    payment = request.args.get('payment') or ''
    assigned = request.args.get('assigned_driver_id') or ''
    rows = [_present_booking(row) for row in rac_store.all_rows('bookings')]
    months = sorted({
        key for key in (
            str(row.get('trip_date') or '')[:7] for row in rows
        ) if re.match(r'^\d{4}-\d{2}$', key)
    })
    if date:
        rows = [row for row in rows if str(row.get('trip_date') or '')[:10] == date]
    if month:
        rows = [row for row in rows if str(row.get('trip_date') or '').startswith(month)]
    if not date and days:
        try:
            span = max(1, min(int(days), 31))
        except (TypeError, ValueError):
            span = 3
        start = (_ist_today() - timedelta(days=span - 1)).strftime('%Y-%m-%d')
        end = _ist_today().strftime('%Y-%m-%d')
        rows = [row for row in rows if start <= str(row.get('trip_date') or '')[:10] <= end]
    if from_date:
        rows = [row for row in rows if str(row.get('trip_date') or '')[:10] >= from_date]
    if to_date:
        rows = [row for row in rows if str(row.get('trip_date') or '')[:10] <= to_date]
    if assigned:
        rows = [row for row in rows if str(row.get('assigned_driver_id') or '') == assigned]
    if search:
        rows = [
            row for row in rows
            if search in str(row.get('source_booking_id', '')).lower()
            or search in str(row.get('employee_name', '')).lower()
            or search in str(row.get('source_name', '')).lower()
        ]
    stats_rows = list(rows)
    if status:
        rows = [row for row in rows if row.get('status') == status]
    if payment:
        want_paid = payment.lower() == 'paid'
        rows = [
            row for row in rows
            if (_driver_payment_status(row.get('driver_payment_status')) == 'Paid') == want_paid
        ]
    sort_by = request.args.get('sort_by') or 'trip_date'
    sort_order = request.args.get('sort_order') or 'DESC'
    _sort_rows(rows, sort_by, sort_order, {
        'source_booking_id': 'text',
        'trip_date': 'date',
        'employee_name': 'text',
        'planned_start': 'text',
        'pickup_time': 'time',
        'duty_type': 'text',
        'amount': 'number',
        'status': 'text',
        'driver_payment_status': 'text',
        'cab_type': 'text',
        'total_km': 'number',
    })
    page_rows, page, limit, total = _paginate(rows, request.args.get('page'), request.args.get('limit'))
    return jsonify({
        'success': True,
        'data': page_rows,
        'summary': {
            'total': len(stats_rows),
            'unassigned': sum(1 for row in stats_rows if row.get('status') == 'Unassigned'),
            'assigned': sum(1 for row in stats_rows if row.get('status') == 'Assigned'),
            'completed': sum(1 for row in stats_rows if row.get('status') == 'Completed'),
            'cancelled': sum(1 for row in stats_rows if row.get('status') == 'Cancelled'),
            'driver_unpaid': sum(
                1 for row in stats_rows
                if _driver_payment_status(row.get('driver_payment_status')) != 'Paid'
            ),
            'driver_paid': sum(
                1 for row in stats_rows
                if _driver_payment_status(row.get('driver_payment_status')) == 'Paid'
            ),
            'months': months,
            'today': _ist_today().strftime('%Y-%m-%d'),
        },
        'pagination': {'page': page, 'limit': limit, 'total': total},
    })


@rac_bp.route('/bookings/ingest', methods=['POST'])
@require_rac_or_ingest
def ingest_bookings():
    payload = request.get_json(silent=True) or {}
    rows = payload.get('bookings') or payload.get('data') or []
    if isinstance(payload, dict) and payload.get('booking_id') and not rows:
        rows = [payload]
    if not isinstance(rows, list) or not rows:
        return jsonify({'success': False, 'message': 'No bookings provided'}), 400
    created = []
    updated = []
    errors = []
    for raw in rows[:200]:
        if not isinstance(raw, dict):
            errors.append({'booking_id': '', 'error': 'Row is not an object'})
            continue
        source_id = str(raw.get('booking_id') or raw.get('source_booking_id') or '').strip()
        if not source_id:
            errors.append({'booking_id': '', 'error': 'booking_id is missing'})
            continue
        trip_date = _coerce_trip_date(
            _parse_excel_date(raw.get('trip_date')) or raw.get('trip_date'),
            source_id,
        )
        pickup = _parse_time(raw.get('trip_time') or raw.get('pickup_time')) or str(raw.get('trip_time') or raw.get('pickup_time') or '').strip()
        duty = str(raw.get('booking_type') or raw.get('duty_type') or '').strip()
        cab = str(raw.get('cab_type') or '').strip()
        start = str(raw.get('planned_start_address') or raw.get('planned_start') or '').strip()
        existing = rac_store.find_one('bookings', 'source_booking_id', source_id)
        if existing:
            changes = {
                'trip_date': trip_date or existing.get('trip_date'),
                'pickup_time': pickup or existing.get('pickup_time'),
                'duty_type': duty or existing.get('duty_type'),
                'cab_type': cab or existing.get('cab_type'),
                'planned_start': start or existing.get('planned_start'),
                'ingest_source': 'whatsapp-group',
                'ingest_message_id': str(raw.get('source_message_id') or '')[:120],
            }
            rac_store.update_one('bookings', 'booking_id', existing.get('booking_id'), changes)
            updated.append(source_id)
            continue
        rac_store.insert('bookings', {
            'booking_id': rac_store.new_id('bkg'),
            'source_booking_id': source_id,
            'trip_date': trip_date,
            'pickup_time': pickup,
            'duty_type': duty,
            'cab_type': cab,
            'planned_start': start,
            'employee_name': str(raw.get('employee_name') or 'WhatsApp booking').strip(),
            'source_name': 'WhatsApp group',
            'status': 'Unassigned',
            'upload_batch_id': '',
            'assigned_driver_id': '',
            'assigned_at': '',
            'driver_payment_status': 'Unpaid',
            'driver_paid_at': '',
            'driver_payment_notes': '',
            'driver_paid_amount': '',
            'amount': _parse_number(raw.get('amount'), 0),
            'ingest_source': 'whatsapp-group',
            'ingest_message_id': str(raw.get('source_message_id') or '')[:120],
            'ingest_confidence': raw.get('confidence') or '',
        })
        created.append(source_id)
    return jsonify({
        'success': True,
        'created': created,
        'updated': updated,
        'errors': errors,
        'created_count': len(created),
        'updated_count': len(updated),
    }), 201 if created else 200


@rac_bp.route('/bookings/payments/bulk', methods=['PATCH'])
@require_rac
def bulk_booking_payment():
    payload = request.get_json(silent=True) or {}
    ids = payload.get('booking_ids') or []
    if not isinstance(ids, list) or not ids:
        return jsonify({'success': False, 'message': 'booking_ids is required'}), 400
    paid = payload.get('paid')
    status = _driver_payment_status(payload.get('driver_payment_status') or payload.get('status'))
    if paid is not None:
        status = 'Paid' if paid in (True, 'true', '1', 1, 'Paid', 'paid', 'yes') else 'Unpaid'
    updated = 0
    missing = []
    for booking_id in ids[:500]:
        booking = rac_store.find_one('bookings', 'booking_id', str(booking_id))
        if not booking:
            missing.append(str(booking_id))
            continue
        rac_store.update_one('bookings', 'booking_id', booking.get('booking_id'), _payment_update(booking, status))
        updated += 1
    return jsonify({
        'success': True,
        'message': f'{updated} booking(s) marked {status}',
        'updated': updated,
        'missing': missing,
        'driver_payment_status': status,
    })


@rac_bp.route('/bookings/<booking_id>', methods=['GET'])
@require_rac
def get_booking(booking_id):
    booking = rac_store.find_one('bookings', 'booking_id', booking_id)
    if not booking:
        return jsonify({'success': False, 'message': 'Booking not found'}), 404
    assigned = None
    if booking.get('assigned_driver_id'):
        assigned = rac_store.find_one('drivers', 'driver_id', booking.get('assigned_driver_id'))
    payload = _present_booking(booking)
    payload['assignedDriver'] = assigned
    return jsonify({'success': True, 'data': payload})


@rac_bp.route('/bookings/<booking_id>/status', methods=['PATCH'])
@require_rac
def update_booking_status(booking_id):
    if not rac_store.find_one('bookings', 'booking_id', booking_id):
        return jsonify({'success': False, 'message': 'Booking not found'}), 404
    payload = request.get_json(silent=True) or {}
    rac_store.update_one('bookings', 'booking_id', booking_id, {'status': payload.get('status')})
    return jsonify({'success': True, 'message': 'Booking status updated'})


@rac_bp.route('/bookings/<booking_id>/payment', methods=['PATCH'])
@require_rac
def update_booking_payment(booking_id):
    booking = rac_store.find_one('bookings', 'booking_id', booking_id)
    if not booking:
        return jsonify({'success': False, 'message': 'Booking not found'}), 404
    payload = request.get_json(silent=True) or {}
    paid = payload.get('paid')
    if paid is None:
        status = _driver_payment_status(payload.get('driver_payment_status') or payload.get('status'))
    else:
        status = 'Paid' if paid in (True, 'true', '1', 1, 'Paid', 'paid', 'yes') else 'Unpaid'
    notes = (payload.get('notes') or payload.get('driver_payment_notes') or booking.get('driver_payment_notes') or '')[:500]
    amount = payload.get('amount', booking.get('amount') or '')
    rac_store.update_one('bookings', 'booking_id', booking_id, _payment_update(booking, status, notes, amount))
    return jsonify({'success': True, 'message': f'Driver payment marked {status}', 'driver_payment_status': status})


@rac_bp.route('/uploads/template.xlsx', methods=['GET'])
@require_rac
def booking_template():
    import pandas as pd
    columns = [
        'SL NO', 'BOOKING ID', 'DATE', 'NAME', 'CAB REG NO', 'MOBIL NO',
        'PLAND START', 'END LOACTION', 'PICKUP TIME', 'END TIME', 'TOTAL HRS SMT',
        'CAB TYPE', 'EMP NAME', 'START KM', 'END KM', 'SMT TOTAL KM', 'DUTY TYPE',
        'DRIVER HRS', 'DRIVER KM', 'TOLL', 'PARKING', 'AMOUNT', 'REMARKS'
    ]
    sample = [{
        'SL NO': 1,
        'BOOKING ID': 'SMT-1001',
        'DATE': '09/09/2026',
        'NAME': 'Traveltime',
        'CAB REG NO': 'KA01AB1234',
        'MOBIL NO': '9876543210',
        'PLAND START': 'Whitefield',
        'END LOACTION': 'MG Road',
        'PICKUP TIME': '08:00',
        'END TIME': '18:00',
        'TOTAL HRS SMT': '10',
        'CAB TYPE': 'SEDAN',
        'EMP NAME': 'Sample Employee',
        'START KM': 10,
        'END KM': 80,
        'SMT TOTAL KM': 70,
        'DUTY TYPE': 'Local',
        'DRIVER HRS': 10,
        'DRIVER KM': 70,
        'TOLL': 0,
        'PARKING': 0,
        'AMOUNT': 2500,
        'REMARKS': 'Sample row — delete before real upload',
    }]
    buffer = io.BytesIO()
    pd.DataFrame(sample, columns=columns).to_excel(buffer, index=False)
    buffer.seek(0)
    return send_file(
        buffer,
        as_attachment=True,
        download_name='smt-booking-template.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )


@rac_bp.route('/uploads/history', methods=['GET'])
@require_rac
def upload_history():
    status = request.args.get('status') or ''
    rows = rac_store.all_rows('uploads')
    if status:
        rows = [row for row in rows if row.get('import_status') == status]
    rows.sort(key=lambda row: str(row.get('uploaded_at') or row.get('created_at') or ''), reverse=True)
    page_rows, page, limit, total = _paginate(rows, request.args.get('page'), request.args.get('limit'))
    return jsonify({
        'success': True,
        'data': page_rows,
        'pagination': {'page': page, 'limit': limit, 'total': total},
    })


@rac_bp.route('/uploads/<batch_id>/status', methods=['GET'])
@require_rac
def upload_status(batch_id):
    batch = rac_store.find_one('uploads', 'batch_id', batch_id)
    if not batch:
        return jsonify({'success': False, 'message': 'Batch not found'}), 404
    return jsonify({
        'success': True,
        'batch_id': batch.get('batch_id'),
        'file_name': batch.get('file_name'),
        'import_status': batch.get('import_status'),
        'total_rows': batch.get('total_rows'),
        'success_rows': batch.get('success_rows'),
        'failed_rows': batch.get('failed_rows'),
        'error_summary': batch.get('error_summary') or [],
        'processed_at': batch.get('updated_at'),
    })


@rac_bp.route('/uploads/excel', methods=['POST'])
@require_rac
def upload_excel():
    upload = request.files.get('file')
    if not upload or not upload.filename:
        return jsonify({'success': False, 'message': 'No file uploaded'}), 400
    name = upload.filename.lower()
    if not name.endswith(('.xlsx', '.xls')):
        return jsonify({'success': False, 'message': 'Only Excel files are allowed'}), 400
    raw = upload.read()
    try:
        import pandas as pd
        frame = pd.read_excel(io.BytesIO(raw))
    except Exception as exc:
        return jsonify({'success': False, 'message': f'Could not read Excel: {exc}'}), 400
    if frame.empty:
        return jsonify({'success': False, 'message': 'Excel file is empty'}), 400

    batch_id = rac_store.new_id('batch')
    existing_ids = {str(row.get('source_booking_id')) for row in rac_store.all_rows('bookings')}
    processed = []
    errors = []
    for index, raw in frame.iterrows():
        mapped = {}
        for column, value in raw.items():
            if pd.isna(value):
                continue
            field = COLUMN_MAPPING.get(_norm_header(column))
            if field is not None:
                mapped[field] = value
        mapped['trip_date'] = _coerce_trip_date(
            _parse_excel_date(mapped.get('trip_date')),
            mapped.get('source_booking_id'),
        )
        mapped['pickup_time'] = _parse_time(mapped.get('pickup_time'))
        mapped['end_time'] = _parse_time(mapped.get('end_time'))
        for key in ('start_km', 'end_km', 'total_km', 'driver_hours', 'driver_km', 'toll', 'parking', 'amount'):
            mapped[key] = _parse_number(mapped.get(key), 0)
        row_number = int(index) + 2
        missing = []
        if not mapped.get('source_booking_id'):
            missing.append('Booking ID is empty')
        if not mapped.get('employee_name'):
            missing.append('Employee name is empty')
        if not mapped.get('trip_date'):
            missing.append('Trip date is invalid or missing')
        booking_id = str(mapped.get('source_booking_id') or '')
        if booking_id and booking_id in existing_ids:
            missing.append('Booking ID already exists')
        if missing:
            errors.append({'row_number': row_number, 'booking_id': booking_id, 'error': '; '.join(missing)})
            continue
        existing_ids.add(booking_id)
        payment_status = _driver_payment_status(mapped.get('driver_payment_status'))
        field_values = {}
        for key in COLUMN_MAPPING.values():
            if key == 'driver_payment_status':
                continue
            field_values[key] = '' if mapped.get(key) is None else mapped.get(key)
        processed.append({
            **field_values,
            'booking_id': rac_store.new_id('bkg'),
            'source_booking_id': booking_id,
            'status': 'Unassigned',
            'upload_batch_id': batch_id,
            'assigned_driver_id': '',
            'assigned_at': '',
            'driver_payment_status': payment_status,
            'driver_paid_at': datetime.utcnow().isoformat() + 'Z' if payment_status == 'Paid' else '',
            'driver_payment_notes': '',
            'driver_paid_amount': mapped.get('amount') or '',
        })

    rac_store.insert('uploads', {
        'batch_id': batch_id,
        'file_name': upload.filename,
        'file_size': upload.content_length or 0,
        'uploaded_by': request.rac_user.get('user_id'),
        'uploaded_at': datetime.utcnow().isoformat() + 'Z',
        'total_rows': int(len(frame)),
        'success_rows': len(processed),
        'failed_rows': len(errors),
        'import_status': 'failed' if not processed else 'completed',
        'error_summary': errors,
    })
    if processed:
        rac_store.insert_many('bookings', processed)
    try:
        import file_archive
        file_archive.archive_bytes('rac-upload', upload.filename, raw, request.rac_user.get('email'))
    except Exception as exc:
        print(f'[RAC] WorkDrive archive skipped: {exc}')
    return jsonify({
        'success': True,
        'batch_id': batch_id,
        'message': f'File processed: {len(processed)} rows imported, {len(errors)} rows failed',
        'status': 'completed' if processed else 'failed',
        'total_rows': int(len(frame)),
        'success_rows': len(processed),
        'failed_rows': len(errors),
        'errors': errors,
    }), 201


@rac_bp.route('/assignments', methods=['POST'])
@require_rac
def create_assignment():
    payload = request.get_json(silent=True) or {}
    booking_id = payload.get('booking_id')
    driver_id = payload.get('driver_id')
    if not booking_id or not driver_id:
        return jsonify({'success': False, 'message': 'Booking ID and Driver ID required'}), 400
    booking = rac_store.find_one('bookings', 'booking_id', booking_id)
    if not booking:
        return jsonify({'success': False, 'message': 'Booking not found'}), 404
    if booking.get('assigned_driver_id'):
        return jsonify({'success': False, 'message': 'Booking is already assigned'}), 409
    driver = rac_store.find_one('drivers', 'driver_id', driver_id)
    if not driver:
        return jsonify({'success': False, 'message': 'Driver not found'}), 404
    assignment_id = rac_store.new_id('asg')
    rac_store.insert('assignments', {
        'assignment_id': assignment_id,
        'booking_id': booking_id,
        'driver_id': driver_id,
        'assigned_by': request.rac_user.get('user_id'),
        'assignment_notes': (payload.get('assignment_notes') or '')[:500],
        'whatsapp_message_status': 'skipped',
    })
    rac_store.update_one('bookings', 'booking_id', booking_id, {
        'status': 'Assigned',
        'assigned_driver_id': driver_id,
        'assigned_at': datetime.utcnow().isoformat() + 'Z',
    })
    rac_store.update_one('drivers', 'driver_id', driver_id, {
        'total_assignments': int(driver.get('total_assignments') or 0) + 1,
    })
    body = _whatsapp_body(booking)
    wa_link = _wa_link(driver.get('whatsapp_number'), body)
    sent, send_info = (False, {})
    if payload.get('send_message_now', True):
        sent, send_info = _wa_bridge_send(driver.get('whatsapp_number'), body)
    send_status = 'sent' if sent else 'ready'
    rac_store.update_one('assignments', 'assignment_id', assignment_id, {
        'whatsapp_message_status': send_status,
    })
    rac_store.insert('messages', {
        'message_log_id': rac_store.new_id('msg'),
        'booking_id': booking_id,
        'driver_id': driver_id,
        'assignment_id': assignment_id,
        'phone_number': driver.get('whatsapp_number'),
        'message_body': body,
        'provider_name': 'wwebjs',
        'send_status': send_status,
        'wa_link': wa_link,
        'error_message': '' if sent else (send_info.get('error') or ''),
    })
    return jsonify({
        'success': True,
        'message': 'Booking assigned successfully',
        'assignment_id': assignment_id,
        'whatsapp_status': send_status,
        'wa_link': wa_link,
        'message_body': body,
        'driver_name': driver.get('driver_name'),
        'phone_number': driver.get('whatsapp_number'),
        'whatsapp_error': send_info.get('error') if not sent else '',
    }), 201


@rac_bp.route('/assignments/<assignment_id>', methods=['GET'])
@require_rac
def get_assignment(assignment_id):
    assignment = rac_store.find_one('assignments', 'assignment_id', assignment_id)
    if not assignment:
        return jsonify({'success': False, 'message': 'Assignment not found'}), 404
    booking = rac_store.find_one('bookings', 'booking_id', assignment.get('booking_id')) or {}
    driver = rac_store.find_one('drivers', 'driver_id', assignment.get('driver_id')) or {}
    payload = dict(assignment)
    payload['booking'] = {
        'source_booking_id': booking.get('source_booking_id'),
        'employee_name': booking.get('employee_name'),
    }
    payload['driver'] = {
        'driver_name': driver.get('driver_name'),
        'whatsapp_number': driver.get('whatsapp_number'),
    }
    return jsonify({'success': True, 'data': payload})


@rac_bp.route('/assignments/<assignment_id>/resend-message', methods=['POST'])
@require_rac
def resend_message(assignment_id):
    assignment = rac_store.find_one('assignments', 'assignment_id', assignment_id)
    if not assignment:
        return jsonify({'success': False, 'message': 'Assignment not found'}), 404
    booking = rac_store.find_one('bookings', 'booking_id', assignment.get('booking_id')) or {}
    driver = rac_store.find_one('drivers', 'driver_id', assignment.get('driver_id')) or {}
    body = _whatsapp_body(booking)
    wa_link = _wa_link(driver.get('whatsapp_number'), body)
    sent, send_info = _wa_bridge_send(driver.get('whatsapp_number'), body)
    send_status = 'sent' if sent else 'ready'
    rac_store.update_one('assignments', 'assignment_id', assignment_id, {'whatsapp_message_status': send_status})
    return jsonify({
        'success': True,
        'message': 'Message sent from your linked WhatsApp' if sent else 'WhatsApp is not linked yet. Scan the QR, or open the chat on your phone.',
        'whatsapp_message_status': send_status,
        'wa_link': wa_link,
        'message_body': body,
        'driver_name': driver.get('driver_name'),
        'phone_number': driver.get('whatsapp_number'),
        'whatsapp_error': send_info.get('error') if not sent else '',
    })


@rac_bp.route('/messages', methods=['GET'])
@require_rac
def list_messages():
    status = request.args.get('send_status') or ''
    rows = rac_store.all_rows('messages')
    if status:
        rows = [row for row in rows if row.get('send_status') == status]
    enriched = []
    for row in rows:
        item = dict(row)
        booking = rac_store.find_one('bookings', 'booking_id', row.get('booking_id')) or {}
        driver = rac_store.find_one('drivers', 'driver_id', row.get('driver_id')) or {}
        item['booking'] = {'source_booking_id': booking.get('source_booking_id')}
        item['driver'] = {'driver_name': driver.get('driver_name')}
        enriched.append(item)
    _sort_rows(enriched, request.args.get('sort_by') or 'created_at', request.args.get('sort_order') or 'DESC', {
        'booking.source_booking_id': 'text',
        'driver.driver_name': 'text',
        'phone_number': 'text',
        'send_status': 'text',
        'created_at': 'date',
        'sent_at': 'date',
    })
    page_rows, page, limit, total = _paginate(enriched, request.args.get('page'), request.args.get('limit'))
    return jsonify({
        'success': True,
        'data': page_rows,
        'pagination': {'page': page, 'limit': limit, 'total': total},
    })


@rac_bp.route('/messages/<message_id>', methods=['GET'])
@require_rac
def get_message(message_id):
    message = rac_store.find_one('messages', 'message_log_id', message_id)
    if not message:
        return jsonify({'success': False, 'message': 'Message not found'}), 404
    booking = rac_store.find_one('bookings', 'booking_id', message.get('booking_id')) or {}
    driver = rac_store.find_one('drivers', 'driver_id', message.get('driver_id')) or {}
    payload = dict(message)
    payload['booking'] = {
        'source_booking_id': booking.get('source_booking_id'),
        'employee_name': booking.get('employee_name'),
    }
    payload['driver'] = {'driver_name': driver.get('driver_name')}
    return jsonify({'success': True, 'data': payload})
