import hashlib
import os
import secrets
import time

import jwt

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


# --- Access tokens (JWT) -----------------------------------------------
#
# Issued once at login/registration, then sent back by the Android app as
# "Authorization: Bearer <token>" on every request that acts on behalf of
# a player. The backend verifies the signature + expiry and trusts the
# player id INSIDE the token — never a player_id the client merely typed
# into a URL or request body. See app/dependencies.py for where this gets
# checked on incoming requests.
#
# JWT_SECRET_KEY must be set as a real env var in production (Render). The
# fallback below only exists so the app still runs locally without extra
# setup — it is NOT safe to deploy with, since anyone who read this source
# file could forge tokens signed with it.
_DEV_ONLY_FALLBACK_SECRET = "dev-only-insecure-secret-change-me"
JWT_SECRET = os.getenv("JWT_SECRET_KEY", _DEV_ONLY_FALLBACK_SECRET)
if JWT_SECRET == _DEV_ONLY_FALLBACK_SECRET:
    print(
        "WARNING: JWT_SECRET_KEY is not set — using an insecure default. "
        "Set a real JWT_SECRET_KEY env var before deploying to Render.",
    )

JWT_ALGORITHM = "HS256"
JWT_EXPIRY_SECONDS = 60 * 60 * 24 * 30  # 30 days — see README notes on why


def create_access_token(player_id: str) -> str:
    now = int(time.time())
    payload = {"sub": player_id, "iat": now, "exp": now + JWT_EXPIRY_SECONDS}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> str:
    """Returns the player_id encoded in a valid token.

    Raises jwt.ExpiredSignatureError if the token's expiry has passed, or
    jwt.InvalidTokenError (its base class) for any other invalid/tampered
    token — callers should catch these and turn them into a 401.
    """
    payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    return payload["sub"]
