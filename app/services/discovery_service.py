import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.discovery_request import DiscoveryRequest
from app.schemas.discovery_response import DiscoveryJobStatus, DiscoveryResultResponse
from app.schemas.candidate import DiscoveredLeadOutput
from app.database.connection import async_session
from app.database.repositories import DiscoveryRepository
from app.discovery.engine import DiscoveryEngine
from app.discovery.query_generator import QueryGenerator
from app.models.rejection import RejectionRecord
from app.core.logging import get_logger

logger = get_logger("service.discovery")


class DiscoveryService:
    """
    Asynchronous discovery job orchestrator.
    Manages job states, runs background discovery tasks, and persists results.
    """
    def __init__(self):
        self.engine = DiscoveryEngine()
        self.query_gen = QueryGenerator()

    async def submit_job(self, request: DiscoveryRequest) -> str:
        async with async_session() as session:
            repo = DiscoveryRepository(session)
            job = await repo.create_job(request.model_dump(mode="json"))
            job_id = job.id

        # Launch background task
        asyncio.create_task(self._run_job(job_id, request))
        return job_id

    async def _run_job(self, job_id: str, request: DiscoveryRequest):
        logger.info(f"Background discovery task started for job {job_id}")
        
        async with async_session() as session:
            repo = DiscoveryRepository(session)
            await repo.update_job_status(job_id, "running")

        try:
            result_data = await self.engine.execute_discovery(request)

            async with async_session() as session:
                repo = DiscoveryRepository(session)
                
                # Save raw candidates
                raw_candidates = result_data.get("raw_candidate_records", [])
                await repo.save_candidates(job_id, raw_candidates)

                # Save merged leads
                leads = result_data.get("leads", [])
                await repo.save_leads(job_id, leads)
                await repo.save_rejections(job_id, result_data.get("rejections", []))
                await repo.save_outcomes(job_id, result_data.get("outcomes", []))

                # Update job status to completed
                await repo.update_job_status(
                    job_id=job_id,
                    status=result_data.get("status", "completed"),
                    total_queries=result_data.get("total_queries", 0),
                    total_candidates=result_data.get("total_candidates", 0),
                    raw_candidates=result_data.get("raw_candidates", 0),
                    candidates_checked=result_data.get("candidates_checked", 0),
                    accepted_leads=result_data.get("accepted_leads", 0),
                    rejected_candidates=result_data.get("rejected_candidates", 0),
                    duplicates=result_data.get("duplicates", 0),
                    error_count=result_data.get("error_count", 0),
                    unique_businesses=result_data.get("unique_businesses", 0),
                    pages_crawled=result_data.get("pages_crawled", 0),
                    errors=result_data.get("errors", []),
                    source_stats=result_data.get("source_stats", {})
                )

            logger.info(f"Discovery job {job_id} successfully completed with {result_data.get('unique_businesses')} leads")

        except Exception as e:
            logger.error(f"Discovery job {job_id} failed with error: {e}", exc_info=True)
            async with async_session() as session:
                repo = DiscoveryRepository(session)
                await repo.update_job_status(
                    job_id=job_id,
                    status="failed",
                    errors=[{"error": str(e), "timestamp": datetime.now(timezone.utc).isoformat()}]
                )

    async def get_job_status(self, job_id: str) -> Optional[DiscoveryJobStatus]:
        async with async_session() as session:
            repo = DiscoveryRepository(session)
            job = await repo.get_job(job_id)
            if not job:
                return None

            return DiscoveryJobStatus(
                job_id=job.id,
                status=job.status,
                created_at=job.created_at,
                completed_at=job.completed_at,
                total_queries=job.total_queries or 0,
                total_candidates=job.total_candidates or 0,
                raw_candidates=job.raw_candidates or 0,
                candidates_checked=job.candidates_checked or 0,
                accepted_leads=job.accepted_leads or 0,
                rejected_candidates=job.rejected_candidates or 0,
                duplicates=job.duplicates or 0,
                error_count=job.error_count or 0,
                unique_businesses=job.unique_businesses or 0,
                pages_crawled=job.pages_crawled or 0,
                errors=job.errors or [],
                source_stats=job.source_stats or {}
            )

    async def get_job_results(self, job_id: str) -> Optional[DiscoveryResultResponse]:
        async with async_session() as session:
            repo = DiscoveryRepository(session)
            job = await repo.get_job(job_id)
            if not job:
                return None

            db_leads = await repo.get_leads_by_job_id(job_id)
            results: List[DiscoveredLeadOutput] = []

            for lead in db_leads:
                data = lead.lead_data
                emails = data.get("emails", [])
                phones = data.get("phone_numbers", [])
                locations = data.get("locations", [])
                first_phone = phones[0].get("value") if phones else None
                first_email = emails[0].get("value") if emails else None
                about = data.get("about") or data.get("description")
                if about and len(about) > 200:
                    about = about[:197] + "..."

                results.append(DiscoveredLeadOutput(
                    company_name=data.get("name"),
                    company_details=about,
                    website=data.get("website"),
                    phone=first_phone,
                    email=first_email,
                    contact={
                        platform: url
                        for platform, url in data.get("social_profiles", {}).items()
                        if url
                    },
                ))

            return DiscoveryResultResponse(
                job_id=job.id,
                status=job.status,
                total_candidates=job.total_candidates or 0,
                unique_businesses=len(results),
                results=results
            )

    async def get_lead_evidence(self, job_id: str, lead_id: str) -> Optional[Dict[str, Any]]:
        async with async_session() as session:
            repo = DiscoveryRepository(session)
            lead = await repo.get_lead_by_id(job_id, lead_id)
            if not lead:
                return None

            data = lead.lead_data or {}
            return {
                "lead_id": lead.id,
                "company_name": data.get("name"),
                "lead_type": data.get("lead_type"),
                "intent_evidence": data.get("intent_evidence"),
                "service_opportunities": data.get("service_opportunities", []),
                "evidence": data.get("evidence", []),
                "raw_metadata": data.get("raw_metadata", {}),
                "sources": data.get("sources", []),
            }

    async def get_job_candidates(self, job_id: str) -> List[Dict[str, Any]]:
        async with async_session() as session:
            repo = DiscoveryRepository(session)
            candidates = await repo.get_candidates_by_job_id(job_id)
            return [
                {
                    "id": c.id,
                    "source_type": c.source_type,
                    "name": c.name,
                    "website": c.website,
                    "domain": c.domain,
                    "data": c.data,
                    "created_at": c.created_at
                }
                for c in candidates
            ]

    async def get_job_rejections(self, job_id: str) -> Optional[Dict[str, Any]]:
        async with async_session() as session:
            repo = DiscoveryRepository(session)
            job = await repo.get_job(job_id)
            if not job:
                return None
            records = await repo.get_rejections_by_job_id(job_id)
            return {
                "job_id": job_id,
                "total_rejected": len(records),
                "rejections": [
                    {
                        "rejection_id": record.id,
                        "job_id": record.job_id,
                        "candidate_name": record.candidate_name,
                        "candidate_url": record.candidate_url,
                        "reason_code": record.reason_code,
                        "reason_detail": record.reason_detail,
                        "stage": record.stage,
                        "source": record.source,
                        "timestamp": record.timestamp,
                    }
                    for record in records
                ],
            }

    async def list_jobs(self, limit: int = 50) -> List[DiscoveryJobStatus]:
        async with async_session() as session:
            repo = DiscoveryRepository(session)
            jobs = await repo.list_jobs(limit=limit)
            return [
                DiscoveryJobStatus(
                    job_id=j.id,
                    status=j.status,
                    created_at=j.created_at,
                    completed_at=j.completed_at,
                    total_queries=j.total_queries or 0,
                    total_candidates=j.total_candidates or 0,
                    raw_candidates=j.raw_candidates or 0,
                    candidates_checked=j.candidates_checked or 0,
                    accepted_leads=j.accepted_leads or 0,
                    rejected_candidates=j.rejected_candidates or 0,
                    duplicates=j.duplicates or 0,
                    error_count=j.error_count or 0,
                    unique_businesses=j.unique_businesses or 0,
                    pages_crawled=j.pages_crawled or 0,
                    errors=j.errors or [],
                    source_stats=j.source_stats or {}
                )
                for j in jobs
            ]
