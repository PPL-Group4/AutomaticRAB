import re
from urllib.parse import urlparse

PRIVATE_IP_PATTERNS = [
    r"^127\.",             # localhost
    r"^10\.",              # 10.0.0.0/8
    r"^172\.(1[6-9]|2\d|3[0-1])\.",  # 172.16.0.0/12
    r"^192\.168\.",        # 192.168.0.0/16
    r"^169\.254\.",        # Link-local
]

def is_private_address(netloc: str) -> bool:
    for pattern in PRIVATE_IP_PATTERNS:
        if re.match(pattern, netloc):
            return True
    return False

def contains_url(text: str) -> bool:
    return "http://" in text.lower() or "https://" in text.lower()

def block_ssrf(text: str):
    if not contains_url(text):
        return

    parsed = urlparse(text)
    netloc = parsed.hostname or ""

    # block internal/private IPs
    if is_private_address(netloc):
        raise ValueError("SSRF blocked: private/internal address")

    # block file:// scheme smuggling
    if parsed.scheme in {"file", "gopher", "ftp"}:
        raise ValueError("SSRF blocked: unsupported scheme")

    # block empty host
    if not netloc:
        raise ValueError("SSRF blocked: malformed URL")
