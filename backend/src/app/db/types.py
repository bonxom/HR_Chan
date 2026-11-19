"""Custom column types shared by ORM models."""

from sqlalchemy.dialects.postgresql.base import ischema_names
from sqlalchemy.types import UserDefinedType


class CIText(UserDefinedType):
    """PostgreSQL ``citext`` (case-insensitive text) used for email columns of context 02."""

    cache_ok = True

    def get_col_spec(self, **kw) -> str:
        return "CITEXT"


# Reflection (alembic check) recognizes the column instead of reporting NullType.
ischema_names.setdefault("citext", CIText)
