"""El mismo formato PBKDF2 en Windows y Cloudflare (Web Crypto en Workers)."""
import hmac
import secrets
import sys
from werkzeug import security


def _derive(password, salt, iterations):
    from js import crypto, Object, Uint8Array
    from pyodide.ffi import run_sync, to_js
    raw = Uint8Array.new(to_js(list(password.encode())))
    salt_bytes = Uint8Array.new(to_js(list(salt.encode())))
    key = run_sync(crypto.subtle.importKey('raw', raw, 'PBKDF2', False, to_js(['deriveBits'])))
    options = to_js(dict(name='PBKDF2', hash='SHA-256', salt=salt_bytes, iterations=iterations), dict_converter=Object.fromEntries)
    bits = run_sync(crypto.subtle.deriveBits(options, key, 256))
    return bytes(Uint8Array.new(bits).to_py()).hex()


def generate_password_hash(password, method='pbkdf2:sha256:600000'):
    if sys.platform != 'emscripten':
        return security.generate_password_hash(password, method=method)
    salt = secrets.token_hex(16)
    return f'pbkdf2:sha256:600000${salt}${_derive(password, salt, 600000)}'


def check_password_hash(stored, password):
    if sys.platform != 'emscripten':
        return security.check_password_hash(stored, password)
    try:
        method, salt, expected = stored.split('$')
        algorithm, digest, rounds = method.split(':')
        if algorithm != 'pbkdf2' or digest != 'sha256' or not 600000 <= int(rounds) <= 1000000:
            return False
        return hmac.compare_digest(_derive(password, salt, int(rounds)), expected)
    except (ValueError, TypeError):
        return False
