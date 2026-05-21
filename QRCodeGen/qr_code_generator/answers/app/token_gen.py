import hashlib
import string
import time

from sqlalchemy.orm import Session

from .models import UrlMapping

BASE62_CHARS = string.ascii_letters + string.digits  # a-zA-Z0-9
TOKEN_LENGTH = 7
MAX_RETRIES = 10


def base62_encode(data: bytes) -> str:
    """Convert bytes to Base62 string."""
    num = int.from_bytes(data, "big")
    if num == 0:
        return BASE62_CHARS[0]
    result = []
    while num > 0:
        num, remainder = divmod(num, 62)
        result.append(BASE62_CHARS[remainder])
    return "".join(reversed(result))


def token_exists_in_db(db: Session, token: str) -> bool:
    return db.query(UrlMapping).filter(UrlMapping.token == token).first() is not None


def generate_token(url: str, db: Session) -> str:
    """SHA-256 + nonce + Base62 token generation with collision retry."""
    for attempt in range(MAX_RETRIES):

        # nonce = timestamp + attempt → 不同時間點產生不同 hash
        # Production 會加 user_id 確保不同用戶同 URL → 不同 token
        nonce = f"{int(time.time())}_{attempt}"
        hash_input = url + nonce

        # Take first N chars + URL-safe encoding
        raw_hash = hashlib.sha256(hash_input.encode()).digest()
        token = base62_encode(raw_hash)[:TOKEN_LENGTH]

        if not token_exists_in_db(db, token):
            return token

    raise RuntimeError(f"Failed to generate unique token after {MAX_RETRIES} retries")
