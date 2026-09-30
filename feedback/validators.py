from django.conf import settings
from django.core.exceptions import ValidationError

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


def validate_image(file):
    """Server-side image checks: size and real (Pillow-detected) type."""
    max_mb = getattr(settings, "FEEDBACK_MAX_IMAGE_MB", 2)
    if file.size > max_mb * 1024 * 1024:
        raise ValidationError(f"Image is too large. The limit is {max_mb} MB.")
    # ImageField sets content_type from the file's real format, not its extension.
    if getattr(file, "content_type", None) not in ALLOWED_CONTENT_TYPES:
        raise ValidationError("Use a JPG, PNG or WEBP image.")
