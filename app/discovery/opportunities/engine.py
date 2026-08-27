from typing import List, Dict, Any, Optional
from app.discovery.opportunities.opportunity_model import ServiceOpportunity, OpportunityResult
from app.discovery.opportunities.service_profiles import (
    normalize_service_name, get_display_name
)
from app.discovery.opportunities.website_signals import WebsiteSignalDetector
from app.discovery.opportunities.seo_signals import SEOSignalDetector
from app.discovery.opportunities.social_signals import SocialSignalDetector
from app.discovery.opportunities.branding_signals import BrandingSignalDetector
from app.discovery.opportunities.content_signals import ContentSignalDetector
from app.core.logging import get_logger

logger = get_logger("opportunities.engine")

# Minimum signal count thresholds
MIN_SIGNALS_LOW = 2       # at least 2 signals to avoid false positives
MIN_SIGNALS_MEDIUM = 2    # at least 2 signals for 'medium'
MIN_SIGNALS_HIGH = 3      # 3+ signals for 'high'


class OpportunityEngine:
    """
    Evaluates a candidate business for potential service opportunities based on
    observable public signals.

    IMPORTANT: This engine does NOT make absolute claims. It identifies
    POTENTIAL opportunities using the word 'potential' in all output.
    A business showing signals does NOT mean they definitely need the service.
    """

    def __init__(self):
        self.website_detector = WebsiteSignalDetector()
        self.seo_detector = SEOSignalDetector()
        self.social_detector = SocialSignalDetector()
        self.branding_detector = BrandingSignalDetector()
        self.content_detector = ContentSignalDetector()

    def evaluate(
        self,
        services_offered: List[str],
        html: str = "",
        meta: Optional[Dict[str, Any]] = None,
        jsonld_items: Optional[List[Dict[str, Any]]] = None,
        social_profiles: Optional[Dict[str, Optional[str]]] = None,
        business_name: Optional[str] = None,
        domain: Optional[str] = None,
        location_keywords: Optional[List[str]] = None,
        page_url: str = "",
    ) -> OpportunityResult:
        """
        Evaluate opportunity signals for each service the user offers.

        Args:
            services_offered: List of raw service names the user sells
            html: Crawled page HTML content
            meta: Extracted page metadata dict
            jsonld_items: Extracted JSON-LD structured data items
            social_profiles: Dict of platform -> URL (or None)
            business_name: Detected business name
            domain: Business domain
            location_keywords: Target location names for local SEO checks
            page_url: Primary page URL (used as evidence)

        Returns:
            OpportunityResult with detected service opportunities
        """
        if not services_offered:
            return OpportunityResult()

        meta = meta or {}
        jsonld_items = jsonld_items or []
        social_profiles = social_profiles or {}

        # Run all signal detectors once and cache results
        website_signals, website_evidence = self.website_detector.detect(html, page_url)
        seo_signals, seo_evidence = self.seo_detector.detect(
            html, meta, jsonld_items, location_keywords, page_url
        )
        social_signals_list, social_evidence = self.social_detector.detect(
            social_profiles, business_name, domain
        )
        branding_signals, branding_evidence = self.branding_detector.detect(
            business_name, domain, social_profiles, html, page_url
        )
        content_signals, content_evidence = self.content_detector.detect(html, page_url)

        opportunities: List[ServiceOpportunity] = []
        analyzed_services: List[str] = []

        for raw_service in services_offered:
            service_key = normalize_service_name(raw_service)
            if not service_key:
                logger.debug(f"Could not normalize service name: '{raw_service}'")
                continue

            analyzed_services.append(service_key)
            display_name = get_display_name(service_key)

            # Assemble signals and evidence for this specific service
            signals: List[str] = []
            evidence: List[str] = []

            if service_key == "seo":
                signals.extend(seo_signals)
                evidence.extend(seo_evidence)
                # Website structure issues also affect SEO
                for s in website_signals:
                    if any(kw in s.lower() for kw in ["h1", "content", "thin", "heading", "navigation"]):
                        signals.append(s)

            elif service_key == "social_media":
                signals.extend(social_signals_list)
                evidence.extend(social_evidence)

            elif service_key == "branding":
                signals.extend(branding_signals)
                evidence.extend(branding_evidence)
                # Social inconsistency is also a branding signal
                for s in social_signals_list:
                    if any(kw in s.lower() for kw in ["inconsistent", "mismatch", "fragmented"]):
                        signals.append(s)

            elif service_key == "website_design":
                signals.extend(website_signals)
                evidence.extend(website_evidence)

            elif service_key == "content_creation":
                signals.extend(content_signals)
                evidence.extend(content_evidence)

            elif service_key == "digital_marketing":
                # Digital marketing is a broad combination
                all_digital_signals = seo_signals + social_signals_list + content_signals
                signals.extend(all_digital_signals)
                evidence.extend(seo_evidence + social_evidence + content_evidence)

            # Deduplicate while preserving order
            seen_signals: set = set()
            unique_signals: List[str] = []
            for s in signals:
                if s not in seen_signals:
                    seen_signals.add(s)
                    unique_signals.append(s)
            signals = unique_signals

            seen_evidence: set = set()
            unique_evidence: List[str] = []
            for e in evidence:
                if e and e not in seen_evidence:
                    seen_evidence.add(e)
                    unique_evidence.append(e)
            evidence = unique_evidence

            signal_count = len(signals)

            # Only report opportunities with sufficient signal evidence
            if signal_count < MIN_SIGNALS_LOW:
                logger.debug(f"Not enough signals for {service_key}: {signal_count}")
                continue

            # Determine confidence level
            if signal_count >= MIN_SIGNALS_HIGH:
                confidence = "high"
            elif signal_count >= MIN_SIGNALS_MEDIUM:
                confidence = "medium"
            else:
                confidence = "low"

            reason = self._generate_reason(service_key, display_name, signals[:3], confidence)

            opportunities.append(ServiceOpportunity(
                service=service_key,
                service_display=display_name,
                confidence=confidence,
                signals=signals,
                evidence=evidence,
                reason=reason,
            ))

        # Sort: high > medium > low
        confidence_order = {"high": 0, "medium": 1, "low": 2}
        opportunities.sort(key=lambda o: confidence_order.get(o.confidence, 3))

        return OpportunityResult(
            has_opportunities=len(opportunities) > 0,
            opportunities=opportunities,
            analyzed_services=analyzed_services,
        )

    def _generate_reason(
        self,
        service_key: str,
        display_name: str,
        top_signals: List[str],
        confidence: str,
    ) -> str:
        """Generate a concise human-readable reason for the opportunity."""
        if not top_signals:
            return f"Potential {display_name} opportunity identified"

        # Use the primary (most descriptive) signal
        primary = top_signals[0].rstrip(".")
        if len(primary) > 120:
            primary = primary[:117] + "..."
        return primary
