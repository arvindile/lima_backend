import hashlib
import secrets

# PBKDF2 via hashlib — no external dependency needed (avoids repeating the
# Python 3.8 package-version issues from earlier). Good enough for a
# learning project; a production app would typically reach for bcrypt/argon2
# via passlib instead.

_ITERATIONS = 100_000


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), _ITERATIONS)
    return f"{salt}:{digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, hex_digest = stored.split(":")
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), _ITERATIONS)
    return secrets.compare_digest(digest.hex(), hex_digest)
