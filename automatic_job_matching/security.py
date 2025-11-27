import ipaddress
import re
from collections.abc import Iterable

from django.core.exceptions import ValidationError

MAX_DESCRIPTION_LENGTH = 1024
MAX_UNIT_LENGTH = 32
MAX_JSON_PAYLOAD_BYTES = 10 * 1024

_UNIT_PATTERN = re.compile(r"^[A-Za-z0-9./\-\s]{0,%d}$" % MAX_UNIT_LENGTH)


class SecurityValidationError(ValidationError):
    """Raised when incoming data violates a security constraint."""


def sanitize_description(raw_description: str) -> str:
    """Normalize and validate a description payload."""
    if raw_description is None:
        raise SecurityValidationError("Description is required.")

    description = raw_description.strip()
    if not description:
        raise SecurityValidationError("Description cannot be empty.")
    if len(description) > MAX_DESCRIPTION_LENGTH:
        raise SecurityValidationError("Description is too long.")
    return description


def sanitize_unit(raw_unit: str | None) -> str | None:
    """Ensure the provided unit is short and lacks dangerous characters."""
    if raw_unit is None:
        return None

    unit = raw_unit.strip()
    if not unit:
        return None
    if len(unit) > MAX_UNIT_LENGTH or not _UNIT_PATTERN.fullmatch(unit):
        raise SecurityValidationError("Unit contains invalid characters.")
    return unit


def ensure_payload_size(body: bytes, max_bytes: int = MAX_JSON_PAYLOAD_BYTES) -> None:
    """Prevent overly-large JSON payloads from being processed."""
    if body and len(body) > max_bytes:
        raise SecurityValidationError("Payload too large.")


def is_safe_url(target_url: str, allowed_schemes: Iterable[str] = ("http", "https")) -> bool:
    """Reject URLs that could be used for SSRF attacks."""
    if not target_url:
        return False

    pattern = re.compile(r"^(?P<scheme>[a-zA-Z][a-zA-Z0-9+.-]*):\/\/(?P<host>[^\/]+)")
    match = pattern.match(target_url.strip())
    if not match:
        return False

    scheme = match.group("scheme").lower()
    if scheme not in allowed_schemes:
        return False

    host = match.group("host").split(":")[0]
    try:
        ipaddress.ip_address(host)
    except ValueError:
        # Domain names are acceptable
        return True

    ip = ipaddress.ip_address(host)
    return not (ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_unspecified)