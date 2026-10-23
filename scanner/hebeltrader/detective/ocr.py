import subprocess
import tempfile
from io import BytesIO
from pathlib import Path

from PIL import Image, UnidentifiedImageError

ALLOWED_MEDIA_TYPES = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}
MAX_IMAGE_BYTES = 2 * 1024 * 1024
MAX_PIXELS = 20_000_000


def validate_image(payload, media_type):
    if media_type not in ALLOWED_MEDIA_TYPES:
        raise ValueError("unsupported screenshot media type")
    if not payload or len(payload) > MAX_IMAGE_BYTES:
        raise ValueError("screenshot size outside allowed range")
    try:
        with Image.open(BytesIO(payload)) as image:
            if image.width * image.height > MAX_PIXELS:
                raise ValueError("screenshot pixel count exceeds limit")
            image.verify()
    except (UnidentifiedImageError, OSError):
        raise ValueError("invalid screenshot") from None


class TesseractOcr:
    engine = "local_tesseract"

    @staticmethod
    def _run(source, languages):
        return subprocess.run(
            ["tesseract", str(source), "stdout", "-l", languages],
            capture_output=True,
            check=False,
            timeout=20,
            text=True,
        )

    def extract(self, payload, media_type):
        validate_image(payload, media_type)
        suffix = "." + ALLOWED_MEDIA_TYPES[media_type]
        with tempfile.TemporaryDirectory(prefix="hebel-ocr-") as directory:
            source = Path(directory) / f"input{suffix}"
            source.write_bytes(payload)
            try:
                process = self._run(source, "deu+eng")
                if process.returncode != 0 and "Failed loading language 'deu'" in process.stderr:
                    process = self._run(source, "eng")
            except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
                raise ValueError("local OCR unavailable") from exc
        if process.returncode != 0:
            raise ValueError("local OCR failed")
        return process.stdout.strip()
