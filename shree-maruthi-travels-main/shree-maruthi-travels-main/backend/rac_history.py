"""Load May–August 2026 RAC duty history into dispatch bookings."""
import json
import os

HISTORY_BATCH = 'hist-may-aug-2026'
HISTORY_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'rac_history.json')


def load_history_bookings():
    if not os.path.isfile(HISTORY_JSON):
        return []
    with open(HISTORY_JSON, encoding='utf-8') as handle:
        raw = json.load(handle)
    bookings = []
    for index, row in enumerate(raw):
        trip_date = row.get('trip_date')
        if not trip_date:
            continue
        bookings.append({
            'booking_id': row.get('booking_id') or f'hist-{index:05d}',
            'source_booking_id': row.get('source_booking_id'),
            'sl_no': row.get('sl_no') or '',
            'trip_date': trip_date,
            'source_name': row.get('source_name') or '',
            'source_vehicle_no': row.get('source_vehicle_no') or '',
            'source_mobile': row.get('source_mobile') or '',
            'planned_start': row.get('planned_start') or '',
            'route_text': row.get('route_text') or '',
            'pickup_time': str(row.get('pickup_time') or ''),
            'end_time': str(row.get('end_time') or ''),
            'total_hours_text': str(row.get('total_hours_text') or ''),
            'cab_type': row.get('cab_type') or '',
            'employee_name': row.get('employee_name') or row.get('source_name') or 'Unknown',
            'start_km': row.get('start_km') or 0,
            'end_km': row.get('end_km') or 0,
            'total_km': row.get('total_km') or 0,
            'duty_type': row.get('duty_type') or '',
            'toll': row.get('toll') or 0,
            'parking': row.get('parking') or 0,
            'amount': row.get('amount') or 0,
            'remarks': row.get('remarks') or '',
            'status': 'Completed',
            'upload_batch_id': HISTORY_BATCH,
            'assigned_driver_id': '',
            'assigned_at': '',
            'driver_payment_status': 'Paid',
            'driver_paid_at': '',
            'driver_payment_notes': 'Imported historical duty',
            'history_month': trip_date[:7],
            'history_source': row.get('history_source') or '',
        })
    return bookings
