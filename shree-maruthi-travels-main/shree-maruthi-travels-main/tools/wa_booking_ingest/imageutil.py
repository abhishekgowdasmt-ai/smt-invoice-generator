"""Image hashing and integrity checks. No OCR here."""
import hashlib
from pathlib import Path


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def verify_image(path):
    path = Path(path)
    if not path.is_file():
        raise RuntimeError('image file is missing')
    size = path.stat().st_size
    if size <= 32:
        raise RuntimeError('image file is empty or incomplete')
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError('Pillow is required to verify images') from exc
    with Image.open(path) as image:
        image.verify()
    with Image.open(path) as image:
        image.load()
        if not image.size[0] or not image.size[1]:
            raise RuntimeError('image has no pixels')
    return size
