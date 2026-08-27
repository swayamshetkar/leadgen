from typing import List, Dict, Set, Optional
from dataclasses import dataclass
from app.schemas.discovery_request import DiscoveryRequest
from app.discovery.opportunities.service_profiles import (
    INTENT_MODIFIERS,
    get_primary_keywords_for_service,
    normalize_service_name,
)


@dataclass
class GeneratedQuery:
    query: str
    family: str  # 'basic', 'service', 'contact', 'intent', 'dork', 'social_dork'
    location: str
    target_intent: str
    query_type: str = "business_discovery"  # 'business_discovery' | 'explicit_intent' | 'industry_intent'
    service: Optional[str] = None
    intent_type: Optional[str] = None


class QueryGenerator:
    """
    Multi-family query expansion engine.
    Generates tailored, high-intent discovery search queries across all locations.
    """

    def generate_queries(self, request: DiscoveryRequest) -> List[GeneratedQuery]:
        queries: List[GeneratedQuery] = []
        seen_queries: Set[str] = set()

        target = request.target
        locations = request.locations
        industry = target.industry.strip()
        keywords = [k.strip() for k in target.keywords if k.strip()]
        services = [s.strip() for s in target.services if s.strip()]
        objective = request.lead_objective.strip() if request.lead_objective else None

        # Build base subject terms
        subject_terms = [industry]
        for kw in keywords:
            if kw.lower() != industry.lower() and kw not in subject_terms:
                subject_terms.append(kw)

        for loc in locations:
            loc_clean = loc.strip()
            if not loc_clean:
                continue

            # 1. Basic Query Family
            for term in subject_terms:
                self._add_query(
                    queries, seen_queries,
                    f"{term} {loc_clean}",
                    family="basic", location=loc_clean, intent=f"Basic lookup for {term}"
                )
                self._add_query(
                    queries, seen_queries,
                    f"best {term} in {loc_clean}",
                    family="basic", location=loc_clean, intent=f"Best rated {term}"
                )

            # 2. Service-Specific Query Family
            for service in services:
                self._add_query(
                    queries, seen_queries,
                    f"{service} {loc_clean}",
                    family="service", location=loc_clean, intent=f"Service search for {service}"
                )
                for term in subject_terms[:2]:
                    self._add_query(
                        queries, seen_queries,
                        f"{term} {service} {loc_clean}",
                        family="service", location=loc_clean, intent=f"{term} providing {service}"
                    )

            # 3. Contact-Oriented Query Family
            contact_suffixes = ["contact", "phone number", "email", "address", "website"]
            for term in subject_terms[:2]:
                for suffix in contact_suffixes:
                    self._add_query(
                        queries, seen_queries,
                        f"{term} {loc_clean} {suffix}",
                        family="contact", location=loc_clean, intent=f"Contact lookup: {suffix}"
                    )

            # 4. Objective & Business Intent Family
            if objective:
                obj_lower = objective.lower()
                if "website" in obj_lower or "web design" in obj_lower:
                    self._add_query(
                        queries, seen_queries,
                        f"{industry} {loc_clean} website",
                        family="intent", location=loc_clean, intent="Website discovery"
                    )
                if "seo" in obj_lower or "marketing" in obj_lower:
                    self._add_query(
                        queries, seen_queries,
                        f"{industry} in {loc_clean} reviews",
                        family="intent", location=loc_clean, intent="Reviews & marketing presence"
                    )
            
            # Common commercial intent queries
            self._add_query(
                queries, seen_queries,
                f"{industry} {loc_clean} \"book appointment\"",
                family="intent", location=loc_clean, intent="Booking intent"
            )

            # 5. Search-Operator / Dork Queries
            for term in subject_terms[:2]:
                # Exact phrase matching
                self._add_query(
                    queries, seen_queries,
                    f'"{term}" "{loc_clean}" "contact"',
                    family="dork", location=loc_clean, intent="Exact contact dork"
                )
                self._add_query(
                    queries, seen_queries,
                    f'"{term}" "{loc_clean}" "email"',
                    family="dork", location=loc_clean, intent="Exact email dork"
                )
                self._add_query(
                    queries, seen_queries,
                    f'"{term}" "{loc_clean}" inurl:contact',
                    family="dork", location=loc_clean, intent="Inurl contact page dork"
                )
                
                # 6. Social Discovery Dorks
                self._add_query(
                    queries, seen_queries,
                    f'site:instagram.com "{term}" "{loc_clean}"',
                    family="social_dork", location=loc_clean, intent="Instagram public profile dork"
                )
                self._add_query(
                    queries, seen_queries,
                    f'site:facebook.com "{term}" "{loc_clean}"',
                    family="social_dork", location=loc_clean, intent="Facebook public profile dork"
                )
                self._add_query(
                    queries, seen_queries,
                    f'site:linkedin.com/company "{term}" "{loc_clean}"',
                    family="social_dork", location=loc_clean, intent="LinkedIn company dork"
                )

        return queries

    def generate_explicit_intent_queries(
        self,
        services_offered: List[str],
        locations: List[str],
        target_industry: str = "",
    ) -> List[GeneratedQuery]:
        """
        Generate searches for businesses publicly asking for help with services
        the user sells. Kept separate from business discovery queries.
        """
        queries: List[GeneratedQuery] = []
        seen_queries: Set[str] = set()
        intent_phrases = INTENT_MODIFIERS[:8]

        for loc in locations:
            loc_clean = loc.strip()
            if not loc_clean:
                continue

            for raw_service in services_offered:
                service_key = normalize_service_name(raw_service)
                if not service_key:
                    continue

                keywords = get_primary_keywords_for_service(service_key, limit=3) or [raw_service]
                generated_for_pair = 0

                for phrase in intent_phrases:
                    if generated_for_pair >= 8:
                        break

                    keyword = keywords[generated_for_pair % len(keywords)]
                    self._add_query(
                        queries,
                        seen_queries,
                        f'"{phrase}" "{keyword}" "{loc_clean}"',
                        family="explicit_intent",
                        location=loc_clean,
                        intent=f"Explicit intent for {keyword}: {phrase}",
                        query_type="explicit_intent",
                        service=service_key,
                        intent_type=self._intent_type_from_phrase(phrase),
                    )
                    generated_for_pair += 1

            if target_industry:
                for phrase in intent_phrases[:4]:
                    self._add_query(
                        queries,
                        seen_queries,
                        f'"{target_industry}" "{phrase}" "{loc_clean}"',
                        family="explicit_intent",
                        location=loc_clean,
                        intent=f"Industry intent for {target_industry}: {phrase}",
                        query_type="industry_intent",
                        service=None,
                        intent_type=self._intent_type_from_phrase(phrase),
                    )

        return queries

    def _add_query(
        self,
        queries: List[GeneratedQuery],
        seen: Set[str],
        query_text: str,
        family: str,
        location: str,
        intent: str,
        query_type: str = "business_discovery",
        service: Optional[str] = None,
        intent_type: Optional[str] = None,
    ):
        q_norm = query_text.strip()
        if q_norm and q_norm.lower() not in seen:
            seen.add(q_norm.lower())
            queries.append(GeneratedQuery(
                query=q_norm,
                family=family,
                location=location,
                target_intent=intent,
                query_type=query_type,
                service=service,
                intent_type=intent_type,
            ))

    def _intent_type_from_phrase(self, phrase: str) -> str:
        phrase_lower = phrase.lower()
        if "hir" in phrase_lower:
            return "hiring"
        if "recommend" in phrase_lower or "suggest" in phrase_lower:
            return "recommend"
        if "looking" in phrase_lower or "seeking" in phrase_lower or "searching" in phrase_lower:
            return "looking_for"
        if "need" in phrase_lower or "require" in phrase_lower:
            return "need"
        if "improve" in phrase_lower:
            return "want_to_improve"
        return "other"
