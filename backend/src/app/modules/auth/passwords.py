"""Argon2id password hashing.

Parameters (documented per specification): Argon2id, 64 MiB memory, three
iterations, parallelism four, 32-byte digest, 16-byte salt. Callers offload these
CPU-bound calls from the event loop with the ``*_async`` helpers.
"""

import asyncio

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

ARGON2_TIME_COST = 3
ARGON2_MEMORY_COST = 64 * 1024
ARGON2_PARALLELISM = 4
ARGON2_HASH_LEN = 32
ARGON2_SALT_LEN = 16

# Fixed hash used to keep unknown-identity logins comparable in cost.
DUMMY_PASSWORD_HASH = (  # noqa: E501 - fixed Argon2 encoded string
    "$argon2id$v=19$m=65536,t=3,p=4$RuEebcyqKEZuJHcakGjllQ$IVZNyw6we36oET0bIN7+o7MhCBXEpo5Wgl3FDlAXgGg"
)

_hasher = PasswordHasher(
    time_cost=ARGON2_TIME_COST,
    memory_cost=ARGON2_MEMORY_COST,
    parallelism=ARGON2_PARALLELISM,
    hash_len=ARGON2_HASH_LEN,
    salt_len=ARGON2_SALT_LEN,
)


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, encoded: str | None) -> bool:
    if not encoded:
        return False
    try:
        return _hasher.verify(encoded, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


async def hash_password_async(password: str) -> str:
    return await asyncio.to_thread(hash_password, password)


async def verify_password_async(password: str, encoded: str | None) -> bool:
    return await asyncio.to_thread(verify_password, password, encoded)


async def verify_dummy_password(password: str) -> bool:
    """Spend comparable verification work for identities that do not exist."""
    await verify_password_async(password, DUMMY_PASSWORD_HASH)
    return False
