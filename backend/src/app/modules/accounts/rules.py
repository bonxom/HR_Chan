"""Account identity rules that do not depend on persistence or HTTP layers."""

from collections.abc import Sequence
from enum import StrEnum


class AccountType(StrEnum):
    ADMIN = "ADMIN"
    EMPLOYEE = "EMPLOYEE"


class EmployeeRole(StrEnum):
    HR = "HR"
    INTERVIEWER = "INTERVIEWER"
    DEPT_MANAGER = "DEPT_MANAGER"
    PROBATION = "PROBATION"


class AccountStatus(StrEnum):
    PENDING_SETUP = "PENDING_SETUP"
    ACTIVE = "ACTIVE"
    LOCKED = "LOCKED"
    PASSWORD_RESET_REQUIRED = "PASSWORD_RESET_REQUIRED"
    DISABLED = "DISABLED"


EMPLOYEE_ROLE_VALUES: tuple[str, ...] = tuple(role.value for role in EmployeeRole)
PROBATION_ROLE = EmployeeRole.PROBATION.value

FULL_NAME_MIN = 1
FULL_NAME_MAX = 200
REASON_MIN = 1
REASON_MAX = 1000
PASSWORD_MIN_CHARS = 8
PASSWORD_MAX_CHARS = 128
PAGE_SIZE_MIN = 1
PAGE_SIZE_MAX = 100
PAGE_SIZE_DEFAULT = 25


class RuleViolation(ValueError):
    """Raised when a value violates an account invariant."""


def normalize_email(email: str) -> str:
    return email.strip().lower()


def email_domain(email: str) -> str:
    normalized = normalize_email(email)
    _, separator, domain = normalized.rpartition("@")
    if not separator:
        raise RuleViolation("Enter a valid email address")
    return domain


def ensure_allowed_email_domain(email: str, allowed_domains: Sequence[str]) -> str:
    """Accept only an exact domain match; subdomains are not implied."""
    domain = email_domain(email)
    allowed = {candidate.strip().lower() for candidate in allowed_domains}
    if domain not in allowed:
        raise RuleViolation("Email address domain is not allowed")
    return normalize_email(email)


def validate_full_name(value: str) -> str:
    trimmed = value.strip()
    if not FULL_NAME_MIN <= len(trimmed) <= FULL_NAME_MAX:
        raise RuleViolation(f"Full name must be {FULL_NAME_MIN}-{FULL_NAME_MAX} characters")
    return trimmed


def validate_reason(value: str) -> str:
    trimmed = value.strip()
    if not REASON_MIN <= len(trimmed) <= REASON_MAX:
        raise RuleViolation(f"Reason must be {REASON_MIN}-{REASON_MAX} characters")
    return trimmed


def validate_password(password: str) -> str:
    """Bound by character count only; never trim or normalize the password."""
    if not PASSWORD_MIN_CHARS <= len(password) <= PASSWORD_MAX_CHARS:
        raise RuleViolation(
            f"Password must be {PASSWORD_MIN_CHARS}-{PASSWORD_MAX_CHARS} characters"
        )
    return password


def parse_roles(roles: Sequence[str]) -> list[EmployeeRole]:
    parsed: list[EmployeeRole] = []
    for role in roles:
        try:
            parsed.append(EmployeeRole(role))
        except ValueError as exc:
            raise RuleViolation(f"Unknown employee role: {role}") from exc
    if len(set(parsed)) != len(parsed):
        raise RuleViolation("Employee roles must not repeat")
    return parsed


def validate_employee_roles(roles: Sequence[str]) -> list[EmployeeRole]:
    parsed = parse_roles(roles)
    if not parsed:
        raise RuleViolation("An employee account requires at least one role")
    if PROBATION_ROLE in parsed and len(parsed) > 1:
        raise RuleViolation("PROBATION must be the only employee role when present")
    return parsed


def validate_account_roles(
    account_type: AccountType | str, roles: Sequence[str]
) -> list[EmployeeRole]:
    if AccountType(account_type) is AccountType.ADMIN:
        if roles:
            raise RuleViolation("Admin accounts cannot carry employee roles")
        return []
    return validate_employee_roles(roles)


def validate_page_size(limit: int) -> int:
    if not PAGE_SIZE_MIN <= limit <= PAGE_SIZE_MAX:
        raise RuleViolation(f"Page size must be {PAGE_SIZE_MIN}-{PAGE_SIZE_MAX}")
    return limit
