"""Candidate submission DTOs."""

from datetime import datetime

from pydantic import BaseModel


class SubmissionOut(BaseModel):
    """Result of an accepted CV upload; never contains a storage key, path or URL."""

    submission_id: int
    submission_token: str
    expires_at: datetime
