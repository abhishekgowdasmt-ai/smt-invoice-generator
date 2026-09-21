import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from parser import parse_date, parse_table_text, parse_time
from validate import validate_booking
from watcher import _header_is_target, _names_match


class NameMatchTests(unittest.TestCase):
    def test_group_name(self):
        self.assertTrue(_names_match('SMT On-call Support-Rac', 'SMT On-call Support-Rac'))
        self.assertTrue(_names_match('SMT On-call Support-Rac', 'smt on-call support-rac'))
        self.assertTrue(_names_match('SMT On call Support Rac', 'SMT On-call Support-Rac'))
        self.assertFalse(_names_match('Some other group', 'SMT On-call Support-Rac'))
        self.assertFalse(_names_match('SMT', 'SMT On-call Support-Rac'))
        self.assertFalse(_names_match('Rac', 'SMT On-call Support-Rac'))
        self.assertTrue(_header_is_target('SMT On-call Support-Rac', 'SMT On-call Support-Rac'))
        self.assertTrue(_header_is_target('smt on-call support-rac', 'SMT On-call Support-Rac'))
        self.assertFalse(_header_is_target('SMT On-call Support', 'SMT On-call Support-Rac'))
        self.assertFalse(_header_is_target('', 'SMT On-call Support-Rac'))


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

    def test_sep_dash_date_and_jumbled_pipe_row(self):
        self.assertEqual(parse_date('21-Sep-26'), '2026-09-21')
        self.assertEqual(parse_time('07:45:00'), '07:45')
        rows = parse_table_text(
            '21-Sep-26| B260920-FHMH Disposal - 12hrs/120kms 07:45:00|Ramanagara'
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['booking_id'], 'B260920-FHMH')
        self.assertEqual(rows[0]['trip_date'], '2026-09-21')
        self.assertEqual(rows[0]['trip_time'], '07:45')
        self.assertIn('Disposal', rows[0]['booking_type'])
        self.assertEqual(rows[0]['planned_start_address'], 'Ramanagara')
        ok, reasons, cleaned = validate_booking(rows[0])
        self.assertTrue(ok, reasons)
        self.assertEqual(cleaned['booking_id'], 'B260920-FHMH')
        self.assertEqual(cleaned['trip_time'], '07:45')

    def test_cab_not_required_when_other_fields_exist(self):
        ok, reasons, cleaned = validate_booking({
            'booking_id': 'B260920-FHMH',
            'booking_type': 'Disposal - 12hrs/120kms',
            'cab_type': '',
            'trip_date': '2026-09-21',
            'trip_time': '07:45',
            'planned_start_address': 'Ramanagara',
            'confidence': 0.83,
        })
        self.assertTrue(ok, reasons)
        self.assertEqual(cleaned['booking_id'], 'B260920-FHMH')
        self.assertFalse(cleaned.get('cab_type'))

    def test_missing_date_uses_upload_date(self):
        ok, reasons, cleaned = validate_booking({
            'booking_id': 'B260920-FHMH',
            'booking_type': 'Disposal',
            'cab_type': '',
            'trip_date': '',
            'trip_time': '07:45',
            'planned_start_address': 'Ramanagara',
            'upload_date': '2026-09-21T06:11:00Z',
            'confidence': 0.83,
        })
        self.assertTrue(ok, reasons)
        self.assertEqual(cleaned['trip_date'], '2026-09-21')

    def test_normalize_cab_dropdown_values(self):
        from validate import normalize_cab
        self.assertEqual(normalize_cab('SEDAN'), 'Sedan')
        self.assertEqual(normalize_cab('suv'), 'SUV')

    def test_approve_salvages_dumped_booking_id(self):
        ok, reasons, cleaned = validate_booking({
            'booking_id': '21-Sep-26| B260920-FHMH Disposal - 12hrs/120kms 07:45:00|Ramanagara',
            'booking_type': '',
            'cab_type': 'SEDAN',
            'trip_date': '',
            'trip_time': '',
            'planned_start_address': '',
            'confidence': 0.17,
        }, staff_override=True)
        self.assertTrue(ok, reasons)
        self.assertEqual(cleaned['booking_id'], 'B260920-FHMH')
        self.assertEqual(cleaned['trip_date'], '2026-09-21')
        self.assertEqual(cleaned['trip_time'], '07:45')

    def test_shifted_columns_pull_duty_and_time_from_cab(self):
        from parser import salvage_payload
        cleaned = salvage_payload({
            'booking_id': 'B260820-4B34',
            'booking_type': 'B260820-4B34',
            'cab_type': 'Disposal - 12hrs/ 120kms 07:30:00',
            'trip_date': '',
            'trip_time': '',
            'planned_start_address': '',
        })
        self.assertEqual(cleaned['booking_id'], 'B260820-4B34')
        self.assertIn('Disposal', cleaned['booking_type'])
        self.assertEqual(cleaned['trip_time'], '07:30')
        self.assertFalse(cleaned.get('cab_type'))

    def test_city_is_not_kept_as_booking_type(self):
        from parser import salvage_payload
        cleaned = salvage_payload({
            'booking_id': 'B260920-FHMH',
            'booking_type': 'Ramanagara',
            'cab_type': '',
            'trip_date': '2026-09-21',
            'trip_time': '',
            'planned_start_address': 'Ramanagara',
            'raw_line': '21-Sep-26| B260920-FHMH Disposal - 12hrs/120kms 07:45:00|Ramanagara',
        })
        self.assertEqual(cleaned['booking_id'], 'B260920-FHMH')
        self.assertIn('Disposal', cleaned['booking_type'])
        self.assertEqual(cleaned['trip_time'], '07:45')
        self.assertEqual(cleaned['planned_start_address'], 'Ramanagara')

    def test_split_ocr_lines_merge_duty_into_booking(self):
        rows = parse_table_text(
            '21-Sep-26| B260920-FHMH|Ramanagara\n'
            'Disposal - 12hrs/120kms 07:45:00'
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['booking_id'], 'B260920-FHMH')
        self.assertEqual(rows[0]['trip_time'], '07:45')
        self.assertIn('Disposal', rows[0]['booking_type'])

    def test_date_is_not_parsed_as_time(self):
        self.assertIsNone(parse_time('21-Sep-26'))


if __name__ == '__main__':
    unittest.main()
