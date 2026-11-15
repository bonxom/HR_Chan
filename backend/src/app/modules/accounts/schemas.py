from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.modules.accounts.models import Account
from app.modules.accounts.rules import (
    FULL_NAME_MAX,
    REASON_MAX,
    AccountStatus,
    AccountType,
    EmployeeRole,
)


class AccountRead(BaseModel):
    id: UUID
    full_name: str
    email: str
    account_type: AccountType
    roles: list[EmployeeRole]
    status: AccountStatus
    created_at: datetime
    last_login_at: datetime | None

    @classmethod
    def from_account(cls, account: Account) -> "AccountRead":
        return cls(
            id=account.id,
            full_name=account.full_name,
            email=account.email,
            account_type=account.account_type,
            roles=[EmployeeRole(role) for role in account.roles],
            status=account.status,
            created_at=account.created_at,
            last_login_at=account.last_login_at,
        )


class AccountPageRead(BaseModel):
    items: list[AccountRead]
    next_cursor: str | None


class AccountCreateRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=FULL_NAME_MAX)
    email: EmailStr
    account_type: AccountType
    roles: list[EmployeeRole] = Field(default_factory=list)


class RolesReplaceRequest(BaseModel):
    roles: list[EmployeeRole]


class ReasonRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=REASON_MAX)


class AccountDeliveryRead(BaseModel):
    account: AccountRead
    email_delivery: str
