from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from app.models.evidence import EvidenceRecord


class EmailRecord(BaseModel):
    value: str
    verified: bool = False
    source_url: Optional[str] = None
    source_type: Optional[str] = None


class PhoneRecord(BaseModel):
    value: str
    raw_value: Optional[str] = None
    source_url: Optional[str] = None
    source_type: Optional[str] = None


class ServiceOpportunity(BaseModel):
    """A detected opportunity for a specific service based on observable public signals."""
    service: str            # normalized key e.g. 'seo', 'social_media', 'branding'
    service_display: str    # human-readable e.g. 'SEO', 'Social Media'
    confidence: str         # 'high', 'medium', 'low'
    signals: List[str] = Field(default_factory=list)   # observable signals detected
    evidence: List[str] = Field(default_factory=list)  # source URLs
    reason: str = ""        # concise human-readable reason


class IntentEvidence(BaseModel):
    """Evidence that a business publicly expressed need for a service."""
    source_url: str
    text: str               # the snippet showing intent
    source_type: str        # 'public_web', 'forum', 'social', 'job_board'
    confidence: str = "medium"   # 'high', 'medium', 'low'


class CandidateBusiness(BaseModel):
    name: Optional[str] = None
    normalized_name: Optional[str] = None
    website: Optional[str] = None
    domain: Optional[str] = None
    industry: Optional[str] = None
    services: List[str] = Field(default_factory=list)   # target business's own services
    description: Optional[str] = None
    about: Optional[str] = None   # concise user-facing description (max ~200 chars)
    phone_numbers: List[PhoneRecord] = Field(default_factory=list)
    emails: List[EmailRecord] = Field(default_factory=list)
    address: Optional[str] = None
    social_profiles: Dict[str, Optional[str]] = Field(default_factory=dict)
    locations: List[str] = Field(default_factory=list)
    sources: List[str] = Field(default_factory=list)
    evidence: List[EvidenceRecord] = Field(default_factory=list)
    raw_metadata: Dict[str, Any] = Field(default_factory=dict)
    is_historical: bool = False
    is_directory: bool = False   # True if domain is an aggregator/directory
    discovery_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Lead Classification Fields
    lead_type: Optional[str] = None    # 'explicit_intent', 'opportunity', 'explicit_and_opportunity'
    service_opportunities: List[ServiceOpportunity] = Field(default_factory=list)
    service_requested: Optional[str] = None   # for explicit_intent leads
    intent_confidence: Optional[str] = None   # 'high', 'medium', 'low'
    intent_evidence: Optional[IntentEvidence] = None
    short_reason: Optional[str] = None        # brief human-readable sales reason

    def add_evidence(
        self,
        field_name: str,
        value: Any,
        source_type: str,
        source_url: Optional[str] = None,
        confidence: float = 1.0,
        context_snippet: Optional[str] = None
    ):
        if source_type not in self.sources:
            self.sources.append(source_type)
        self.evidence.append(
            EvidenceRecord(
                field_name=field_name,
                value=value,
                source_type=source_type,
                source_url=source_url,
                confidence=confidence,
                context_snippet=context_snippet
            )
        )

    def generate_about(self) -> str:
        """Generate a concise about field from description."""
        raw = self.description or ""
        raw = raw.strip()
        if len(raw) > 200:
            raw = raw[:197] + "..."
        return raw

    def primary_phone(self) -> Optional[str]:
        """Return the best phone number."""
        return self.phone_numbers[0].value if self.phone_numbers else None

    def primary_email(self) -> Optional[str]:
        """Return the best email."""
        return self.emails[0].value if self.emails else None

    def primary_location(self) -> Optional[str]:
        """Return the primary discovered location."""
        return self.locations[0] if self.locations else None
