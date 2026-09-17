"""Normalize OCR/table text into booking rows. No invented fields."""
import re

HEADER_ALIASES = {
    'booking_id': ('booking_id', 'bookingid', 'bkgid', 'bkg_id', 'id'),
    'booking_type': ('booking_type', 'bookingtype', 'duty_type', 'dutytype', 'duty', 'type'),
    'cab_type': ('cab_type', 'cabtype', 'cab', 'vehicle', 'vehicle_type'),
    'trip_date': ('trip_date', 'tripdate', 'date', 'duty_date', 'booking_date'),
    'trip_time': ('trip_time', 'triptime', 'time', 'pickup_time', 'pickuptime', 'start_time'),
    'planned_start_address': (
        'planned_start_address', 'plannedstartaddress', 'planned_start', 'pland_start',
        'pickup', 'address', 'start_address', 'location',
    ),
}

ID_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._/-]{3,49}$')
MONTHS = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'sept': 9, 'oct': 10, 'nov': 11, 'dec': 12,
}


def _norm_key(value):
    return re.sub(r'[^a-z0-9]+', '', str(value or '').lower())


def map_header(value):
    key = _norm_key(value)
    for field, aliases in HEADER_ALIASES.items():
        if key in aliases:
            return field
    return None


def parse_date(value):
    text = re.sub(r'\s+', ' ', str(value or '').strip())
    if not text:
        return None
    text = text.replace('.', '-')
    match = re.match(r'^(\d{4})-(\d{1,2})-(\d{1,2})$', text)
    if match:
        year, month, day = (int(part) for part in match.groups())
        if 1 <= month <= 12 and 1 <= day <= 31:
            return f'{year:04d}-{month:02d}-{day:02d}'
    match = re.match(r'^(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})$', text)
    if match:
        first, second, year = (int(part) for part in match.groups())
        if year < 100:
            year += 2000
        day, month = first, second
        if month > 12 and first <= 12:
            day, month = second, first
        if 1 <= month <= 12 and 1 <= day <= 31:
            return f'{year:04d}-{month:02d}-{day:02d}'
    match = re.match(r'^(\d{1,2})\s+([A-Za-z]{3,9})\s+(\d{2,4})$', text)
    if match:
        day = int(match.group(1))
        month = MONTHS.get(match.group(2)[:3].lower())
        year = int(match.group(3))
        if year < 100:
            year += 2000
        if month and 1 <= day <= 31:
            return f'{year:04d}-{month:02d}-{day:02d}'
    return None


def parse_time(value):
    text = str(value or '').strip().upper()
    if not text:
        return None
    match = re.search(r'(\d{1,2})[:.](\d{2})\s*(AM|PM)?', text)
    if not match:
        match = re.search(r'^(\d{3,4})$', re.sub(r'\D', '', text))
        if not match:
            return None
        digits = match.group(1).zfill(4)
        hour, minute = int(digits[:2]), int(digits[2:])
        suffix = 'PM' if 'PM' in text else ('AM' if 'AM' in text else '')
    else:
        hour, minute = int(match.group(1)), int(match.group(2))
        suffix = match.group(3) or ''
    if suffix == 'PM' and hour < 12:
        hour += 12
    if suffix == 'AM' and hour == 12:
        hour = 0
    if hour > 23 or minute > 59:
        return None
    return f'{hour:02d}:{minute:02d}'


def split_row(line):
    text = str(line or '').strip()
    if not text:
        return []
    if '\t' in text:
        return [part.strip() for part in text.split('\t')]
    return [part.strip() for part in re.split(r'\s{2,}', text) if part.strip()]


def _looks_header(cells):
    mapped = [map_header(cell) for cell in cells]
    return sum(1 for item in mapped if item) >= 3


def parse_table_text(text, source_message_id='', source_image=''):
    lines = [line.strip() for line in str(text or '').splitlines() if line.strip()]
    if not lines:
        return []
    headers = None
    start = 0
    first_cells = split_row(lines[0])
    if _looks_header(first_cells):
        headers = [map_header(cell) for cell in first_cells]
        start = 1
    else:
        headers = ['booking_id', 'booking_type', 'cab_type', 'trip_date', 'trip_time', 'planned_start_address']
    rows = []
    for line in lines[start:]:
        cells = split_row(line)
        if not cells or _looks_header(cells):
            continue
        item = {
            'booking_id': '',
            'booking_type': '',
            'cab_type': '',
            'trip_date': '',
            'trip_time': '',
            'planned_start_address': '',
            'source_message_id': source_message_id,
            'source_image': source_image,
            'confidence': 0.0,
            'raw_line': line,
        }
        if headers and len(headers) >= 3:
            for index, cell in enumerate(cells):
                field = headers[index] if index < len(headers) else None
                if field:
                    item[field] = cell
            if not item['planned_start_address'] and len(cells) > len([h for h in headers if h]):
                item['planned_start_address'] = ' '.join(cells[len(headers):]).strip()
        else:
            continue
        item['trip_date'] = parse_date(item.get('trip_date')) or ''
        item['trip_time'] = parse_time(item.get('trip_time')) or ''
        item['booking_id'] = str(item.get('booking_id') or '').strip()
        filled = sum(1 for key in ('booking_id', 'booking_type', 'cab_type', 'trip_date', 'trip_time', 'planned_start_address') if item.get(key))
        item['confidence'] = round(filled / 6.0, 2)
        rows.append(item)
    return rows
