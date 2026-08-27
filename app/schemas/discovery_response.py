from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from app.schemas.candidate import DiscoveredLeadOutput
from app.models.rejection import RejectionRecord


class DiscoveryJobStatus(BaseModel):
    job_id: str
    status: str  # pending, running, completed, completed_partial, failed
    created_at: datetime
    completed_at: Optional[datetime] = None
    total_queries: int = 0
    total_candidates: int = 0
    raw_candidates: int = 0
    candidates_checked: int = 0
    accepted_leads: int = 0
    rejected_candidates: int = 0
    duplicates: int = 0
    error_count: int = 0
    unique_businesses: int = 0
    pages_crawled: int = 0
    errors: List[Dict[str, Any]] = Field(default_factory=list)
    source_stats: Dict[str, Any] = Field(default_factory=dict)


class DiscoveryJobResponse(BaseModel):
    job_id: str
    status: str
    message: str


class DiscoveryResultResponse(BaseModel):
    job_id: str
    status: str
    total_candidates: int
    unique_businesses: int
    results: List[DiscoveredLeadOutput]


class DiscoveryRejectionResponse(BaseModel):
    rejection_id: str
    job_id: Optional[str] = None
    candidate_name: Optional[str] = None
    candidate_url: Optional[str] = None
    reason_code: str
    reason_detail: str
    stage: str
    source: Optional[str] = None
    timestamp: datetime


class DiscoveryRejectionsResponse(BaseModel):
    job_id: str
    total_rejected: int
    rejections: List[DiscoveryRejectionResponse]
