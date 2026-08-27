from typing import List
from pydantic import BaseModel, Field


class AIValidationResult(BaseModel):
    is_real_business: bool = False
    name_is_business: bool = False
    is_source_page: bool = False
    matches_industry: bool = False
    matches_location: bool = False
    website_belongs_to_business: bool = False
    contacts_belong_to_business: bool = False
    is_contactable: bool = False
    is_plausible_prospect: bool = False
    reasons: List[str] = Field(default_factory=list)


class CandidateValidationInput(BaseModel):
    name: str
    industry: str = ""
    location: str = ""
    requested_locations: List[str] = Field(default_factory=list)
    website: str = ""
    phone: str = ""
    email: str = ""
    social_profiles: dict[str, str] = Field(default_factory=dict)
    description: str = ""