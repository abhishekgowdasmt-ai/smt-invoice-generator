"""In-memory RAC store with JSON file + optional Zoho Sheet persistence."""
import json
import os
import threading
import time
import uuid
from datetime import datetime

import zoho_sheet

STORE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rac_data.json')
_lock = threading.Lock()
_data = None

SHEETS = {
    'drivers': 'RAC_Drivers',
    'bookings': 'RAC_Bookings',
    'assignments': 'RAC_Assignments',
    'uploads': 'RAC_Uploads',
    'messages': 'RAC_Messages',
}

SAMPLE_DRIVERS = [
    {
        'driver_id': 'drv-sample-1',
        'driver_name': 'RAJA KUMAR',
        'whatsapp_number': '+919876543210',
        'alternate_number': '',
        'vehicle_number': 'KA-01-AB-1234',
        'vehicle_type': 'SEDAN',
        'home_area': 'BANGALORE',
        'active_status': True,
        'total_assignments': 0,
        'notes': '',
    },
    {
        'driver_id': 'drv-sample-2',
        'driver_name': 'SHARMA JI',
        'whatsapp_number': '+919876543211',
        'alternate_number': '',
        'vehicle_number': 'KA-01-CD-3456',
        'vehicle_type': 'SEDAN',
        'home_area': 'BANGALORE',
        'active_status': True,
        'total_assignments': 0,
        'notes': '',
    },
    {
        'driver_id': 'drv-sample-3',
        'driver_name': 'GUPTA',
        'whatsapp_number': '+919876543212',
        'alternate_number': '',
        'vehicle_number': 'KA-01-EF-5678',
        'vehicle_type': 'SUV',
        'home_area': 'WHITEFIELD',
        'active_status': True,
        'total_assignments': 0,
        'notes': '',
    },
]


def _now():
    return datetime.utcnow().isoformat(timespec='seconds') + 'Z'


def _empty():
    return {key: [] for key in SHEETS}


def _stringify(row):
    out = {}
    for key, value in row.items():
        if value is None:
            out[key] = ''
        elif isinstance(value, bool):
            out[key] = 'true' if value else 'false'
        elif isinstance(value, (dict, list)):
            out[key] = json.dumps(value)
        else:
            out[key] = str(value)
    return out


def _parse_row(row):
    parsed = dict(row or {})
    parsed.pop('row_index', None)
    status = parsed.get('active_status')
    if isinstance(status, str):
        parsed['active_status'] = status.strip().lower() in ('true', '1', 'yes')
    for key in ('sl_no', 'total_assignments', 'success_rows', 'failed_rows', 'total_rows', 'retry_count'):
        if parsed.get(key) in ('', None):
            continue
        try:
            parsed[key] = int(float(parsed[key]))
        except (TypeError, ValueError):
            pass
    for key in ('start_km', 'end_km', 'total_km', 'driver_hours', 'driver_km', 'toll', 'parking', 'amount', 'file_size'):
        if parsed.get(key) in ('', None):
            continue
        try:
            parsed[key] = float(parsed[key])
        except (TypeError, ValueError):
            pass
    summary = parsed.get('error_summary')
    if isinstance(summary, str) and summary.startswith('['):
        try:
            parsed['error_summary'] = json.loads(summary)
        except json.JSONDecodeError:
            pass
    return parsed


def _save_json(data):
    try:
        with open(STORE_PATH, 'w', encoding='utf-8') as handle:
            json.dump(data, handle, indent=2)
    except OSError as exc:
        print(f'[RAC] Could not write {STORE_PATH}: {exc}')


def _load_json():
    if not os.path.isfile(STORE_PATH):
        return None
    try:
        with open(STORE_PATH, encoding='utf-8') as handle:
            loaded = json.load(handle)
        data = _empty()
        for key in data:
            data[key] = loaded.get(key) or []
        return data
    except (OSError, json.JSONDecodeError) as exc:
        print(f'[RAC] Could not read {STORE_PATH}: {exc}')
        return None


def _load_zoho():
    if not zoho_sheet.zoho_configured():
        return None
    data = _empty()
    bookings_ok = False
    any_ok = False
    for key, worksheet in SHEETS.items():
        try:
            rows = zoho_sheet.fetch_records(worksheet)
        except Exception as exc:
            print(f'[RAC] Zoho fetch {key} failed: {exc}')
            rows = None
        if rows is None:
            continue
        any_ok = True
        data[key] = [_parse_row(row) for row in rows if row]
        if key == 'bookings':
            bookings_ok = True
    if not any_ok:
        return None
    if zoho_sheet.zoho_configured() and not bookings_ok:
        print('[RAC] Zoho bookings sheet was not readable; using local history instead')
        return None
    return data


def _hydrate_zoho():
    try:
        zoho = _load_zoho()
    except Exception as exc:
        print(f'[RAC] Zoho hydrate failed: {exc}')
        return
    if not zoho:
        return
    with _lock:
        if _data is None:
            return
        by_id = {str(row.get('source_booking_id')): row for row in _data.get('bookings') or []}
        for row in zoho.get('bookings') or []:
            by_id[str(row.get('source_booking_id'))] = row
        _data['bookings'] = list(by_id.values())
        for kind in ('drivers', 'assignments', 'uploads', 'messages'):
            if zoho.get(kind):
                _data[kind] = zoho[kind]
        _attach_drivers(_data)
        _attach_history(_data, push=False)
        _save_json(_data)


def _attach_history(data, push=True):
    import rac_history
    pending = []
    existing = {str(row.get('source_booking_id')) for row in data['bookings']}
    for row in rac_history.load_history_bookings():
        if row.get('source_booking_id') in existing:
            continue
        item = dict(row)
        item['created_at'] = item.get('created_at') or _now()
        item['updated_at'] = item.get('updated_at') or _now()
        data['bookings'].append(item)
        existing.add(str(item.get('source_booking_id')))
        if push:
            pending.append(item)
    if pending and not any(str(row.get('batch_id')) == rac_history.HISTORY_BATCH for row in data['uploads']):
        data['uploads'].append({
            'batch_id': rac_history.HISTORY_BATCH,
            'file_name': 'RAC historical duty workbooks (Nov 2025–Sep 2026)',
            'file_size': 0,
            'uploaded_by': 'history-import',
            'uploaded_at': _now(),
            'total_rows': len(pending),
            'success_rows': len(pending),
            'failed_rows': 0,
            'import_status': 'completed',
            'error_summary': [],
            'created_at': _now(),
            'updated_at': _now(),
        })
    return pending


def _attach_drivers(data):
    import rac_history
    existing = {str(row.get('driver_name') or '').strip().lower() for row in data['drivers']}
    added = []
    for row in rac_history.load_history_drivers():
        name = str(row.get('driver_name') or '').strip()
        if not name or name.lower() in existing:
            continue
        item = dict(row)
        item['created_at'] = item.get('created_at') or _now()
        item['updated_at'] = item.get('updated_at') or _now()
        data['drivers'].append(item)
        existing.add(name.lower())
        added.append(item)
    return added


def _seed_if_needed(data):
    _attach_drivers(data)
    if not data['drivers']:
        stamped = []
        for driver in SAMPLE_DRIVERS:
            item = dict(driver)
            item['created_at'] = item.get('created_at') or _now()
            item['updated_at'] = item.get('updated_at') or _now()
            stamped.append(item)
        data['drivers'] = stamped
    _attach_history(data, push=False)
    return data, []


def load():
    global _data
    with _lock:
        if _data is not None:
            return _data
        data = _load_json() or _empty()
        data, _ = _seed_if_needed(data)
        _data = data
        _save_json(_data)
    threading.Thread(target=_hydrate_zoho, daemon=True).start()
    return _data


def reset():
    global _data
    with _lock:
        _data = None


def all_rows(kind):
    return list(load().get(kind) or [])


def find_one(kind, field, value):
    if value is None:
        return None
    wanted = str(value)
    for row in all_rows(kind):
        if str(row.get(field, '')) == wanted:
            return row
    return None


def insert(kind, row):
    item = dict(row)
    item['created_at'] = item.get('created_at') or _now()
    item['updated_at'] = _now()
    load()
    with _lock:
        _data[kind].append(item)
        _save_json(_data)
    if zoho_sheet.zoho_configured():
        zoho_sheet.add_records(SHEETS[kind], [_stringify(item)])
    return item


def insert_many(kind, rows):
    stored = []
    for row in rows:
        item = dict(row)
        item['created_at'] = item.get('created_at') or _now()
        item['updated_at'] = _now()
        stored.append(item)
    if not stored:
        return []
    load()
    with _lock:
        _data[kind].extend(stored)
        _save_json(_data)
    if zoho_sheet.zoho_configured():
        chunk = 80
        for start in range(0, len(stored), chunk):
            zoho_sheet.add_records(SHEETS[kind], [_stringify(row) for row in stored[start:start + chunk]])
            time.sleep(0.4)
    return stored


def update_one(kind, id_field, id_value, changes):
    updated = None
    load()
    with _lock:
        for row in _data[kind]:
            if str(row.get(id_field, '')) == str(id_value):
                row.update(changes)
                row['updated_at'] = _now()
                updated = dict(row)
                break
        if updated:
            _save_json(_data)
    if updated and zoho_sheet.zoho_configured():
        zoho_sheet.update_record(SHEETS[kind], id_field, id_value, _stringify(updated))
    return updated


def new_id(prefix):
    return f'{prefix}-{uuid.uuid4().hex[:12]}'
