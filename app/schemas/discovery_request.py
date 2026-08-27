from typing import List, Optional
from pydantic import BaseModel, Field


class TargetBusiness(BaseModel):
    industry: str = Field(..., description="Target industry (e.g. 'Dental clinics')")
    services: List[str] = Field(default_factory=list, description="Target services (e.g. ['dental implants', 'cosmetic dentistry'])")
    keywords: List[str] = Field(default_factory=list, description="Keywords (e.g. ['dentist', 'dental clinic'])")


class Requirements(BaseModel):
    must_have: List[str] = Field(
        default_factory=list,
        description="Eligibility constraints. Candidates missing these will be excluded (e.g. ['website'])."
    )
    preferred: List[str] = Field(
        default_factory=list,
        description="Desired fields to prioritize (e.g. ['instagram', 'email'])."
    )
    exclude: List[str] = Field(
        default_factory=list,
        description="Exclusion keywords (e.g. ['hospitals', 'government clinics'])."
    )


class DiscoverySettings(BaseModel):
    target_leads: int = Field(default=20, ge=1, le=5000, description="Number of final validated contactable leads requested")
    max_candidates_checked: int = Field(default=250, ge=1, le=50000)
    max_search_queries: int = Field(default=100, ge=1, le=10000)
    max_runtime_minutes: float = Field(default=10, gt=0, le=240)
    language: str = Field(default="en", description="Language code")
    discovery_depth: str = Field(default="standard", description="standard, shallow, deep")
    enable_historical: bool = Field(default=False, description="Enable historical archive lookups")
    enable_playwright_fallback: bool = Field(default=True, description="Enable Playwright dynamic JS rendering fallback")

    @property
    def max_results(self) -> int:
        """Compatibility accessor for older internal callers."""
        return self.target_leads


class DiscoveryRequest(BaseModel):
    target: TargetBusiness
    locations: List[str] = Field(..., min_length=1, description="Target locations (cities, regions, areas)")
    lead_objective: Optional[str] = Field(
        default=None,
        description="Natural language objective (e.g. 'Find businesses that may need a new website')"
    )
    services_offered: List[str] = Field(
        default_factory=list,
        description="Services WE SELL (e.g. ['SEO', 'Branding', 'Social Media', 'Website Design']). Used for opportunity detection and explicit intent discovery."
    )
    requirements: Requirements = Field(default_factory=Requirements)
    collect: List[str] = Field(
        default_factory=lambda: [
            "business_name",
            "website",
            "phone",
            "email",
            "address",
            "instagram",
            "facebook",
            "linkedin",
            "services",
            "description"
        ],
        description="Fields we attempt to extract. Missing fields are preserved as null/empty without disqualifying candidates."
    )
    settings: DiscoverySettings = Field(default_factory=DiscoverySettings)
