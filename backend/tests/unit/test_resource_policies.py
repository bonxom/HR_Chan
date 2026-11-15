import uuid

import pytest

from app.core.exceptions import AppError
from app.core.security import Principal
from app.modules.accounts.rules import AccountType, EmployeeRole
from app.modules.auth.policies import require_resource

ACCOUNT_ID = uuid.UUID("55555555-5555-4555-8555-555555555555")
SESSION_ID = uuid.UUID("66666666-6666-4666-8666-666666666666")


def principal(account_type: AccountType, roles: list[EmployeeRole]) -> Principal:
    from datetime import UTC, datetime, timedelta

    return Principal(
        account_id=ACCOUNT_ID,
        account_type=account_type,
        roles=tuple(roles),
        session_id=SESSION_ID,
        credential_version=0,
        session_absolute_expires_at=datetime.now(UTC) + timedelta(hours=1),
    )


def role_policy(allowed_role: EmployeeRole):
    async def policy(candidate: Principal, action: str, resource: object) -> bool:
        return allowed_role in candidate.roles

    return policy


def allow_all():
    async def policy(candidate: Principal, action: str, resource: object) -> bool:
        return True

    return policy


async def test_missing_policy_denies_access() -> None:
    employee = principal(AccountType.EMPLOYEE, [EmployeeRole.HR])
    with pytest.raises(AppError) as error:
        await require_resource(employee, "read", object(), None)
    assert error.value.status_code == 403
    assert error.value.code == "forbidden"


async def test_policy_returning_false_denies_access() -> None:
    employee = principal(AccountType.EMPLOYEE, [EmployeeRole.INTERVIEWER])
    with pytest.raises(AppError):
        await require_resource(employee, "read", object(), role_policy(EmployeeRole.HR))


async def test_admin_is_not_a_resource_bypass() -> None:
    admin = principal(AccountType.ADMIN, [])
    with pytest.raises(AppError):
        await require_resource(admin, "read", object(), allow_all())


async def test_role_union_can_grant_access() -> None:
    employee = principal(AccountType.EMPLOYEE, [EmployeeRole.HR, EmployeeRole.DEPT_MANAGER])
    await require_resource(employee, "read", object(), role_policy(EmployeeRole.DEPT_MANAGER))
    await require_resource(employee, "read", object(), role_policy(EmployeeRole.HR))


async def test_policy_receives_the_requested_action_and_object() -> None:
    employee = principal(AccountType.EMPLOYEE, [EmployeeRole.HR])
    resource = {"id": 7}
    seen: list[tuple[str, object]] = []

    async def policy(candidate: Principal, action: str, item: object) -> bool:
        seen.append((action, item))
        return True

    await require_resource(employee, "approve", resource, policy)
    assert seen == [("approve", resource)]
