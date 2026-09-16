"""Push imported RAC history + drivers into Zoho Sheet (new rows only)."""
import json
import os
import sys
import time

from dotenv import load_dotenv

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
load_dotenv(os.path.join(ROOT, '..', '.env'))
load_dotenv(os.path.join(ROOT, '.env'))
sys.path.insert(0, ROOT)

import rac_history
import rac_store
import zoho_sheet


def keys_from(rows, field):
    return {str(row.get(field) or '').strip().lower() for row in rows if str(row.get(field) or '').strip()}


def push(kind, rows, id_field):
    existing = zoho_sheet.fetch_records(rac_store.SHEETS[kind]) or []
    seen = keys_from(existing, id_field)
    pending = []
    for row in rows:
        key = str(row.get(id_field) or '').strip().lower()
        if not key or key in seen:
            continue
        item = dict(row)
        item['created_at'] = item.get('created_at') or rac_store._now()
        item['updated_at'] = item.get('updated_at') or rac_store._now()
        pending.append(rac_store._stringify(item))
        seen.add(key)
    print(kind, 'existing', len(existing), 'new', len(pending))
    chunk = 60
    ok = 0
    for start in range(0, len(pending), chunk):
        part = pending[start:start + chunk]
        if zoho_sheet.add_records(rac_store.SHEETS[kind], part):
            ok += len(part)
        else:
            print('FAILED chunk', start)
        time.sleep(0.5)
    print(kind, 'pushed', ok)


def main():
    if not zoho_sheet.zoho_configured():
        raise SystemExit('Zoho is not configured')
    drivers = rac_history.load_history_drivers()
    bookings = rac_history.load_history_bookings()
    push('drivers', drivers, 'driver_name')
    push('bookings', bookings, 'source_booking_id')


if __name__ == '__main__':
    main()
