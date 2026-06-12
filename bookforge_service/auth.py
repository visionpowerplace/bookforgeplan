"""Authentication helpers — password hashing + signed-cookie sessions, stdlib only.

No external auth library. Passwords are PBKDF2-HMAC-SHA256 with a per-user salt;
sessions are a signed, expiring cookie (HMAC-SHA256). The signing secret comes from
SECRET_KEY, or is generated once and persisted under BOOKFORGE_DATA so sessions
survive restarts.
"""
import base64
import hashlib
import hmac
import os
import secrets
import time

from . import db

COOKIE = "bf_session"
_ITERS = 200_000


def _secret() -> str:
    s = os.environ.get("SECRET_KEY")
    if s:
        return s
    path = os.path.join(db.DATA_DIR, ".secret")
    os.makedirs(db.DATA_DIR, exist_ok=True)
    if os.path.exists(path):
        return open(path).read().strip()
    s = secrets.token_hex(32)
    with open(path, "w") as f:
        f.write(s)
    return s


# ---- passwords ------------------------------------------------------------

def hash_password(pw: str, salt: str = None):
    salt = salt or secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), _ITERS).hex()
    return h, salt


def verify_password(pw: str, pw_hash: str, salt: str) -> bool:
    test = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), _ITERS).hex()
    return hmac.compare_digest(test, pw_hash)


# ---- sessions -------------------------------------------------------------

def make_session(user_id: int, days: int = 30) -> str:
    exp = int(time.time()) + days * 86400
    payload = f"{user_id}.{exp}"
    sig = hmac.new(_secret().encode(), payload.encode(), hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(f"{payload}.{sig}".encode()).decode()


def read_session(token: str):
    try:
        raw = base64.urlsafe_b64decode(token.encode()).decode()
        user_id, exp, sig = raw.split(".")
        good = hmac.new(_secret().encode(), f"{user_id}.{exp}".encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(good, sig):
            return None
        if int(exp) < time.time():
            return None
        return int(user_id)
    except Exception:
        return None


def current_user(request):
    """Return the logged-in user dict, or None."""
    tok = request.cookies.get(COOKIE)
    if not tok:
        return None
    uid = read_session(tok)
    if uid is None:
        return None
    return db.get_user(uid)
