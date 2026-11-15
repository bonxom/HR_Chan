"""Explicit resource authorization extension point.

Future modules supply an async policy callable for their own objects. A missing
policy never authorizes access, and Admin is not a universal bypass.
"""

from typing import Protocol

from app.core.exceptions import AppError
from app.core.security import Principal
from app.modules.accounts.rules import AccountType


class ResourcePolicy(Protocol):
    async def __call__(self, principal: Principal, action: str, resource: object) -> bool: ...


def _denied() -> AppError:
    return AppError("Resource access denied", status_code=403, code="forbidden")


async def require_resource(
    principal: Principal,
    action: str,
    resource: object,
    policy: ResourcePolicy | None,
) -> None:
    if principal.account_type is AccountType.ADMIN:
        raise _denied()
    if policy is None:
        raise _denied()
    if not await policy(principal, action, resource):
        raise _denied()
