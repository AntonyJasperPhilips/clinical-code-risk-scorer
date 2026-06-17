"""Reversible obfuscation stand-in for patient record encryption.

NOTE: This is a *demo* — a Caesar/XOR-style transform, NOT real cryptography.
Never use this for actual patient data.
"""


def _xor(data: bytes, key: int) -> bytes:
    return bytes(b ^ (key & 0xFF) for b in data)


def encrypt(plaintext: str, key: int) -> str:
    """Obfuscate a record string. Returns a hex-encoded payload."""
    if not 0 < key < 256:
        raise ValueError("key must be in range 1..255")
    return _xor(plaintext.encode("utf-8"), key).hex()


def decrypt(payload_hex: str, key: int) -> str:
    """Reverse :func:`encrypt`."""
    if not 0 < key < 256:
        raise ValueError("key must be in range 1..255")
    return _xor(bytes.fromhex(payload_hex), key).decode("utf-8")
