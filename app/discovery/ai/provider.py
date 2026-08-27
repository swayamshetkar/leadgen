from abc import ABC, abstractmethod
from app.discovery.ai.schemas import CandidateValidationInput, AIValidationResult
from app.utils.text import similarity_ratio


class AIValidationProvider(ABC):
    @abstractmethod
    async def validate(self, candidate: CandidateValidationInput, pass_number: int) -> AIValidationResult:
        raise NotImplementedError


class DeterministicValidationProvider(AIValidationProvider):
    """Offline provider used by default; replaceable with an LLM adapter later."""

    async def validate(self, candidate: CandidateValidationInput, pass_number: int) -> AIValidationResult:
        text = " ".join((candidate.name, candidate.industry, candidate.description)).lower()
        source_markers = ("best ", "top ", " in ", "directory", "listing", "results")
        is_source_page = any(marker in candidate.name.lower() for marker in source_markers)
        matches_industry = any(
            token.rstrip("s") in text
            for token in candidate.industry.lower().split()
            if len(token) >= 4
        )
        has_contact = bool(candidate.website or candidate.phone or candidate.email or candidate.social_profiles)
        has_location = bool(candidate.location) and any(
            location.lower() in candidate.location.lower()
            or similarity_ratio(location, candidate.location) >= 0.65
            for location in candidate.requested_locations
        )
        return AIValidationResult(
            is_real_business=bool(candidate.name.strip()) and not is_source_page,
            name_is_business=bool(candidate.name.strip()) and not is_source_page,
            is_source_page=is_source_page,
            matches_industry=matches_industry,
            matches_location=has_location,
            website_belongs_to_business=bool(candidate.website),
            contacts_belong_to_business=has_contact,
            is_contactable=has_contact,
            is_plausible_prospect=has_contact,
            reasons=[] if has_contact else ["No usable public contact path"],
        )