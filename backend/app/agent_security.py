import hashlib
import hmac
import secrets
import threading
import time
from collections import defaultdict, deque


def generate_agent_secret() -> str:
    return secrets.token_urlsafe(32)


def hash_agent_secret(value: str, app_secret: str) -> str:
    return hmac.new(app_secret.encode(), value.encode(), hashlib.sha256).hexdigest()


def verify_agent_secret(value: str, expected_hash: str, app_secret: str) -> bool:
    actual = hash_agent_secret(value, app_secret)
    return hmac.compare_digest(actual, expected_hash)


class EnrollmentRateLimiter:
    def __init__(self, max_attempts: int = 10, window_seconds: int = 60):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._attempts = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        threshold = now - self.window_seconds
        with self._lock:
            attempts = self._attempts[key]
            while attempts and attempts[0] <= threshold:
                attempts.popleft()
            if len(attempts) >= self.max_attempts:
                return False
            attempts.append(now)
            return True
