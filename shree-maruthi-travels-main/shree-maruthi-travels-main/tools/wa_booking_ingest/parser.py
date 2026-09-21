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
BOOKING_ID_IN_TEXT = re.compile(r'\bB\d{6}-[A-Za-z0-9]{2,12}\b', re.I)
CAB_TYPES = (
    'SEDAN', 'SUV', 'MUV', 'CRYSTA', 'INNOVA', 'ERTIGA', 'DZIRE', 'SWIFT',
    'TIAGO', 'ETIOS', 'TOYOTA', 'HONDA', 'HYUNDAI', 'TEMPO', 'TRAVELLER',
)
DUTY_WORDS = (
    'DISPOSAL', 'DROP', 'PICKUP', 'PICK UP', 'OUTSTATION', 'LOCAL',
    '12HRS', '8HRS', '4HRS', '12HRS-120KM', '8HRS-80KM',
)
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


def extract_booking_id(value):
    text = str(value or '')
    match = BOOKING_ID_IN_TEXT.search(text)
    if match:
        return match.group(0).upper()
    cleaned = text.strip()
    if re.match(r'^[A-Za-z]\d{6}-[A-Za-z0-9]{2,12}$', cleaned):
        return cleaned.upper()
    return ''


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
    match = re.search(r'(\d{1,2})[/\s-]+([A-Za-z]{3,9})[/\s-]+(\d{2,4})', text)
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
    match = re.search(r'(\d{1,2})[:.](\d{2})(?::\d{2})?\s*(AM|PM)?', text)
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
        return [part.strip() for part in text.split('\t') if part.strip()]
    if '|' in text:
        return [part.strip() for part in text.split('|') if part.strip()]
    return [part.strip() for part in re.split(r'\s{2,}', text) if part.strip()]


def _looks_header(cells):
    mapped = [map_header(cell) for cell in cells]
    return sum(1 for item in mapped if item) >= 3


def _empty_item(source_message_id='', source_image='', raw_line=''):
    return {
        'booking_id': '',
        'booking_type': '',
        'cab_type': '',
        'trip_date': '',
        'trip_time': '',
        'planned_start_address': '',
        'source_message_id': source_message_id,
        'source_image': source_image,
        'confidence': 0.0,
        'raw_line': raw_line,
    }


def map_cells_by_content(cells, item=None):
    """Pull ID/date/time/duty/address out of jammed OCR cells. Does not invent cab type."""
    item = item or _empty_item()
    leftovers = []
    for raw_cell in cells:
        cell = re.sub(r'\s+', ' ', str(raw_cell or '').strip())
        if not cell:
            continue
        if not item['trip_date']:
            dated = parse_date(cell)
            if dated and len(cell) <= 24 and not extract_booking_id(cell):
                item['trip_date'] = dated
                continue
        bid = extract_booking_id(cell)
        time_val = parse_time(cell)
        if bid and (not extract_booking_id(item.get('booking_id'))):
            item['booking_id'] = bid
            remainder = re.sub(re.escape(bid), ' ', cell, count=1, flags=re.I)
            remainder = re.sub(r'\b\d{1,2}[:.]\d{2}(?::\d{2})?\b', ' ', remainder)
            if time_val and not item['trip_time']:
                item['trip_time'] = time_val
            leftovers.append(remainder)
            continue
        if time_val and re.match(r'^\d{1,2}[:.]\d{2}', cell) and len(cell) <= 14:
            item['trip_time'] = item['trip_time'] or time_val
            continue
        leftovers.append(cell)

    cleaned_parts = []
    for part in leftovers:
        text = re.sub(r'\s+', ' ', str(part or '')).strip(' -|/,')
        if not text:
            continue
        upper = text.upper()
        for cab in CAB_TYPES:
            if re.search(rf'\b{re.escape(cab)}\b', upper) and not item['cab_type']:
                item['cab_type'] = cab
                text = re.sub(rf'\b{re.escape(cab)}\b', ' ', text, flags=re.I)
                text = re.sub(r'\s+', ' ', text).strip(' -|/,')
                break
        if text:
            cleaned_parts.append(text)

    if len(cleaned_parts) >= 2:
        if not item['booking_type']:
            item['booking_type'] = cleaned_parts[0]
        if not item['planned_start_address']:
            item['planned_start_address'] = cleaned_parts[-1]
    elif len(cleaned_parts) == 1:
        blob = cleaned_parts[0]
        upper = blob.upper()
        if any(word in upper for word in DUTY_WORDS) and not item['booking_type']:
            item['booking_type'] = blob
        elif not item['planned_start_address']:
            item['planned_start_address'] = blob
    return item


def salvage_payload(payload):
    """Split a jammed OCR blob into fields. Never overwrites a valid ID/date."""
    payload = dict(payload or {})
    blob = ' | '.join(
        str(payload.get(key) or '')
        for key in ('booking_id', 'raw_line', 'text', 'booking_type', 'planned_start_address')
        if payload.get(key)
    )
    extracted = map_cells_by_content(split_row(blob) or [blob], _empty_item(raw_line=blob))
    if not extracted.get('booking_id') and blob:
        extracted = map_cells_by_content([blob], extracted)
    for key in ('booking_id', 'booking_type', 'cab_type', 'trip_date', 'trip_time', 'planned_start_address'):
        current = str(payload.get(key) or '').strip()
        if key == 'booking_id' and current and not extract_booking_id(current) and extracted.get('booking_id'):
            payload[key] = extracted['booking_id']
            continue
        if not current and extracted.get(key):
            payload[key] = extracted[key]
    if payload.get('trip_date'):
        payload['trip_date'] = parse_date(payload['trip_date']) or payload['trip_date']
    if payload.get('trip_time'):
        payload['trip_time'] = parse_time(payload['trip_time']) or payload['trip_time']
    extracted_id = extract_booking_id(payload.get('booking_id'))
    if extracted_id:
        payload['booking_id'] = extracted_id
    return payload


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
        item = _empty_item(source_message_id, source_image, line)
        if headers and len(headers) >= 3:
            for index, cell in enumerate(cells):
                field = headers[index] if index < len(headers) else None
                if field:
                    item[field] = cell
            if not item['planned_start_address'] and len(cells) > len([h for h in headers if h]):
                item['planned_start_address'] = ' '.join(cells[len(headers):]).strip()
        positional_id = extract_booking_id(item.get('booking_id'))
        if not positional_id or not parse_date(item.get('trip_date') or ''):
            item = map_cells_by_content(cells, item)
            if not item.get('booking_id'):
                item = map_cells_by_content([line], item)
        else:
            item['booking_id'] = positional_id
        item['trip_date'] = parse_date(item.get('trip_date')) or ''
        item['trip_time'] = parse_time(item.get('trip_time')) or ''
        item['booking_id'] = extract_booking_id(item.get('booking_id')) or (
            str(item.get('booking_id') or '').strip() if not parse_date(item.get('booking_id') or '') else ''
        )
        filled = sum(
            1 for key in (
                'booking_id', 'booking_type', 'cab_type', 'trip_date', 'trip_time', 'planned_start_address',
            ) if item.get(key)
        )
        item['confidence'] = round(filled / 6.0, 2)
        rows.append(item)
    return rows
