"""Validate extracted booking rows.

A blank booking ID is filled from the place, date, time, and cab. Every other
missing field stays blank and is sent to review.
"""
import re
from datetime import datetime, timedelta, timezone

from parser import ID_RE, date_from_booking_id, extract_booking_id, parse_date, parse_time, salvage_payload

GARBAGE = re.compile(r'^[^A-Za-z0-9]+$')
IST = timezone(timedelta(hours=5, minutes=30))


def _clean(value):
    return re.sub(r'\s+', ' ', str(value or '').strip())


def upload_booking_date(row=None):
    """Booking date when OCR did not read one: the upload/ingest day in IST."""
    row = row or {}
    for key in ('upload_date', 'created_at', 'ingested_at'):
        raw = str(row.get(key) or '').strip()
        if not raw:
            continue
        parsed = parse_date(raw[:10])
        if parsed:
            return parsed
        try:
            stamp = datetime.fromisoformat(raw.replace('Z', '+00:00'))
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=timezone.utc)
            return stamp.astimezone(IST).strftime('%Y-%m-%d')
        except Exception:
            continue
    return datetime.now(IST).strftime('%Y-%m-%d')


def booking_id_from_fields(address, trip_date, trip_time, cab):
    """ID when the screenshot has none: place name + trip date + trip time + cab."""
    place = re.sub(r'[^A-Za-z0-9]+', '', str(address or ''))
    day = re.sub(r'\D', '', str(parse_date(trip_date) or ''))
    clock = re.sub(r'\D', '', str(parse_time(trip_time) or ''))
    vehicle = re.sub(r'[^A-Za-z0-9]+', '', str(cab or ''))
    if not place or len(day) != 8 or len(clock) != 4 or not vehicle:
        return ''
    suffix = f'-{day}-{clock}-{vehicle}'
    room = 50 - len(suffix)
    if room < 1:
        return ''
    return f'{place[:room]}{suffix}'


def normalize_cab(value):
    key = re.sub(r'[^a-z0-9]+', '', str(value or '').lower())
    if not key:
        return ''
    if key in ('suv', 'muv') or 'cryst' in key or 'innova' in key or 'ertiga' in key:
        return 'SUV'
    if key in ('sedan', 'dzire', 'swift', 'etios', 'ciaz', 'tiago'):
        return 'Sedan'
    if str(value).strip() in ('Sedan', 'SUV'):
        return str(value).strip()
    return _clean(value)


def validate_booking(row, staff_override=False):
    original_address = _clean((row or {}).get('planned_start_address'))
    row = salvage_payload(row)
    reasons = []
    printed_id = extract_booking_id(row.get('booking_id')) or _clean(row.get('booking_id'))
    trip_date = parse_date(row.get('trip_date')) or _clean(row.get('trip_date'))
    if not trip_date:
        # Booking IDs are BYYMMDD-XXXX, which is more reliable than stamping today's date.
        trip_date = date_from_booking_id(printed_id) or upload_booking_date(row)
    elif not parse_date(trip_date) and not re.match(r'^\d{4}-\d{2}-\d{2}$', trip_date):
        reasons.append('trip_date is not a valid date')
    trip_time = parse_time(row.get('trip_time')) or _clean(row.get('trip_time'))
    if trip_time and not parse_time(trip_time) and not re.match(r'^\d{2}:\d{2}$', trip_time):
        reasons.append('trip_time is not a valid time')
    if not trip_time:
        reasons.append('trip_time is missing')
    cab = normalize_cab(row.get('cab_type'))
    if cab and (GARBAGE.match(cab) or len(cab) < 2):
        reasons.append('cab_type looks corrupted')
    booking_type = _clean(row.get('booking_type'))
    if not booking_type:
        reasons.append('booking_type is missing')
    elif GARBAGE.match(booking_type) or len(booking_type) < 2:
        reasons.append('booking_type looks corrupted')
    address = _clean(row.get('planned_start_address'))
    if not address:
        reasons.append('planned_start_address is missing')
    generated = False
    booking_id = printed_id
    if not booking_id and original_address:
        booking_id = booking_id_from_fields(original_address, trip_date, trip_time, cab)
        generated = bool(booking_id)
    if not booking_id:
        reasons.append('booking_id is missing')
    elif not ID_RE.match(booking_id):
        reasons.append('booking_id does not look like a real ID')
    confidence = float(row.get('confidence') or 0)
    required_missing = any(
        'missing' in item or 'not a valid' in item or 'does not look' in item or 'corrupted' in item
        for item in reasons
    )
    if confidence and confidence < 0.5 and not staff_override and required_missing:
        reasons.append('extraction confidence is too low')
    ok = not reasons
    cleaned = dict(row)
    cleaned['booking_id'] = booking_id
    cleaned['booking_id_generated'] = generated
    cleaned['trip_date'] = parse_date(trip_date) or trip_date
    cleaned['trip_time'] = parse_time(trip_time) or trip_time
    cleaned['cab_type'] = cab
    cleaned['booking_type'] = booking_type
    cleaned['planned_start_address'] = address
    if staff_override:
        cleaned['confidence'] = 1
    return ok, reasons, cleaned
