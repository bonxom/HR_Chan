import itertools

import pytest

from app.modules.accounts.rules import (
    AccountType,
    EmployeeRole,
    RuleViolation,
    ensure_allowed_email_domain,
    normalize_email,
    validate_account_roles,
    validate_employee_roles,
    validate_full_name,
    validate_page_size,
    validate_password,
    validate_reason,
)


def _combined_role_sets() -> list[list[str]]:
    combinable = [EmployeeRole.HR, EmployeeRole.INTERVIEWER, EmployeeRole.DEPT_MANAGER]
    sets: list[list[str]] = []
    for size in range(1, len(combinable) + 1):
        for combination in itertools.combinations(combinable, size):
            sets.append([role.value for role in combination])
    return sets


@pytest.mark.parametrize("roles", _combined_role_sets())
def test_accepts_nonempty_subsets_of_combined_roles(roles: list[str]) -> None:
    assert [role.value for role in validate_employee_roles(roles)] == roles


def test_accepts_probation_alone() -> None:
    assert validate_employee_roles(["PROBATION"]) == [EmployeeRole.PROBATION]


@pytest.mark.parametrize(
    "roles",
    [
        [],
        ["PROBATION", "HR"],
        ["HR", "PROBATION"],
        ["HR", "HR"],
        ["HR", "hr"],
        ["CEO"],
        [""],
    ],
)
def test_rejects_invalid_employee_role_sets(roles: list[str]) -> None:
    with pytest.raises(RuleViolation):
        validate_employee_roles(roles)


def test_admin_accounts_cannot_carry_employee_roles() -> None:
    with pytest.raises(RuleViolation):
        validate_account_roles(AccountType.ADMIN, ["HR"])
    assert validate_account_roles(AccountType.ADMIN, []) == []


def test_employee_accounts_require_roles() -> None:
    with pytest.raises(RuleViolation):
        validate_account_roles(AccountType.EMPLOYEE, [])


@pytest.mark.parametrize(
    ("email", "expected"),
    [
        ("  User.Name@sis.hust.edu.vn  ", "user.name@sis.hust.edu.vn"),
        ("USER@SIS.HUST.EDU.VN", "user@sis.hust.edu.vn"),
    ],
)
def test_normalizes_email_case_and_whitespace(email: str, expected: str) -> None:
    assert normalize_email(email) == expected


@pytest.mark.parametrize(
    "email",
    [
        "user@sis.hust.edu.vn",
        "user@SIS.hust.edu.vn",
        "user.name+tag@sis.hust.edu.vn",
    ],
)
def test_accepts_only_exact_allowed_domain(email: str) -> None:
    assert ensure_allowed_email_domain(email, ["sis.hust.edu.vn"]) == normalize_email(email)


@pytest.mark.parametrize(
    "email",
    [
        "user@gmail.com",
        "user@sub.sis.hust.edu.vn",
        "user@sis.hust.edu.vn.evil.com",
        "user@evil-sis.hust.edu.vn",
        "user@sis.hust.edu",
        "no-domain",
    ],
)
def test_rejects_other_domains_and_subdomains(email: str) -> None:
    with pytest.raises(RuleViolation):
        ensure_allowed_email_domain(email, ["sis.hust.edu.vn"])


@pytest.mark.parametrize("length", [8, 9, 128])
def test_accepts_password_character_bounds(length: int) -> None:
    password = "a" * length
    assert validate_password(password) == password


@pytest.mark.parametrize("length", [0, 7, 129])
def test_rejects_password_character_bounds(length: int) -> None:
    with pytest.raises(RuleViolation):
        validate_password("a" * length)


def test_preserves_password_characters_without_normalization() -> None:
    password = "  mật khẩu có dấu cách  "
    assert validate_password(password) == password
    assert validate_password("é" * 8) == "é" * 8


def test_full_name_is_trimmed_and_bounded() -> None:
    assert validate_full_name("  Nguyễn Văn A  ") == "Nguyễn Văn A"
    with pytest.raises(RuleViolation):
        validate_full_name("   ")
    with pytest.raises(RuleViolation):
        validate_full_name("a" * 201)


def test_reason_is_trimmed_and_bounded() -> None:
    assert validate_reason("  security review ") == "security review"
    with pytest.raises(RuleViolation):
        validate_reason("  ")
    with pytest.raises(RuleViolation):
        validate_reason("a" * 1001)


@pytest.mark.parametrize("limit", [0, 101, -1])
def test_rejects_out_of_range_page_size(limit: int) -> None:
    with pytest.raises(RuleViolation):
        validate_page_size(limit)


@pytest.mark.parametrize("limit", [1, 25, 100])
def test_accepts_page_size_bounds(limit: int) -> None:
    assert validate_page_size(limit) == limit
