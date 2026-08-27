from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, status, Query
from app.schemas.discovery_request import DiscoveryRequest
from app.schemas.discovery_response import (
    DiscoveryJobResponse,
    DiscoveryJobStatus,
    DiscoveryResultResponse
    ,DiscoveryRejectionsResponse
)
from app.services.discovery_service import DiscoveryService

router = APIRouter(prefix="/api/v1/discovery", tags=["Lead Discovery"])
discovery_service = DiscoveryService()


@router.post(
    "",
    response_model=DiscoveryJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a new lead discovery job"
)
async def submit_discovery_job(request: DiscoveryRequest):
    """
    Submits a multi-source lead discovery request across multiple target locations.
    Returns a job_id immediately to track progress asynchronously.
    """
    job_id = await discovery_service.submit_job(request)
    return DiscoveryJobResponse(
        job_id=job_id,
        status="pending",
        message="Discovery job successfully submitted and running in the background."
    )


@router.get(
    "/{job_id}",
    response_model=DiscoveryJobStatus,
    summary="Get status and progress of a discovery job"
)
async def get_discovery_job_status(job_id: str):
    job_status = await discovery_service.get_job_status(job_id)
    if not job_status:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Discovery job with ID '{job_id}' not found."
        )
    return job_status


@router.get(
    "/{job_id}/results",
    response_model=DiscoveryResultResponse,
    summary="Get discovered business leads"
)
async def get_discovery_job_results(job_id: str):
    results = await discovery_service.get_job_results(job_id)
    if not results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Discovery job with ID '{job_id}' not found."
        )
    return results


@router.get(
    "/{job_id}/rejections",
    response_model=DiscoveryRejectionsResponse,
    summary="Get rejected candidates for debugging",
)
async def get_discovery_job_rejections(job_id: str):
    rejections = await discovery_service.get_job_rejections(job_id)
    if not rejections:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Discovery job with ID '{job_id}' not found.",
        )
    return rejections


@router.get(
    "/{job_id}/leads/{lead_id}/evidence",
    response_model=Dict[str, Any],
    summary="Get detailed evidence for a discovered lead"
)
async def get_discovery_lead_evidence(job_id: str, lead_id: str):
    evidence = await discovery_service.get_lead_evidence(job_id, lead_id)
    if not evidence:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lead '{lead_id}' for discovery job '{job_id}' not found."
        )
    return evidence


@router.get(
    "/{job_id}/candidates",
    response_model=List[Dict[str, Any]],
    summary="Get raw discovered candidates prior to deduplication"
)
async def get_discovery_job_candidates(job_id: str):
    return await discovery_service.get_job_candidates(job_id)


@router.get(
    "",
    response_model=List[DiscoveryJobStatus],
    summary="List past discovery jobs"
)
async def list_discovery_jobs(limit: int = Query(default=20, ge=1, le=100)):
    return await discovery_service.list_jobs(limit=limit)
