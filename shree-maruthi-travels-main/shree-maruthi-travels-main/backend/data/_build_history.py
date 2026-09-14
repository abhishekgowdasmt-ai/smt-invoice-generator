import json
import os
import re
from datetime import datetime
from collections import Counter

import pandas as pd

src = r'C:\Users\Abhishek B G\Downloads\Invoice generation samples\RAC_Automation-main\RAC_Automation-main\MONTH OF MAY TO AUGUST FULL DUTY XL RAC 2026.xlsx'
out = r'C:\Users\Abhishek B G\Downloads\Invoice generation samples\shree-maruthi-travels-main\shree-maruthi-travels-main\backend\data\rac_history.json'

MAP = {
    'SL NO': 'sl_no', 'BOOKING ID': 'source_booking_id', 'DATE': 'trip_date', 'NAME': 'source_name',
    'CAB REG NO': 'source_vehicle_no', 'MOBIL NO': 'source_mobile', 'PLAND START': 'planned_start',
    'END LOACTION': 'route_text', 'END LOCATION': 'route_text', 'PICKUP TIME': 'pickup_time',
    'END TIME': 'end_time', 'TOTAL HRS SMT': 'total_hours_text', 'CAB TYPE': 'cab_type',
    'EMP NAME': 'employee_name', 'START KM': 'start_km', 'END KM': 'end_km', 'SMT TOTAL KM': 'total_km',
    'DUTY TYPE': 'duty_type', 'TOLL': 'toll', 'PARKING': 'parking', 'AMOUNT': 'amount',
}


def norm(col):
    return re.sub(r'\s+', ' ', str(col or '').strip().upper())


def parse_date(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if hasattr(value, 'strftime'):
        year = value.year + 100 if value.year < 2000 else value.year
        return f'{year:04d}-{value.month:02d}-{value.day:02d}'
    text = str(value).strip().replace(' 00:00:00', '')
    if text.lower() in ('', 'nan', 'nat', 'none'):
        return None
    for fmt in ('%d-%b-%y', '%d-%b-%Y', '%Y-%m-%d', '%d/%m/%Y', '%d/%m/%y'):
        try:
            parsed = datetime.strptime(text[:20], fmt)
            year = parsed.year + 100 if parsed.year < 2000 else parsed.year
            return f'{year:04d}-{parsed.month:02d}-{parsed.day:02d}'
        except ValueError:
            continue
    return None


def num(value, default=0):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    matches = re.findall(r'\d+(?:\.\d+)?', str(value))
    return float(matches[-1]) if matches else default


def clean_text(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ''
    return str(value).replace('\u0000', '').strip()


def clean_cab(value):
    text = clean_text(value)
    if not text or re.match(r'^\d', text):
        return ''
    return text


rows = []
seen = set()
xl = pd.ExcelFile(src)
for sheet in xl.sheet_names:
    df = pd.read_excel(src, sheet_name=sheet)
    for i, raw in df.iterrows():
        mapped = {}
        for col, val in raw.items():
            if str(col).startswith('Unnamed') or pd.isna(val):
                continue
            field = MAP.get(norm(col))
            if field:
                mapped[field] = val
        date = parse_date(mapped.get('trip_date'))
        name = clean_text(mapped.get('source_name'))
        emp = clean_text(mapped.get('employee_name'))
        if not date:
            continue
        bid = clean_text(mapped.get('source_booking_id'))
        if bid.lower() in ('nan', 'none'):
            bid = ''
        if not bid:
            bid = f"HIST-{date}-{mapped.get('sl_no') or i}"
        if bid in seen:
            bid = f'{bid}-{i}'
        seen.add(bid)
        rows.append({
            'booking_id': f'hist-{len(rows):05d}',
            'source_booking_id': bid,
            'sl_no': mapped.get('sl_no') if mapped.get('sl_no') == mapped.get('sl_no') else '',
            'trip_date': date,
            'source_name': name,
            'source_vehicle_no': clean_text(mapped.get('source_vehicle_no')),
            'source_mobile': clean_text(mapped.get('source_mobile')),
            'planned_start': clean_text(mapped.get('planned_start')),
            'route_text': clean_text(mapped.get('route_text')),
            'pickup_time': clean_text(mapped.get('pickup_time')),
            'end_time': clean_text(mapped.get('end_time')),
            'total_hours_text': clean_text(mapped.get('total_hours_text')),
            'cab_type': clean_cab(mapped.get('cab_type')),
            'employee_name': emp or name or 'Unknown',
            'start_km': num(mapped.get('start_km')),
            'end_km': num(mapped.get('end_km')),
            'total_km': num(mapped.get('total_km')),
            'duty_type': clean_text(mapped.get('duty_type')),
            'toll': num(mapped.get('toll')),
            'parking': num(mapped.get('parking')),
            'amount': num(mapped.get('amount')),
            'history_source': sheet,
        })

os.makedirs(os.path.dirname(out), exist_ok=True)
with open(out, 'w', encoding='utf-8') as handle:
    json.dump(rows, handle, ensure_ascii=False, separators=(',', ':'))
print('wrote', out, 'rows', len(rows), 'kb', round(os.path.getsize(out)/1024, 1))
print('months', Counter(r['trip_date'][:7] for r in rows))
