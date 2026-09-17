"""Validate extracted booking rows. Never invent missing values."""
import re

from parser import ID_RE, parse_date, parse_time

GARBAGE = re.compile(r'^[^A-Za-z0-9]+$')


def _clean(value):
    return re.sub(r'\s+', ' ', str(value or '').strip())


def validate_booking(row):
    reasons = []
    booking_id = _clean(row.get('booking_id'))
    if not booking_id:
        reasons.append('booking_id is missing')
    elif not ID_RE.match(booking_id):
        reasons.append('booking_id does not look like a real ID')
    trip_date = parse_date(row.get('trip_date')) or _clean(row.get('trip_date'))
    if not trip_date:
        reasons.append('trip_date is missing')
    elif not parse_date(trip_date) and not re.match(r'^\d{4}-\d{2}-\d{2}$', trip_date):
        reasons.append('trip_date is not a valid date')
    trip_time = parse_time(row.get('trip_time')) or _clean(row.get('trip_time'))
    if trip_time and not parse_time(trip_time) and not re.match(r'^\d{2}:\d{2}$', trip_time):
        reasons.append('trip_time is not a valid time')
    if not trip_time:
        reasons.append('trip_time is missing')
    cab = _clean(row.get('cab_type'))
    if not cab:
        reasons.append('cab_type is missing')
    elif GARBAGE.match(cab) or len(cab) < 2:
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
    if confidence and confidence < 0.5:
        reasons.append('extraction confidence is too low')
    ok = not reasons
    cleaned = dict(row)
    cleaned['booking_id'] = booking_id
    cleaned['trip_date'] = parse_date(trip_date) or trip_date
    cleaned['trip_time'] = parse_time(trip_time) or trip_time
    cleaned['cab_type'] = cab
    cleaned['booking_type'] = booking_type
    cleaned['planned_start_address'] = address
    return ok, reasons, cleaned
