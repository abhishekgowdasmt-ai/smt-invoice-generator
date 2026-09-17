"""Replaceable OCR providers. Local Tesseract is default; AI is optional."""
from parser import parse_table_text


class OCRProvider:
    name = 'base'

    def extract_text(self, image_path):
        raise NotImplementedError


class LocalOCRProvider(OCRProvider):
    name = 'local'

    def extract_text(self, image_path):
        import config
        try:
            import pytesseract
            from PIL import Image, ImageOps, ImageFilter
        except ImportError as exc:
            raise RuntimeError('pytesseract and Pillow are required for local OCR') from exc
        if config.TESSERACT_CMD:
            pytesseract.pytesseract.tesseract_cmd = config.TESSERACT_CMD
        image = Image.open(image_path)
        gray = ImageOps.grayscale(image)
        sharp = gray.filter(ImageFilter.SHARPEN)
        try:
            import cv2
            import numpy as np
            arr = np.array(sharp)
            arr = cv2.threshold(arr, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
            sharp = Image.fromarray(arr)
        except Exception:
            pass
        return pytesseract.image_to_string(sharp, config='--psm 6')


class OptionalAIProvider(OCRProvider):
    name = 'ai'

    def extract_text(self, image_path):
        import base64
        import json
        import urllib.request
        import config
        if not config.AI_API_KEY or not config.AI_API_URL:
            raise RuntimeError('AI OCR is not configured. Set AI_API_URL and AI_API_KEY.')
        with open(image_path, 'rb') as handle:
            encoded = base64.b64encode(handle.read()).decode('ascii')
        body = json.dumps({
            'model': 'gpt-4o-mini',
            'input': 'Extract every booking table row as TSV with headers BOOKING_ID, BOOKING_TYPE, CAB_TYPE, TRIP_DATE, TRIP_TIME, PLANNED_START_ADDRESS. Do not invent values.',
            'image_b64': encoded,
        }).encode('utf-8')
        req = urllib.request.Request(
            config.AI_API_URL,
            data=body,
            headers={'Authorization': f'Bearer {config.AI_API_KEY}', 'Content-Type': 'application/json'},
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        return data.get('text') or data.get('output') or ''


def get_provider():
    import config
    if config.OCR_PROVIDER == 'ai':
        return OptionalAIProvider()
    return LocalOCRProvider()


def extract_bookings(image_path, source_message_id=''):
    provider = get_provider()
    text = provider.extract_text(image_path)
    rows = parse_table_text(text, source_message_id=source_message_id, source_image=str(image_path))
    return text, rows
