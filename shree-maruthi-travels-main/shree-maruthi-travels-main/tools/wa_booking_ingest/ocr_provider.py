"""Replaceable OCR providers. External APIs run server-side only; Tesseract is fallback."""
import base64
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from io import BytesIO
from pathlib import Path

from parser import parse_table_text


class OCRProvider:
    name = 'base'

    def extract_text(self, image_path):
        raise NotImplementedError


def _jpeg_bytes(image_path, max_side=1600, quality=80, max_bytes=900000):
    from PIL import Image
    image = Image.open(image_path).convert('RGB')
    width, height = image.size
    scale = min(1.0, float(max_side) / max(width, height, 1))
    if scale < 1:
        image = image.resize((max(1, int(width * scale)), max(1, int(height * scale))))
    q = quality
    payload = b''
    while q >= 40:
        buf = BytesIO()
        image.save(buf, format='JPEG', quality=q, optimize=True)
        payload = buf.getvalue()
        if len(payload) <= max_bytes:
            return payload
        q -= 10
    return payload


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


class OCRSpaceProvider(OCRProvider):
    name = 'ocrspace'

    def extract_text(self, image_path):
        import config
        from logutil import log, redact
        if not config.OCR_SPACE_API_KEY:
            raise RuntimeError('OCR_SPACE_API_KEY is not set')
        encoded = base64.b64encode(_jpeg_bytes(image_path)).decode('ascii')
        body = urllib.parse.urlencode({
            'apikey': config.OCR_SPACE_API_KEY,
            'base64Image': f'data:image/jpeg;base64,{encoded}',
            'language': 'eng',
            'isOverlayRequired': 'false',
            'OCREngine': '2',
            'isTable': 'true',
            'scale': 'true',
        }).encode('utf-8')
        req = urllib.request.Request(
            config.OCR_SPACE_URL,
            data=body,
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            method='POST',
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode('utf-8'))
        except urllib.error.HTTPError as exc:
            raise RuntimeError(redact(f'OCR.space HTTP {exc.code}')) from exc
        if data.get('IsErroredOnProcessing'):
            raise RuntimeError(redact(str(data.get('ErrorMessage') or 'OCR.space failed')))
        parts = []
        for item in data.get('ParsedResults') or []:
            text = (item.get('ParsedText') or '').strip()
            if text:
                parts.append(text)
        if not parts:
            raise RuntimeError('OCR.space returned no text')
        log.info('[OCR] ocrspace chars=%s', sum(len(part) for part in parts))
        return '\n'.join(parts)


def _gemini_models():
    import config
    names = []
    for name in (
        config.GEMINI_MODEL,
        'gemini-2.5-flash',
        'gemini-2.0-flash',
        'gemini-2.0-flash-001',
        'gemini-1.5-flash',
    ):
        if name and name not in names:
            names.append(name)
    return names


def normalize_model_text(text):
    cleaned = str(text or '').strip()
    if cleaned.startswith('```'):
        cleaned = re.sub(r'^```(?:tsv|csv|json|text)?\s*', '', cleaned, flags=re.I)
        cleaned = re.sub(r'\s*```$', '', cleaned)
    stripped = cleaned.strip()
    if stripped.startswith('[') or stripped.startswith('{'):
        try:
            data = json.loads(stripped)
        except Exception:
            return cleaned
        rows = data if isinstance(data, list) else data.get('bookings') or data.get('rows') or [data]
        lines = ['BOOKING_ID\tBOOKING_TYPE\tCAB_TYPE\tTRIP_DATE\tTRIP_TIME\tPLANNED_START_ADDRESS']
        for row in rows:
            if not isinstance(row, dict):
                continue
            lines.append('\t'.join(str(row.get(key) or '') for key in (
                'booking_id', 'booking_type', 'cab_type', 'trip_date', 'trip_time', 'planned_start_address',
            )))
        return '\n'.join(lines)
    return cleaned


class GeminiProvider(OCRProvider):
    name = 'gemini'

    def extract_text(self, image_path):
        import config
        from logutil import log, redact
        if not config.GEMINI_API_KEY:
            raise RuntimeError('GEMINI_API_KEY is not set')
        encoded = base64.b64encode(_jpeg_bytes(image_path, max_side=2000, max_bytes=3_500_000)).decode('ascii')
        prompt = (
            'This is an SMT cab booking table screenshot. '
            'Each booking may be one row like: date | BOOKING_ID duty 12hrs/120kms HH:MM | location. '
            'Return TSV only with headers BOOKING_ID, BOOKING_TYPE, CAB_TYPE, TRIP_DATE, TRIP_TIME, PLANNED_START_ADDRESS. '
            'BOOKING_TYPE is Disposal/Drop/Pickup/12hrs. TRIP_DATE as YYYY-MM-DD. TRIP_TIME as HH:MM. '
            'Leave CAB_TYPE empty unless SEDAN/SUV/CRYSTA/etc is visible. Do not invent values.'
        )
        body = json.dumps({
            'contents': [{
                'parts': [
                    {'text': prompt},
                    {'inlineData': {'mimeType': 'image/jpeg', 'data': encoded}},
                ]
            }]
        }).encode('utf-8')
        last_error = None
        for model in _gemini_models():
            url = (
                f'https://generativelanguage.googleapis.com/v1beta/models/'
                f'{urllib.parse.quote(model)}:generateContent'
            )
            req = urllib.request.Request(
                url,
                data=body,
                headers={
                    'Content-Type': 'application/json',
                    'x-goog-api-key': config.GEMINI_API_KEY,
                },
                method='POST',
            )
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    data = json.loads(resp.read().decode('utf-8'))
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode('utf-8', errors='replace')[:200]
                last_error = RuntimeError(redact(f'Gemini {model} HTTP {exc.code} {detail}'))
                log.warning('[OCR] %s', last_error)
                continue
            parts = (((data.get('candidates') or [{}])[0].get('content') or {}).get('parts') or [])
            text = normalize_model_text('\n'.join(str(part.get('text') or '') for part in parts))
            if text.strip():
                log.info('[OCR] gemini model=%s chars=%s', model, len(text))
                return text
            last_error = RuntimeError(f'Gemini {model} returned no text')
        if last_error:
            raise last_error
        raise RuntimeError('Gemini returned no text')


class OptionalAIProvider(OCRProvider):
    name = 'ai'

    def extract_text(self, image_path):
        import config
        if not config.AI_API_KEY or not config.AI_API_URL:
            raise RuntimeError('AI OCR is not configured. Set AI_API_URL and AI_API_KEY.')
        encoded = base64.b64encode(Path(image_path).read_bytes()).decode('ascii')
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


class FallbackProvider(OCRProvider):
    def __init__(self, providers):
        self.providers = [item for item in providers if item]
        self.name = '+'.join(item.name for item in self.providers) or 'empty'

    def extract_text(self, image_path):
        from logutil import log, redact
        last_error = None
        for provider in self.providers:
            try:
                text = provider.extract_text(image_path)
                if str(text or '').strip():
                    return text
                last_error = RuntimeError(f'{provider.name} returned empty text')
            except Exception as exc:
                last_error = exc
                log.warning('[OCR] %s failed: %s', provider.name, redact(exc))
        if last_error:
            raise last_error
        raise RuntimeError('No OCR provider is configured')


def get_provider():
    import config
    requested = config.OCR_PROVIDER
    local = LocalOCRProvider()
    if requested in ('ocrspace', 'ocr.space'):
        return FallbackProvider([OCRSpaceProvider(), local])
    if requested in ('gemini', 'google'):
        return FallbackProvider([GeminiProvider(), local])
    if requested == 'ai':
        return OptionalAIProvider()
    if requested == 'local':
        return local
    chain = []
    if config.GEMINI_API_KEY:
        chain.append(GeminiProvider())
    if config.OCR_SPACE_API_KEY:
        chain.append(OCRSpaceProvider())
    chain.append(local)
    return FallbackProvider(chain)


def extract_bookings(image_path, source_message_id=''):
    from logutil import log
    provider = get_provider()
    log.info('[OCR] provider=%s file=%s', provider.name, Path(image_path).name)
    text = provider.extract_text(image_path)
    rows = parse_table_text(text, source_message_id=source_message_id, source_image=str(image_path))
    return text, rows
