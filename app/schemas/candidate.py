from typing import Optional, Dict, List
from pydantic import BaseModel, Field


class ServiceOpportunityOutput(BaseModel):
    service: str
    service_display: str = ""
    confidence: str         # 'high', 'medium', 'low'
    reason: str = ""
    signals: List[str] = Field(default_factory=list)


class DiscoveredLeadOutput(BaseModel):
    """Only the contact fields intended for the public results endpoint."""
    company_name: Optional[str] = None
    company_details: Optional[str] = None
    website: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    contact: Dict[str, Optional[str]] = Field(default_factory=dict)


# Backward-compatible aliases for internal mapping
class EmailOutput(BaseModel):
    value: str
    verified: bool = False
    source: Optional[str] = None


class PhoneOutput(BaseModel):
    value: str
    source: Optional[str] = None
