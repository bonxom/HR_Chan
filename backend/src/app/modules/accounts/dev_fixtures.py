"""Development-only account fixtures shared by the CLI and the dev login route.

These personas are the only identities a development bypass may authenticate as.
"""

from dataclasses import dataclass

from app.modules.accounts.rules import AccountType

DEV_SEED_PASSWORD = "dev-only-password"


@dataclass(frozen=True)
class DevPersona:
    id: str
    email: str
    full_name: str
    account_type: AccountType
    roles: tuple[str, ...]


DEV_PERSONAS: tuple[DevPersona, ...] = (
    DevPersona("admin", "dev.admin@sis.hust.edu.vn", "Dev Administrator", AccountType.ADMIN, ()),
    DevPersona("hr", "dev.hr@sis.hust.edu.vn", "Dev HR", AccountType.EMPLOYEE, ("HR",)),
    DevPersona(
        "interviewer",
        "dev.interviewer@sis.hust.edu.vn",
        "Dev Interviewer",
        AccountType.EMPLOYEE,
        ("INTERVIEWER",),
    ),
    DevPersona(
        "manager",
        "dev.manager@sis.hust.edu.vn",
        "Dev Manager",
        AccountType.EMPLOYEE,
        ("DEPT_MANAGER",),
    ),
    DevPersona(
        "trainee",
        "dev.trainee@sis.hust.edu.vn",
        "Dev Trainee",
        AccountType.EMPLOYEE,
        ("PROBATION",),
    ),
)

DEV_PERSONAS_BY_ID = {persona.id: persona for persona in DEV_PERSONAS}

# Backwards-compatible shape for the seeding command.
DEV_ACCOUNTS = tuple(
    (persona.email, persona.full_name, persona.account_type, persona.roles)
    for persona in DEV_PERSONAS
)
