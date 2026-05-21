from urllib.parse import urlparse

MAX_URL_LENGTH = 2048

BLOCKED_DOMAINS = {
    "evil.com",
    "malware.example.com",
    "phishing.example.com",
}


def is_blocked_domain(hostname: str | None) -> bool:
    if hostname is None:
        return True
    return hostname.lower() in BLOCKED_DOMAINS


def validate_url(url: str) -> str:
    """Format check, normalization, and blocklist validation."""
    if len(url) > MAX_URL_LENGTH:  # Exceeds max length
        raise ValueError("URL exceeds max length")

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Invalid scheme")

    # Normalization — same URL should map to one token
    normalized = url.lower().rstrip("/")
    if parsed.scheme == "http":
        normalized = normalized.replace("http://", "https://", 1)

    # Malicious URL — short links should not become phishing vectors
    if is_blocked_domain(parsed.hostname):
        raise ValueError("URL is on blocklist")

    return normalized
