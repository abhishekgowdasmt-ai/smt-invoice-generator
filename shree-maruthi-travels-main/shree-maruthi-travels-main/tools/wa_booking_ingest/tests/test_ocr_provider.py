import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config
import ocr_provider
from logutil import redact


class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.payload).encode('utf-8')


class OCRProviderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.image = self.tmp / 'shot.jpg'
        from PIL import Image
        Image.new('RGB', (40, 20), (255, 255, 255)).save(self.image, format='JPEG')
        self.old = (
            config.OCR_PROVIDER,
            config.OCR_SPACE_API_KEY,
            config.GEMINI_API_KEY,
            config.AI_API_KEY,
            config.AI_API_URL,
        )

    def tearDown(self):
        (
            config.OCR_PROVIDER,
            config.OCR_SPACE_API_KEY,
            config.GEMINI_API_KEY,
            config.AI_API_KEY,
            config.AI_API_URL,
        ) = self.old

    def test_auto_without_keys_uses_local(self):
        config.OCR_PROVIDER = 'auto'
        config.OCR_SPACE_API_KEY = ''
        config.GEMINI_API_KEY = ''
        provider = ocr_provider.get_provider()
        self.assertEqual(provider.name, 'local')

    def test_auto_prefers_gemini_then_ocrspace_then_local(self):
        config.OCR_PROVIDER = 'auto'
        config.GEMINI_API_KEY = 'gemini-test-key-12345'
        config.OCR_SPACE_API_KEY = 'ocrspace-test-key-12345'
        self.assertEqual(ocr_provider.get_provider().name, 'gemini+ocrspace+local')

    def test_ocrspace_extracts_text(self):
        config.OCR_SPACE_API_KEY = 'ocrspace-test-key-12345'
        fake = FakeResponse({
            'IsErroredOnProcessing': False,
            'ParsedResults': [{'ParsedText': 'B260921-FHMH\tDisposal\tSEDAN\t21-Sep-26\t07:45\tRamanagara'}],
        })
        with mock.patch('urllib.request.urlopen', return_value=fake) as opened:
            text = ocr_provider.OCRSpaceProvider().extract_text(self.image)
        self.assertIn('B260921-FHMH', text)
        self.assertTrue(opened.called)
        body = opened.call_args[0][0].data.decode('utf-8')
        self.assertNotIn('ocrspace-test-key-12345', redact(body))

    def test_ocrspace_falls_back_to_local(self):
        config.OCR_PROVIDER = 'ocrspace'
        config.OCR_SPACE_API_KEY = 'ocrspace-test-key-12345'
        with mock.patch.object(ocr_provider.OCRSpaceProvider, 'extract_text', side_effect=RuntimeError('quota')):
            with mock.patch.object(ocr_provider.LocalOCRProvider, 'extract_text', return_value='B260921-FALL\tDROP'):
                text = ocr_provider.get_provider().extract_text(self.image)
        self.assertIn('B260921-FALL', text)

    def test_gemini_extracts_text(self):
        config.GEMINI_API_KEY = 'gemini-test-key-12345'
        fake = FakeResponse({
            'candidates': [{'content': {'parts': [{'text': 'BOOKING_ID\tCAB_TYPE\nB260921-GEMX\tSEDAN'}]}}],
        })
        with mock.patch('urllib.request.urlopen', return_value=fake):
            text = ocr_provider.GeminiProvider().extract_text(self.image)
        self.assertIn('B260921-GEMX', text)

    def test_redact_hides_ocr_keys(self):
        config.OCR_SPACE_API_KEY = 'ocrspace-secret-key-99999'
        config.GEMINI_API_KEY = 'gemini-secret-key-88888'
        message = redact('ocr=ocrspace-secret-key-99999 gem=gemini-secret-key-88888')
        self.assertNotIn('ocrspace-secret-key-99999', message)
        self.assertNotIn('gemini-secret-key-88888', message)
        self.assertIn('[redacted]', message)

    def test_frontend_does_not_embed_ocr_keys(self):
        page = ROOT.parents[1] / 'rac' / 'frontend' / 'src' / 'pages' / 'BookingOcrPage.jsx'
        text = page.read_text(encoding='utf-8') if page.is_file() else ''
        self.assertTrue(page.is_file())
        self.assertNotIn('OCR_SPACE_API_KEY', text)
        self.assertNotIn('GEMINI_API_KEY', text)
        self.assertNotIn('api.ocr.space', text)


if __name__ == '__main__':
    unittest.main()
