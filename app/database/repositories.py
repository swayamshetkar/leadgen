import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, desc
from app.models.discovery import (
    DiscoveryJobModel, DiscoveredCandidateModel, DiscoveredLeadModel,
    DiscoveryRejectionModel, DiscoveryOutcomeModel,
)
from app.models.candidate import CandidateBusiness
from app.models.rejection import RejectionRecord


class DiscoveryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_job(self, request_payload: dict) -> DiscoveryJobModel:
        job = DiscoveryJobModel(
            id=str(uuid.uuid4()),
            status="pending",
            request_payload=request_payload,
            created_at=datetime.now(timezone.utc)
        )
        self.session.add(job)
        await self.session.commit()
        await self.session.refresh(job)
        return job

    async def get_job(self, job_id: str) -> Optional[DiscoveryJobModel]:
        stmt = select(DiscoveryJobModel).where(DiscoveryJobModel.id == job_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_jobs(self, limit: int = 50) -> List[DiscoveryJobModel]:
        stmt = select(DiscoveryJobModel).order_by(desc(DiscoveryJobModel.created_at)).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_job_status(
        self,
        job_id: str,
        status: str,
        total_queries: Optional[int] = None,
        total_candidates: Optional[int] = None,
        raw_candidates: Optional[int] = None,
        candidates_checked: Optional[int] = None,
        accepted_leads: Optional[int] = None,
        rejected_candidates: Optional[int] = None,
        duplicates: Optional[int] = None,
        error_count: Optional[int] = None,
        unique_businesses: Optional[int] = None,
        pages_crawled: Optional[int] = None,
        errors: Optional[list] = None,
        source_stats: Optional[dict] = None
    ):
        values: Dict[str, Any] = {"status": status}
        if status in ("completed", "completed_partial", "failed"):
            values["completed_at"] = datetime.now(timezone.utc)
        if total_queries is not None:
            values["total_queries"] = total_queries
        if total_candidates is not None:
            values["total_candidates"] = total_candidates
        for field, value in {
            "raw_candidates": raw_candidates,
            "candidates_checked": candidates_checked,
            "accepted_leads": accepted_leads,
            "rejected_candidates": rejected_candidates,
            "duplicates": duplicates,
            "error_count": error_count,
        }.items():
            if value is not None:
                values[field] = value
        if unique_businesses is not None:
            values["unique_businesses"] = unique_businesses
        if pages_crawled is not None:
            values["pages_crawled"] = pages_crawled
        if errors is not None:
            values["errors"] = errors
        if source_stats is not None:
            values["source_stats"] = source_stats

        stmt = update(DiscoveryJobModel).where(DiscoveryJobModel.id == job_id).values(**values)
        await self.session.execute(stmt)
        await self.session.commit()

    async def save_candidates(self, job_id: str, candidates: List[CandidateBusiness]):
        for cand in candidates:
            db_cand = DiscoveredCandidateModel(
                id=str(uuid.uuid4()),
                job_id=job_id,
                source_type=",".join(cand.sources),
                name=cand.name,
                website=cand.website,
                domain=cand.domain,
                data=cand.model_dump(mode="json"),
                created_at=datetime.now(timezone.utc)
            )
            self.session.add(db_cand)
        await self.session.commit()

    async def save_leads(self, job_id: str, leads: List[CandidateBusiness]):
        for lead in leads:
            first_phone = lead.phone_numbers[0].value if lead.phone_numbers else None
            db_lead = DiscoveredLeadModel(
                id=str(uuid.uuid4()),
                job_id=job_id,
                name=lead.name,
                domain=lead.domain,
                website=lead.website,
                phone=first_phone,
                address=lead.address,
                lead_data=lead.model_dump(mode="json"),
                confidence_score=1.0,
                created_at=datetime.now(timezone.utc)
            )
            self.session.add(db_lead)
        await self.session.commit()

    async def get_leads_by_job_id(self, job_id: str) -> List[DiscoveredLeadModel]:
        stmt = select(DiscoveredLeadModel).where(DiscoveredLeadModel.job_id == job_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_lead_by_id(self, job_id: str, lead_id: str) -> Optional[DiscoveredLeadModel]:
        stmt = select(DiscoveredLeadModel).where(
            DiscoveredLeadModel.job_id == job_id,
            DiscoveredLeadModel.id == lead_id,
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_candidates_by_job_id(self, job_id: str) -> List[DiscoveredCandidateModel]:
        stmt = select(DiscoveredCandidateModel).where(DiscoveredCandidateModel.job_id == job_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def save_rejections(self, job_id: str, rejections: List[RejectionRecord]):
        for rejection in rejections:
            self.session.add(DiscoveryRejectionModel(
                id=str(uuid.uuid4()),
                job_id=job_id,
                candidate_name=rejection.candidate_name,
                candidate_url=rejection.candidate_url,
                reason_code=rejection.reason_code,
                reason_detail=rejection.reason_detail,
                stage=rejection.stage,
                source=rejection.source,
                timestamp=rejection.timestamp,
            ))
        await self.session.commit()

    async def get_rejections_by_job_id(self, job_id: str) -> List[DiscoveryRejectionModel]:
        stmt = select(DiscoveryRejectionModel).where(
            DiscoveryRejectionModel.job_id == job_id
        ).order_by(DiscoveryRejectionModel.timestamp)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def save_outcomes(self, job_id: str, outcomes: List[dict]):
        for outcome in outcomes:
            self.session.add(DiscoveryOutcomeModel(
                id=str(uuid.uuid4()),
                job_id=job_id,
                candidate_name=outcome.get("candidate_name"),
                candidate_url=outcome.get("candidate_url"),
                outcome=outcome["outcome"],
                detail=outcome.get("detail"),
                source=outcome.get("source"),
                timestamp=outcome.get("timestamp", datetime.now(timezone.utc)),
            ))
        await self.session.commit()
