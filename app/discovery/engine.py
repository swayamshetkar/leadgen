import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from app.schemas.discovery_request import DiscoveryRequest
from app.models.candidate import CandidateBusiness, EmailRecord, PhoneRecord
from app.models.evidence import EvidenceRecord
from app.core.logging import get_logger
from app.discovery.sources.base import BaseDiscoverySource
from app.discovery.sources.search import SearchDiscoverySource
from app.discovery.sources.maps import MapsDiscoverySource
from app.discovery.sources.instagram import InstagramDiscoverySource
from app.discovery.sources.dorking import DorkingDiscoverySource
from app.discovery.sources.historical import HistoricalDiscoverySource
from app.discovery.sources.intent import ExplicitIntentDiscoverySource
from app.discovery.website.crawler import WebsiteCrawler
from app.discovery.extractors.jsonld import JSONLDExtractor
from app.discovery.extractors.metadata import MetadataExtractor
from app.discovery.extractors.contact import ContactExtractor
from app.discovery.extractors.social import SocialExtractor
from app.discovery.extractors.business import BusinessExtractor
from app.discovery.deduplication.merger import CandidateMerger
from app.discovery.opportunities.engine import OpportunityEngine
from app.models.candidate import ServiceOpportunity as CandidateServiceOpportunity
from app.utils.urls import extract_domain
from app.core.config import settings
from app.discovery.ai.validator import AICandidateValidator
from app.discovery.validation.business_validator import BusinessValidator
from app.discovery.deduplication.matcher import CandidateMatcher
from app.models.rejection import RejectionRecord

logger = get_logger("discovery.engine")


class DiscoveryEngine:
    """
    Multi-Source Lead Discovery Engine.
    Executes parallel discovery strategies, crawls candidate domains,
    extracts structured intelligence, normalizes data, and aggregates evidence.
    """
    def __init__(self):
        self.sources: List[BaseDiscoverySource] = [
            SearchDiscoverySource(),
            MapsDiscoverySource(),
            InstagramDiscoverySource(),
            HistoricalDiscoverySource(),
            ExplicitIntentDiscoverySource(),
        ]
        self.crawler = WebsiteCrawler()
        self.jsonld_extractor = JSONLDExtractor()
        self.meta_extractor = MetadataExtractor()
        self.contact_extractor = ContactExtractor()
        self.social_extractor = SocialExtractor()
        self.business_extractor = BusinessExtractor()
        self.merger = CandidateMerger()
        self.opportunity_engine = OpportunityEngine()
        self.ai_validator = AICandidateValidator()
        self.business_validator = BusinessValidator()
        self.matcher = CandidateMatcher()

    async def execute_discovery(
        self,
        request: DiscoveryRequest,
        progress_callback: Optional[Any] = None
    ) -> Dict[str, Any]:
        job_errors: List[Dict[str, Any]] = []
        source_stats: Dict[str, int] = {}
        all_candidates: List[CandidateBusiness] = []
        registry: List[CandidateBusiness] = []
        accepted_leads: List[CandidateBusiness] = []
        rejections: List[RejectionRecord] = []
        outcomes: List[Dict[str, Any]] = []
        started_at = asyncio.get_running_loop().time()
        target_leads = request.settings.target_leads
        candidate_limit = request.settings.max_candidates_checked
        runtime_limit = request.settings.max_runtime_minutes * 60
        total_queries = len(SearchDiscoverySource().query_gen.generate_queries(request))
        if request.services_offered:
            total_queries += len(SearchDiscoverySource().query_gen.generate_explicit_intent_queries(
                request.services_offered, request.locations, request.target.industry
            ))

        logger.info(f"Starting discovery engine for industry '{request.target.industry}' across {len(request.locations)} locations")

        # 1. Run sources concurrently, consuming each source as it finishes.
        async def _run_source(source: BaseDiscoverySource):
            try:
                results = await source.discover(request)
                source_stats[source.name] = len(results)
                return results
            except asyncio.TimeoutError:
                logger.warning(
                    "Discovery source '%s' exceeded %ss and was cancelled",
                    source.name,
                    settings.SOURCE_TIMEOUT,
                )
                job_errors.append({
                    "source": source.name,
                    "status": "timeout",
                    "error": f"Source exceeded {settings.SOURCE_TIMEOUT} seconds",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                source_stats[source.name] = 0
                return []
            except Exception as e:
                logger.error(f"Discovery source '{source.name}' failed: {e}", exc_info=True)
                job_errors.append({
                    "source": source.name,
                    "status": "failed",
                    "error": str(e),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
                source_stats[source.name] = 0
                return []

        tasks = {
            asyncio.create_task(asyncio.wait_for(_run_source(src), settings.SOURCE_TIMEOUT)): src.name
            for src in self.sources
        }
        crawled_count = 0
        seen_crawled_domains = set()
        checked = 0
        duplicates = 0
        candidate_errors = 0
        while tasks and len(accepted_leads) < target_leads:
            remaining = runtime_limit - (asyncio.get_running_loop().time() - started_at)
            if remaining <= 0 or checked >= candidate_limit:
                break
            done, _ = await asyncio.wait(
                tasks,
                timeout=remaining,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if not done:
                break
            for task in done:
                source_name = tasks.pop(task, None)
                try:
                    source_candidates = task.result()
                except asyncio.TimeoutError:
                    source_candidates = []
                    source_stats[source_name] = 0
                    job_errors.append({
                        "source": source_name,
                        "status": "timeout",
                        "error": f"Source exceeded {settings.SOURCE_TIMEOUT} seconds",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                except Exception as error:
                    source_candidates = []
                    source_stats[source_name] = 0
                    job_errors.append({
                        "source": source_name,
                        "status": "failed",
                        "error": str(error),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                all_candidates.extend(source_candidates)
                for candidate in source_candidates:
                    if checked >= candidate_limit or len(accepted_leads) >= target_leads:
                        break
                    checked += 1
                    try:
                        existing = next((item for item in registry if self.matcher.is_match(item, candidate)), None)
                        if existing is not None:
                            merged = self.merger._merge_cluster([existing, candidate])
                            registry[registry.index(existing)] = merged
                            accepted_index = next(
                                (index for index, lead in enumerate(accepted_leads)
                                 if self.matcher.is_match(existing, lead)),
                                None,
                            )
                            if accepted_index is not None:
                                accepted_leads[accepted_index] = merged
                            duplicates += 1
                            outcomes.append(self._outcome(candidate, "DUPLICATE", "Matched an existing registry identity"))
                            continue
                        registry.append(candidate)

                        validation = self.business_validator.validate(candidate, request)
                        if not validation.is_valid:
                            rejection = self._rejection(candidate, validation.rejection_reason or "Candidate failed deterministic validation", validation.rejection_reason)
                            rejections.append(rejection)
                            outcomes.append(self._outcome(candidate, "REJECTED", rejection.reason_detail))
                            continue
                        identity = await self.ai_validator.validate_identity(candidate, request)
                        if not (identity.is_real_business and identity.name_is_business and identity.matches_industry and identity.matches_location):
                            rejection = self._rejection(candidate, "; ".join(identity.reasons) or "Candidate failed identity validation", self._ai_reason_code(identity))
                            rejections.append(rejection)
                            outcomes.append(self._outcome(candidate, "REJECTED", rejection.reason_detail))
                            continue

                        if (
                            candidate.website and candidate.domain
                            and candidate.domain not in seen_crawled_domains
                            and len(seen_crawled_domains) < settings.MAX_WEBSITE_DOMAINS_PER_JOB
                        ):
                            seen_crawled_domains.add(candidate.domain)
                            try:
                                pages = await asyncio.wait_for(
                                    self.crawler.crawl_domain(candidate.website, max_pages=3),
                                    timeout=settings.WEBSITE_CRAWL_TIMEOUT,
                                )
                                crawled_count += len(pages)
                                for page in pages:
                                    self._enrich_candidate_from_page(candidate, page.html, page.url, request.target.services, request.services_offered, request.locations)
                            except Exception as error:
                                logger.debug("Website expansion failed for %s: %s", candidate.website, error)

                        final_check = await self.ai_validator.validate_final(candidate, request)
                        final_validation = self.business_validator.validate(candidate, request)
                        if final_check.is_contactable and final_validation.is_valid:
                            self._finalize_lead_intelligence(candidate)
                            accepted_leads.append(candidate)
                            outcomes.append(self._outcome(candidate, "ACCEPTED", "Candidate passed final validation"))
                        else:
                            rejection = self._rejection(candidate, "; ".join(final_check.reasons) or final_validation.rejection_reason or "Candidate failed final validation", "NO_CONTACT_METHOD" if not final_check.is_contactable else "CONTACT_MISMATCH", stage="contact_validation")
                            rejections.append(rejection)
                            outcomes.append(self._outcome(candidate, "REJECTED", rejection.reason_detail))
                    except Exception as error:
                        candidate_errors += 1
                        outcomes.append(self._outcome(candidate, "ERROR", str(error)))
                        logger.exception("Candidate processing failed for %s", candidate.name)

        for task in tasks:
            task.cancel()
        if len(accepted_leads) >= target_leads:
            final_status = "completed"
        else:
            final_status = "completed_partial"
        logger.info("Discovery complete: %s checked, %s accepted (%s)", checked, len(accepted_leads), final_status)

        return {
            "total_candidates": len(all_candidates),
            "unique_businesses": len(accepted_leads),
            "raw_candidates": len(all_candidates),
            "candidates_checked": checked,
            "rejected_candidates": len(rejections),
            "duplicates": duplicates,
            "candidate_errors": candidate_errors,
            "error_count": candidate_errors,
            "accepted_leads": len(accepted_leads),
            "status": final_status,
            "target_leads": target_leads,
            "max_candidates_checked": candidate_limit,
            "total_queries": total_queries,
            "pages_crawled": crawled_count,
            "errors": job_errors,
            "source_stats": source_stats,
            "raw_candidates": len(all_candidates),
            "raw_candidate_records": all_candidates,
            "leads": accepted_leads,
            "rejections": rejections,
            "outcomes": outcomes,
        }

    def _outcome(self, candidate: CandidateBusiness, outcome: str, detail: str) -> Dict[str, Any]:
        return {
            "candidate_name": candidate.name,
            "candidate_url": candidate.website,
            "outcome": outcome,
            "detail": detail,
            "source": ",".join(candidate.sources) or None,
            "timestamp": datetime.now(timezone.utc),
        }

    def _rejection(
        self,
        candidate: CandidateBusiness,
        detail: str,
        reason_code: Optional[str] = None,
        stage: str = "business_identity",
    ) -> RejectionRecord:
        code = reason_code if reason_code in {
            "NOT_A_BUSINESS", "DIRECTORY_SOURCE", "INVALID_COMPANY_NAME", "WRONG_INDUSTRY",
            "WRONG_LOCATION", "DUPLICATE", "WEBSITE_MISMATCH", "CONTACT_MISMATCH",
            "NO_CONTACT_METHOD", "LOW_IDENTITY_CONFIDENCE", "INVALID_URL", "INVALID_CONTACT",
            "EXPLICIT_INTENT_NOT_CONFIRMED", "SOURCE_ERROR", "OTHER",
        } else "OTHER"
        lowered = detail.lower()
        if "directory" in lowered or "aggregator" in lowered:
            code = "DIRECTORY_SOURCE"
        elif "listing title" in lowered or "identifiable business name" in lowered:
            code = "NOT_A_BUSINESS"
        elif "industry" in lowered:
            code = "WRONG_INDUSTRY"
        elif "location" in lowered:
            code = "WRONG_LOCATION"
        elif "contact" in lowered:
            code = "NO_CONTACT_METHOD"
        if stage == "business_identity":
            stage = {
                "WRONG_INDUSTRY": "relevance",
                "WRONG_LOCATION": "location",
                "NO_CONTACT_METHOD": "contact_validation",
                "CONTACT_MISMATCH": "contact_validation",
            }.get(code, stage)
        return RejectionRecord(
            candidate_name=candidate.name,
            candidate_url=candidate.website,
            reason_code=code,
            reason_detail=detail,
            stage=stage,
            source=",".join(candidate.sources) or None,
        )

    def _ai_reason_code(self, result) -> str:
        if result.is_source_page or not result.name_is_business:
            return "NOT_A_BUSINESS"
        if not result.matches_industry:
            return "WRONG_INDUSTRY"
        if not result.matches_location:
            return "WRONG_LOCATION"
        return "LOW_IDENTITY_CONFIDENCE"

    def _enrich_candidate_from_page(
        self,
        cand: CandidateBusiness,
        html: str,
        page_url: str,
        target_services: List[str],
        services_offered: Optional[List[str]] = None,
        location_keywords: Optional[List[str]] = None,
    ):
        if not html:
            return

        # 1. JSON-LD Extraction
        jsonld_items = self.jsonld_extractor.extract(html, page_url)
        for j_item in jsonld_items:
            if j_item.get("name") and (not cand.name or len(j_item["name"]) > len(cand.name)):
                cand.name = j_item["name"]
                cand.add_evidence("name", j_item["name"], "jsonld", page_url, confidence=0.98)

            if j_item.get("telephone"):
                phone_val = j_item["telephone"]
                if not any(p.value == phone_val for p in cand.phone_numbers):
                    cand.phone_numbers.append(PhoneRecord(value=phone_val, source_url=page_url, source_type="jsonld"))
                    cand.add_evidence("phone", phone_val, "jsonld", page_url, confidence=0.95)

            if j_item.get("email"):
                email_val = j_item["email"]
                if not any(e.value == email_val for e in cand.emails):
                    cand.emails.append(EmailRecord(value=email_val, verified=False, source_url=page_url, source_type="jsonld"))
                    cand.add_evidence("email", email_val, "jsonld", page_url, confidence=0.95)

            if j_item.get("address") and not cand.address:
                cand.address = j_item["address"]
                cand.add_evidence("address", j_item["address"], "jsonld", page_url, confidence=0.95)

            if j_item.get("description") and not cand.description:
                cand.description = j_item["description"]

        # 2. Metadata Extraction
        meta = self.meta_extractor.extract(html, page_url)
        if not cand.description and meta.get("description"):
            cand.description = meta["description"]
            cand.add_evidence("description", meta["description"], "meta_tag", page_url, confidence=0.85)

        # 3. Contacts Extraction (HTML Body & Links)
        contacts = self.contact_extractor.extract_contacts(html, page_url)
        for em in contacts["emails"]:
            if not any(e.value == em.value for e in cand.emails):
                cand.emails.append(em)
                cand.add_evidence("email", em.value, "website_html", page_url, confidence=0.90)

        for ph in contacts["phone_numbers"]:
            if not any(p.value == ph.value for p in cand.phone_numbers):
                cand.phone_numbers.append(ph)
                cand.add_evidence("phone", ph.value, "website_html", page_url, confidence=0.90)

        if not cand.address and contacts.get("address"):
            cand.address = contacts["address"]
            cand.add_evidence("address", contacts["address"], "website_html", page_url, confidence=0.80)

        # 4. Social Profile Extraction
        same_as = []
        for j in jsonld_items:
            same_as.extend(j.get("sameAs", []))
        socials = self.social_extractor.extract_socials(html, same_as_urls=same_as)
        for platform, link in socials.items():
            if platform not in cand.social_profiles or not cand.social_profiles[platform]:
                cand.social_profiles[platform] = link
                cand.add_evidence(f"social_profiles.{platform}", link, "website_link", page_url, confidence=0.92)

        # 5. Business Details Extraction
        biz_info = self.business_extractor.extract_business_info(
            html, meta, jsonld_items, target_services=target_services
        )
        if not cand.name and biz_info.get("name"):
            cand.name = biz_info["name"]
            cand.add_evidence("name", biz_info["name"], "website_heading", page_url, confidence=0.80)

        for s in biz_info.get("services", []):
            if s not in cand.services:
                cand.services.append(s)

        # 6. Opportunity Detection
        if services_offered:
            result = self.opportunity_engine.evaluate(
                services_offered=services_offered,
                html=html,
                meta=meta,
                jsonld_items=jsonld_items,
                social_profiles=cand.social_profiles,
                business_name=cand.name,
                domain=cand.domain,
                location_keywords=location_keywords,
                page_url=page_url,
            )
            if result.has_opportunities:
                existing_services = {o.service for o in cand.service_opportunities}
                for opp in result.opportunities:
                    if opp.service not in existing_services:
                        cand.service_opportunities.append(
                            CandidateServiceOpportunity.model_validate(opp.model_dump())
                        )
                        existing_services.add(opp.service)

                if cand.lead_type == "explicit_intent":
                    cand.lead_type = "explicit_and_opportunity"
                elif not cand.lead_type:
                    cand.lead_type = "opportunity"
                if not cand.short_reason:
                    cand.short_reason = result.get_short_reason()

    def _finalize_lead_intelligence(self, lead: CandidateBusiness):
        if not lead.about:
            lead.about = lead.generate_about()

        if lead.service_opportunities and not lead.short_reason:
            top = lead.service_opportunities[0]
            lead.short_reason = f"Potential {top.service_display} opportunity: {top.reason}"
        elif lead.intent_evidence and not lead.short_reason:
            text = lead.intent_evidence.text
            if len(text) > 140:
                text = text[:137] + "..."
            lead.short_reason = f"Public intent signal: {text}"
