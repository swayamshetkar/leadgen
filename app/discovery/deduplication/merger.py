from typing import List, Dict, Optional, Set
from app.models.candidate import CandidateBusiness, EmailRecord, PhoneRecord
from app.models.evidence import EvidenceRecord
from app.schemas.discovery_request import Requirements
from app.discovery.deduplication.matcher import CandidateMatcher
from app.discovery.normalization.business import BusinessNormalizer
from app.discovery.validation.business_validator import BusinessValidator


class CandidateMerger:
    """
    Groups, merges, and validates discovered candidates into unified business leads.
    Preserves all provenance evidence and enforces incomplete-lead tolerance.
    """
    def __init__(self):
        self.matcher = CandidateMatcher()
        self.validator = BusinessValidator()

    def merge_candidates(
        self,
        candidates: List[CandidateBusiness],
        requirements: Optional[Requirements] = None,
        request=None,
    ) -> List[CandidateBusiness]:
        if not candidates:
            return []

        # Reject weak source records before clustering so they cannot contribute
        # contacts or identity data to an otherwise valid business.
        if request:
            candidates = [
                candidate for candidate in candidates
                if self.validator.validate(candidate, request).is_valid
            ]
        elif requirements:
            candidates = [candidate for candidate in candidates if self._is_eligible(candidate, requirements)]

        if not candidates:
            return []

        # 1. Cluster candidates by identity
        clusters: List[List[CandidateBusiness]] = []
        for cand in candidates:
            matched = False
            for cluster in clusters:
                if any(self.matcher.is_match(cand, existing) for existing in cluster):
                    cluster.append(cand)
                    matched = True
                    break
            if not matched:
                clusters.append([cand])

        # 2. Merge each cluster into a single canonical record
        merged_leads: List[CandidateBusiness] = []
        for cluster in clusters:
            merged = self._merge_cluster(cluster)
            
            # 3. Apply eligibility requirements and final business validation
            if request:
                validation = self.validator.validate(merged, request)
                is_valid = validation.is_valid
            else:
                is_valid = self._is_eligible(merged, requirements)

            if is_valid:
                merged_leads.append(merged)

        return merged_leads

    def _merge_cluster(self, cluster: List[CandidateBusiness]) -> CandidateBusiness:
        if len(cluster) == 1:
            return cluster[0]

        # Determine best business name (prefer non-search / longer / cleaned names)
        names = [c.name for c in cluster if c.name]
        best_name = names[0] if names else None
        for n in names:
            # Prefer names that are not just root domains or handles
            if not n.startswith("@") and "." not in n:
                best_name = n
                break

        # Best website and domain
        best_website = next((c.website for c in cluster if c.website), None)
        best_domain = next((c.domain for c in cluster if c.domain), None)

        # Best address
        best_address = next((c.address for c in cluster if c.address), None)

        # Best description
        descriptions = [c.description for c in cluster if c.description]
        best_desc = max(descriptions, key=len) if descriptions else None
        abouts = [c.about for c in cluster if c.about]
        best_about = max(abouts, key=len) if abouts else None

        # Best industry
        industry = next((c.industry for c in cluster if c.industry), None)

        # Combine emails (deduplicate by lowercase value)
        seen_emails: Set[str] = set()
        merged_emails: List[EmailRecord] = []
        for c in cluster:
            for em in c.emails:
                val_lower = em.value.strip().lower()
                if val_lower and val_lower not in seen_emails:
                    seen_emails.add(val_lower)
                    merged_emails.append(em)

        # Combine phones (deduplicate by digits)
        seen_phones: Set[str] = set()
        merged_phones: List[PhoneRecord] = []
        for c in cluster:
            for ph in c.phone_numbers:
                val = ph.value.strip()
                if val and val not in seen_phones:
                    seen_phones.add(val)
                    merged_phones.append(ph)

        # Combine social profiles
        merged_socials: Dict[str, Optional[str]] = {}
        for c in cluster:
            for plat, link in c.social_profiles.items():
                if link and (plat not in merged_socials or not merged_socials[plat]):
                    merged_socials[plat] = link

        # Combine services
        seen_services: Set[str] = set()
        merged_services: List[str] = []
        for c in cluster:
            for s in c.services:
                s_clean = s.strip()
                if s_clean and s_clean.lower() not in seen_services:
                    seen_services.add(s_clean.lower())
                    merged_services.append(s_clean)

        # Combine locations
        seen_locs: Set[str] = set()
        merged_locations: List[str] = []
        for c in cluster:
            for l in c.locations:
                l_clean = l.strip()
                if l_clean and l_clean.lower() not in seen_locs:
                    seen_locs.add(l_clean.lower())
                    merged_locations.append(l_clean)

        # Combine sources
        merged_sources: List[str] = []
        for c in cluster:
            for src in c.sources:
                if src not in merged_sources:
                    merged_sources.append(src)

        # Combine evidence
        merged_evidence: List[EvidenceRecord] = []
        for c in cluster:
            merged_evidence.extend(c.evidence)

        # Check if any is historical
        is_historical = any(c.is_historical for c in cluster)
        is_directory = any(c.is_directory for c in cluster)

        lead_type = self._merge_lead_type(cluster)
        service_opportunities = self._merge_service_opportunities(cluster)
        intent_candidate = next((c for c in cluster if c.intent_evidence), None)
        short_reason = next((c.short_reason for c in cluster if c.short_reason), None)
        service_requested = next((c.service_requested for c in cluster if c.service_requested), None)
        intent_confidence = next((c.intent_confidence for c in cluster if c.intent_confidence), None)

        merged_candidate = CandidateBusiness(
            name=best_name,
            normalized_name=BusinessNormalizer.normalize_name(best_name),
            website=best_website,
            domain=best_domain,
            industry=industry,
            services=merged_services,
            description=best_desc,
            about=best_about,
            phone_numbers=merged_phones,
            emails=merged_emails,
            address=best_address,
            social_profiles=merged_socials,
            locations=merged_locations,
            sources=merged_sources,
            evidence=merged_evidence,
            is_historical=is_historical,
            is_directory=is_directory,
            lead_type=lead_type,
            service_opportunities=service_opportunities,
            service_requested=service_requested,
            intent_confidence=intent_confidence,
            intent_evidence=intent_candidate.intent_evidence if intent_candidate else None,
            short_reason=short_reason,
        )

        return merged_candidate

    def _merge_lead_type(self, cluster: List[CandidateBusiness]) -> Optional[str]:
        has_intent = any(c.lead_type in ("explicit_intent", "explicit_and_opportunity") or c.intent_evidence for c in cluster)
        has_opportunity = any(
            c.lead_type in ("opportunity", "explicit_and_opportunity") or c.service_opportunities
            for c in cluster
        )
        if has_intent and has_opportunity:
            return "explicit_and_opportunity"
        if has_intent:
            return "explicit_intent"
        if has_opportunity:
            return "opportunity"
        return None

    def _merge_service_opportunities(self, cluster: List[CandidateBusiness]):
        by_service = {}
        order = {"high": 0, "medium": 1, "low": 2}
        for c in cluster:
            for opp in c.service_opportunities:
                current = by_service.get(opp.service)
                if not current or order.get(opp.confidence, 3) < order.get(current.confidence, 3):
                    by_service[opp.service] = opp
        return sorted(by_service.values(), key=lambda o: order.get(o.confidence, 3))

    def _is_eligible(self, lead: CandidateBusiness, requirements: Optional[Requirements]) -> bool:
        if not requirements:
            return True

        # Check Must-Have constraints (ONLY these determine eligibility)
        for req in requirements.must_have:
            req_lower = req.lower().strip()
            if req_lower == "website" and not lead.website:
                return False
            elif req_lower in ("phone", "phone_number") and not lead.phone_numbers:
                return False
            elif req_lower == "email" and not lead.emails:
                return False
            elif req_lower == "address" and not lead.address:
                return False
            elif req_lower == "instagram" and not lead.social_profiles.get("instagram"):
                return False
            elif req_lower == "linkedin" and not lead.social_profiles.get("linkedin"):
                return False
            elif req_lower == "facebook" and not lead.social_profiles.get("facebook"):
                return False

        # Check Exclude keywords
        for exc in requirements.exclude:
            exc_lower = exc.lower().strip()
            if exc_lower:
                name_text = (lead.name or "").lower()
                desc_text = (lead.description or "").lower()
                if exc_lower in name_text or exc_lower in desc_text:
                    return False

        return True
