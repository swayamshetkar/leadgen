from typing import Generic, TypeVar, Optional, Any
from datetime import datetime, timezone
from pydantic import BaseModel, Field

T = TypeVar("T")


class EvidenceRecord(BaseModel):
    """
    Provenance tracking for any field or discovery discovery step.
    """
    field_name: str
    value: Any
    source_type: str  # e.g., 'search', 'osm_maps', 'instagram', 'website_jsonld', 'website_html', 'wayback'
    source_url: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    context_snippet: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class EvidenceField(BaseModel, Generic[T]):
    """
    Wrapper for a data value with associated provenance evidence.
    """
    value: T
    source_type: str
    source_url: Optional[str] = None
    confidence: float = 1.0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
