import base64
import hashlib

from cryptography.fernet import Fernet


def local_cipher(agent_secret: str) -> Fernet:
    key = hashlib.sha256(f"service-monitor-agent:{agent_secret}".encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))
