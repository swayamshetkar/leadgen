from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field


class RejectionRecord(BaseModel):
    rejection_id: Optional[str] = None
    job_id: Optional[str] = None
    candidate_name: Optional[str] = None
    candidate_url: Optional[str] = None
    reason_code: str
    reason_detail: str
    stage: str
    source: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))