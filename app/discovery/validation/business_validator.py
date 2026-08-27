import re
from typing import Optional, List, Set
from urllib.parse import urlparse
from dataclasses import dataclass
from app.models.candidate import CandidateBusiness
from app.schemas.discovery_request import DiscoveryRequest


# Known directory/aggregator domains that are sources, NOT business leads.
# These should NEVER appear as the company in a final lead.
DIRECTORY_DOMAINS: Set[str] = {
    # Healthcare / Medical
    "practo.com", "lybrate.com", "whatclinic.com", "healthgrades.com",
    "zocdoc.com", "doctorondemand.com", "1mg.com",
    # Local business directories
    "justdial.com", "sulekha.com", "asklaila.com", "indiamart.com",
    "tradeindia.com", "yellowpages.com", "yellowpages.in",
    "magicpin.in", "magicpin.com",
    # Review & discovery platforms
    "yelp.com", "tripadvisor.com", "zomato.com", "swiggy.com",
    "urbanclap.com", "urbancompany.com", "housejoy.in",
    # Jobs & professional
    "ambitionbox.com", "glassdoor.com", "indeed.com", "naukri.com",
    "linkedin.com",  # LinkedIn company pages are sources
    # E-commerce aggregators
    "amazon.com", "flipkart.com", "snapdeal.com",
    # General knowledge / media
    "wikipedia.org", "youtube.com", "facebook.com",
    "instagram.com", "twitter.com", "x.com", "reddit.com",
    "pinterest.com", "quora.com", "scribd.com",
    # Search engines
    "google.com", "bing.com", "duckduckgo.com", "yahoo.com",
    # Travel
    "makemytrip.com", "booking.com", "airbnb.com",
    # News / content
    "medium.com", "wordpress.com", "blogspot.com",
    # Social media tools
    "linktree.com", "linkin.bio",
}


@dataclass
class ValidationResult:
    is_valid: bool
    rejection_reason: Optional[str] = None
    warnings: List[str] = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


class BusinessValidator:
    """
    Validates that a discovered candidate represents a genuine, identifiable
    business entity that matches the discovery request criteria.

    Validation stages:
    1. Name plausibility (not a generic term, not the directory name)
    2. Directory/source detection (aggregator domains are rejected)
    3. Target industry relevance
    4. Location validation
    5. Contactability and minimum identity quality
    """

    def validate(
        self,
        candidate: CandidateBusiness,
        request: DiscoveryRequest,
    ) -> ValidationResult:
        """
        Validate a candidate business against the discovery request.
        Returns ValidationResult indicating whether the candidate is a valid lead.
        """
        warnings: List[str] = []

        # Stage 1: Directory / Aggregator Detection
        candidate_domain = candidate.domain or self._domain_from_url(candidate.website)
        if candidate.is_directory or self._is_directory_domain(candidate_domain):
            return ValidationResult(
                is_valid=False,
                rejection_reason=f"Domain '{candidate_domain or 'source record'}' is a directory/aggregator, not a business"
            )

        # Stage 2: Name Plausibility
        name_check = self._validate_name(candidate.name)
        if not name_check.is_valid:
            return name_check

        # A source page or intent snippet is evidence, not the business itself.
        has_name = bool(candidate.name and len(candidate.name.strip()) >= 2)
        if not has_name:
            return ValidationResult(
                is_valid=False,
                rejection_reason="Candidate has no identifiable business name"
            )

        # Stage 3: Identity and contactability
        has_identity_contact = bool(
            candidate.website
            or candidate.phone_numbers
            or candidate.emails
            or any(candidate.social_profiles.values())
        )
        if not has_identity_contact:
            return ValidationResult(
                is_valid=False,
                rejection_reason="Candidate has no usable public contact path"
            )

        # Stage 4: Target Industry Relevance
        if candidate.name and request.target:
            relevance = self._check_industry_relevance(
                candidate,
                request.target.industry,
                request.target.keywords,
            )
            if relevance.rejection_reason:
                return relevance

        # Stage 5: Location Validation. Missing location evidence is not a match.
        if request.locations:
            candidate_locations = list(candidate.locations)
            if candidate.address:
                candidate_locations.append(candidate.address)
            if not candidate_locations:
                return ValidationResult(
                    is_valid=False,
                    rejection_reason="Candidate has no business-specific location evidence"
                )
            location_ok = self._check_location(candidate_locations, request.locations)
            if not location_ok:
                return ValidationResult(
                    is_valid=False,
                    rejection_reason="Candidate location does not match any requested location"
                )

        # Stage 6: Must-Have field check (from Requirements)
        if request.requirements and request.requirements.must_have:
            must_have_check = self._check_must_have(candidate, request.requirements.must_have)
            if not must_have_check.is_valid:
                return must_have_check

        # Stage 7: Exclusion keywords
        if request.requirements and request.requirements.exclude:
            exclude_check = self._check_exclusions(candidate, request.requirements.exclude)
            if not exclude_check.is_valid:
                return exclude_check

        return ValidationResult(is_valid=True, warnings=warnings)

    def _is_directory_domain(self, domain: str) -> bool:
        """Check if a domain is a known directory/aggregator."""
        if not domain:
            return False
        domain_lower = domain.lower().strip()
        # Direct match
        if domain_lower in DIRECTORY_DOMAINS:
            return True
        # Subdomain match (e.g. "bangalore.justdial.com")
        for dir_domain in DIRECTORY_DOMAINS:
            if domain_lower.endswith("." + dir_domain):
                return True
        return False

    def _domain_from_url(self, website: Optional[str]) -> str:
        if not website:
            return ""
        try:
            return (urlparse(website).hostname or "").lower().removeprefix("www.")
        except ValueError:
            return ""

    def _name_matches_directory(self, name: str, domain: str) -> bool:
        """Check if the candidate name appears to be the directory site name itself."""
        if not name or not domain:
            return False
        name_lower = name.lower().strip()
        domain_root = domain.split(".")[0].lower() if "." in domain else domain.lower()

        # Check if name IS the directory
        directory_names = {
            "practo", "magicpin", "justdial", "sulekha", "lybrate", "indiamart",
            "tradeindia", "yellowpages", "yelp", "tripadvisor", "zomato",
            "swiggy", "urbanclap", "urbancompany", "linkedin", "facebook",
            "instagram", "twitter", "youtube", "wikipedia", "scribd"
        }
        return domain_root in directory_names and domain_root in name_lower

    def _validate_name(self, name: Optional[str]) -> ValidationResult:
        """Validate business name plausibility."""
        if not name:
            # No name is acceptable if there's other data — this is the incomplete lead rule
            return ValidationResult(is_valid=True)

        name_stripped = name.strip()

        # Too short
        if len(name_stripped) < 2:
            return ValidationResult(
                is_valid=False,
                rejection_reason=f"Business name too short: '{name_stripped}'"
            )

        # Generic/non-business names
        generic_terms = {
            "home", "index", "results", "search results", "loading",
            "error", "404", "page not found", "untitled", "website",
        }
        if name_stripped.lower() in generic_terms:
            return ValidationResult(
                is_valid=False,
                rejection_reason=f"Business name appears to be a generic page element: '{name_stripped}'"
            )

        listing_title = re.match(
            r"^(?:(?:best|top|all|find|list(?:ing)?|search)\s+)?"
            r"(?:dental\s+clinics?|dentists?|medical\s+clinics?|hospitals?|"
            r"restaurants?|salons?|lawyers?)\s+in\s+.+$",
            name_stripped,
            re.IGNORECASE,
        )
        if listing_title:
            return ValidationResult(
                is_valid=False,
                rejection_reason=f"Business name appears to be a listing title: '{name_stripped}'",
            )

        return ValidationResult(is_valid=True)

    def _check_industry_relevance(
        self,
        candidate: CandidateBusiness,
        industry: str,
        keywords: List[str],
    ) -> ValidationResult:
        """
        Check if the candidate appears to be in the target industry.
        Relevance is hard eligibility for final leads. A source title mentioning
        the target is insufficient without matching business-specific text.
        """
        if not industry:
            return ValidationResult(is_valid=True)

        # Build searchable text from candidate
        text_to_check = " ".join(filter(None, [
            candidate.name or "",
            candidate.description or "",
            candidate.industry or "",
            " ".join(candidate.services),
        ])).lower()

        industry_lower = industry.lower()
        check_terms = [industry_lower] + [k.lower() for k in (keywords or [])]

        # Remove very common/short words and compare meaningful industry tokens.
        stop_words = {"in", "the", "and", "or", "a", "an", "of", "for", "with", "at"}
        relevant_terms = {
            token.rstrip("s")
            for term in check_terms
            for token in re.findall(r"[a-z0-9]+", term)
            if token not in stop_words and len(token) >= 4
        }

        if relevant_terms:
            found = any(
                term in text_to_check
                for term in relevant_terms
            )
            if not found:
                return ValidationResult(
                    is_valid=False,
                    rejection_reason="Industry keywords are not present in business-specific data"
                )

        return ValidationResult(is_valid=True)

    def _check_location(
        self,
        candidate_locations: List[str],
        requested_locations: List[str],
    ) -> bool:
        """Check if candidate location overlaps with any requested location."""
        if not candidate_locations or not requested_locations:
            return True  # Can't check — assume OK

        candidate_loc_text = " ".join(candidate_locations).lower()
        for req_loc in requested_locations:
            if req_loc.lower() in candidate_loc_text:
                return True
        return False

    def _check_must_have(
        self,
        candidate: CandidateBusiness,
        must_have: List[str],
    ) -> ValidationResult:
        """Check eligibility requirements (must_have). ONLY these can disqualify."""
        for req in must_have:
            req_lower = req.lower().strip()
            if req_lower == "website" and not candidate.website:
                return ValidationResult(
                    is_valid=False,
                    rejection_reason="Required field 'website' is missing"
                )
            elif req_lower in ("phone", "phone_number") and not candidate.phone_numbers:
                return ValidationResult(
                    is_valid=False,
                    rejection_reason="Required field 'phone' is missing"
                )
            elif req_lower == "email" and not candidate.emails:
                return ValidationResult(
                    is_valid=False,
                    rejection_reason="Required field 'email' is missing"
                )
            elif req_lower == "address" and not candidate.address:
                return ValidationResult(
                    is_valid=False,
                    rejection_reason="Required field 'address' is missing"
                )
            elif req_lower == "instagram" and not candidate.social_profiles.get("instagram"):
                return ValidationResult(
                    is_valid=False,
                    rejection_reason="Required field 'instagram' is missing"
                )
            elif req_lower == "linkedin" and not candidate.social_profiles.get("linkedin"):
                return ValidationResult(
                    is_valid=False,
                    rejection_reason="Required field 'linkedin' is missing"
                )
        return ValidationResult(is_valid=True)

    def _check_exclusions(
        self,
        candidate: CandidateBusiness,
        exclude_keywords: List[str],
    ) -> ValidationResult:
        """Check if candidate matches any exclusion keywords."""
        text_to_check = " ".join(filter(None, [
            candidate.name or "",
            candidate.description or "",
            candidate.industry or "",
        ])).lower()

        for exc in exclude_keywords:
            exc_lower = exc.lower().strip()
            if exc_lower and exc_lower in text_to_check:
                return ValidationResult(
                    is_valid=False,
                    rejection_reason=f"Candidate matches exclusion keyword: '{exc}'"
                )
        return ValidationResult(is_valid=True)
