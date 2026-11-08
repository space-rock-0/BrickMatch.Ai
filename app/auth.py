"""Minimal dependency-free password hashing and signed bearer tokens."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time


def hash_password(password: str) -> str:
    if len(password) < 10:
        raise ValueError("Password must be at least 10 characters")
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt$16384$8$1${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt_hex, digest_hex = stored.split("$")
        actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex),
                                n=int(n), r=int(r), p=int(p))
        return scheme == "scrypt" and hmac.compare_digest(actual.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def _encode(value: dict) -> str:
    raw = json.dumps(value, separators=(",", ":"), sort_keys=True).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _secret() -> bytes:
    secret = os.getenv("BRICKMATCH_AUTH_SECRET")
    if not secret:
        if os.getenv("BRICKMATCH_AUTH_REQUIRED", "false").lower() == "true":
            raise RuntimeError("BRICKMATCH_AUTH_SECRET is required when authentication is enabled")
        secret = "local-development-only-change-me"
    return secret.encode()


def issue_token(user_id: str, expires_seconds: int = 60 * 60 * 24 * 7) -> str:
    header = _encode({"alg": "HS256", "typ": "JWT"})
    payload = _encode({"sub": user_id, "exp": int(time.time()) + expires_seconds})
    signed = f"{header}.{payload}".encode()
    signature = hmac.new(_secret(), signed, hashlib.sha256).digest()
    encoded = base64.urlsafe_b64encode(signature).rstrip(b"=").decode()
    return f"{header}.{payload}.{encoded}"


def verify_token(token: str) -> str | None:
    try:
        header, payload, signature = token.split(".")
        expected = hmac.new(_secret(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
        actual = base64.urlsafe_b64decode(signature + "=" * (-len(signature) % 4))
        if not hmac.compare_digest(expected, actual):
            return None
        data = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        return data["sub"] if int(data["exp"]) > int(time.time()) else None
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None
