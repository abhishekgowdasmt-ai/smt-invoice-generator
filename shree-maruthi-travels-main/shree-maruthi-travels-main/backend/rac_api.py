"""RAC dispatch API backed by Zoho Sheets (JSON fallback)."""
import io
import os
import re
from datetime import datetime
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
    if not header.startswith('Bearer '):
        return None
    token = header.split(' ', 1)[1].strip()
    try:
        return TOKEN.loads(token, max_age=60 * 60 * 24 * 7)
    except (BadSignature, SignatureExpired):
        return None


def require_rac(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        user = _auth_user()
        if not user:
            return jsonify({'success': False, 'message': 'Unauthorized - No token provided'}), 401
        request.rac_user = user
        return fn(*args, **kwargs)
    return wrapped


def _norm_header(value):
    return re.sub(r'\s+', ' ', str(value or '').strip().upper())


def _parse_excel_date(value):
    if value is None or value == '':
        return None
    if hasattr(value, 'strftime'):
        return value.strftime('%Y-%m-%d')
    text = str(value).strip()
    if '/' in text:
        parts = text.split('/')
        if len(parts) == 3:
            try:
                day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
                if year < 100:
                    year += 2000 if year < 50 else 1900
                return datetime(year, month, day).strftime('%Y-%m-%d')
            except ValueError:
                pass
    if isinstance(value, (int, float)):
        try:
            from datetime import timedelta
            base = datetime(1899, 12, 30)
            return (base + timedelta(days=float(value))).strftime('%Y-%m-%d')
        except (ValueError, OverflowError):
            return None
    try:
        return datetime.strptime(text[:10], '%Y-%m-%d').strftime('%Y-%m-%d')
    except ValueError:
        return None


def _parse_time(value):
    if not value:
        return None
    match = re.search(r'(\d{1,2})[:.](\d{2})', str(value))
    if not match:
        return None
    return f'{int(match.group(1)):02d}:{match.group(2)}'


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


def _whatsapp_body(booking):
    pickup = (booking.get('pickup_time') or 'N/A')
    end = (booking.get('end_time') or 'N/A')
    route = booking.get('route_text') or 'N/A'
    if len(str(route)) > 100:
        route = str(route)[:100] + '...'
    return (
        'New Ride Assigned\n\n'
        f"Booking ID: {booking.get('source_booking_id')}\n"
        f"Date: {booking.get('trip_date')}\n"
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
    return jsonify({'success': True, 'token': TOKEN.dumps(RAC_USER), 'user': RAC_USER})


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
    return jsonify({
        'success': True,
        'data': {
            'total_uploaded_today': uploaded_today,
            'unassigned_rides': sum(1 for row in bookings if row.get('status') == 'Unassigned'),
            'assigned_rides': sum(1 for row in bookings if row.get('status') == 'Assigned'),
            'completed_rides': sum(1 for row in bookings if row.get('status') == 'Completed'),
            'cancelled_rides': sum(1 for row in bookings if row.get('status') == 'Cancelled'),
            'unpaid_driver_payments': sum(
                1 for row in bookings
                if row.get('status') in ('Assigned', 'Completed')
                and _driver_payment_status(row.get('driver_payment_status')) != 'Paid'
            ),
            'message_sent_count': sum(1 for row in messages if row.get('send_status') == 'sent'),
            'message_failed_count': sum(1 for row in messages if row.get('send_status') in ('failed', 'skipped')),
            'upload_timestamp': datetime.utcnow().isoformat() + 'Z',
        }
    })


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
    rows.sort(key=lambda row: str(row.get('driver_name') or '').lower())
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
    if not name or not phone:
        return jsonify({'success': False, 'message': 'Driver name and WhatsApp number required'}), 400
    if rac_store.find_one('drivers', 'whatsapp_number', phone):
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
    status = request.args.get('status') or ''
    search = (request.args.get('search') or '').strip().lower()
    payment = request.args.get('payment') or ''
    assigned = request.args.get('assigned_driver_id') or ''
    rows = rac_store.all_rows('bookings')
    if date:
        rows = [row for row in rows if str(row.get('trip_date') or '') == date]
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
    sort_by = request.args.get('sort_by') or 'created_at'
    reverse = (request.args.get('sort_order') or 'DESC').upper() != 'ASC'
    rows.sort(key=lambda row: str(row.get(sort_by) or ''), reverse=reverse)
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
        },
        'pagination': {'page': page, 'limit': limit, 'total': total},
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
    payload = dict(booking)
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
    rac_store.update_one('bookings', 'booking_id', booking_id, {
        'driver_payment_status': status,
        'driver_paid_at': datetime.utcnow().isoformat() + 'Z' if status == 'Paid' else '',
        'driver_payment_notes': notes,
        'driver_paid_amount': amount,
    })
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
    try:
        import pandas as pd
        frame = pd.read_excel(io.BytesIO(upload.read()))
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
        mapped['trip_date'] = _parse_excel_date(mapped.get('trip_date'))
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
    rows.sort(key=lambda row: str(row.get('sent_at') or row.get('created_at') or ''), reverse=True)
    enriched = []
    for row in rows:
        item = dict(row)
        booking = rac_store.find_one('bookings', 'booking_id', row.get('booking_id')) or {}
        driver = rac_store.find_one('drivers', 'driver_id', row.get('driver_id')) or {}
        item['booking'] = {'source_booking_id': booking.get('source_booking_id')}
        item['driver'] = {'driver_name': driver.get('driver_name')}
        enriched.append(item)
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
