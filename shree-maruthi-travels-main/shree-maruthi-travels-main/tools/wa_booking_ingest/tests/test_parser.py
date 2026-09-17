import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from parser import parse_date, parse_table_text, parse_time
from validate import validate_booking


class ParserTests(unittest.TestCase):
    def test_dates(self):
        self.assertEqual(parse_date('17/09/2026'), '2026-09-17')
        self.assertEqual(parse_date('2026-09-17'), '2026-09-17')
        self.assertEqual(parse_date('17 Sep 2026'), '2026-09-17')
        self.assertIsNone(parse_date('not a date'))

    def test_times(self):
        self.assertEqual(parse_time('08:30 AM'), '08:30')
        self.assertEqual(parse_time('09.15'), '09:15')
        self.assertEqual(parse_time('1330'), '13:30')
        self.assertEqual(parse_time('1:05 PM'), '13:05')
        self.assertIsNone(parse_time('99:99'))

    def test_table_extraction(self):
        text = (ROOT / 'tests/fixtures/sample_table.txt').read_text(encoding='utf-8')
        rows = parse_table_text(text, source_message_id='msg-1', source_image='sample.jpg')
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]['booking_id'], 'B260917-AB12')
        self.assertEqual(rows[0]['trip_date'], '2026-09-17')
        self.assertEqual(rows[0]['trip_time'], '08:30')
        self.assertEqual(rows[2]['cab_type'], 'CRYSTA')
        self.assertEqual(rows[0]['source_message_id'], 'msg-1')

    def test_malformed_ocr_does_not_invent(self):
        rows = parse_table_text(
            'BOOKING_ID\tBOOKING_TYPE\tCAB_TYPE\tTRIP_DATE\tTRIP_TIME\tPLANNED_START_ADDRESS\n'
            '??\t##\t@@\tnot-a-date\tzz\t'
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['booking_id'], '??')
        self.assertFalse(rows[0]['trip_date'])
        ok, reasons, _ = validate_booking(rows[0])
        self.assertFalse(ok)
        self.assertTrue(reasons)


class ValidateTests(unittest.TestCase):
    def test_ok_row(self):
        ok, reasons, cleaned = validate_booking({
            'booking_id': 'B260917-AB12',
            'booking_type': '12HRS-120KM',
            'cab_type': 'SEDAN',
            'trip_date': '17/09/2026',
            'trip_time': '08:30 AM',
            'planned_start_address': 'Whitefield',
            'confidence': 0.9,
        })
        self.assertTrue(ok, reasons)
        self.assertEqual(cleaned['trip_date'], '2026-09-17')
        self.assertEqual(cleaned['trip_time'], '08:30')

    def test_missing_id(self):
        ok, reasons, _ = validate_booking({
            'booking_type': 'DROP', 'cab_type': 'SEDAN', 'trip_date': '2026-09-17',
            'trip_time': '09:00', 'planned_start_address': 'Harlur',
        })
        self.assertFalse(ok)
        self.assertTrue(any('booking_id' in item for item in reasons))


if __name__ == '__main__':
    unittest.main()
