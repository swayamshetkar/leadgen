from app.discovery.ai.provider import AIValidationProvider, DeterministicValidationProvider
from app.discovery.ai.schemas import CandidateValidationInput, AIValidationResult
from app.models.candidate import CandidateBusiness
from app.schemas.discovery_request import DiscoveryRequest


class AICandidateValidator:
    def __init__(self, provider: AIValidationProvider | None = None):
        self.provider = provider or DeterministicValidationProvider()

    def _input(self, candidate: CandidateBusiness, request: DiscoveryRequest) -> CandidateValidationInput:
        return CandidateValidationInput(
            name=candidate.name or "",
            industry=" ".join([request.target.industry, *request.target.keywords]),
            location=" ".join([*candidate.locations, candidate.address or ""]),
            requested_locations=request.locations,
            website=candidate.website or "",
            phone=candidate.primary_phone() or "",
            email=candidate.primary_email() or "",
            social_profiles={k: v for k, v in candidate.social_profiles.items() if v},
            description=candidate.description or candidate.about or "",
        )

    async def validate_identity(self, candidate: CandidateBusiness, request: DiscoveryRequest) -> AIValidationResult:
        return await self.provider.validate(self._input(candidate, request), 1)

    async def validate_final(self, candidate: CandidateBusiness, request: DiscoveryRequest) -> AIValidationResult:
        return await self.provider.validate(self._input(candidate, request), 2)