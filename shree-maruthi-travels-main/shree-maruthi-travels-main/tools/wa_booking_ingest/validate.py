"""Validate extracted booking rows. Never invent missing values."""
import re
from datetime import datetime, timedelta, timezone

from parser import ID_RE, extract_booking_id, parse_date, parse_time, salvage_payload

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


def normalize_cab(value):
    key = re.sub(r'[^a-z0-9]+', '', str(value or '').lower())
    if not key:
        return ''
    if key in ('suv', 'muv') or 'cryst' in key or 'innova' in key:
        return 'SUV'
    if key in ('sedan', 'dzire', 'swift', 'etios', 'ciaz', 'tiago'):
        return 'Sedan'
    if str(value).strip() in ('Sedan', 'SUV'):
        return str(value).strip()
    return _clean(value)


def validate_booking(row, staff_override=False):
    row = salvage_payload(row)
    reasons = []
    booking_id = extract_booking_id(row.get('booking_id')) or _clean(row.get('booking_id'))
    if not booking_id:
        reasons.append('booking_id is missing')
    elif not ID_RE.match(booking_id):
        reasons.append('booking_id does not look like a real ID')
    trip_date = parse_date(row.get('trip_date')) or _clean(row.get('trip_date'))
    if not trip_date:
        trip_date = upload_booking_date(row)
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
    cleaned['trip_date'] = parse_date(trip_date) or trip_date
    cleaned['trip_time'] = parse_time(trip_time) or trip_time
    cleaned['cab_type'] = cab
    cleaned['booking_type'] = booking_type
    cleaned['planned_start_address'] = address
    if staff_override:
        cleaned['confidence'] = 1
    return ok, reasons, cleaned
