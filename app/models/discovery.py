import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, Text, JSON, Boolean, Float
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class DiscoveryJobModel(Base):
    __tablename__ = "discovery_jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    status = Column(String(32), default="pending", index=True)  # pending, running, completed, failed
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)
    
    # Serialized request
    request_payload = Column(JSON, nullable=False)
    
    # Progress & Metrics
    total_queries = Column(Integer, default=0)
    total_candidates = Column(Integer, default=0)
    raw_candidates = Column(Integer, default=0)
    candidates_checked = Column(Integer, default=0)
    accepted_leads = Column(Integer, default=0)
    rejected_candidates = Column(Integer, default=0)
    duplicates = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    unique_businesses = Column(Integer, default=0)
    pages_crawled = Column(Integer, default=0)
    
    # Errors & logs summary
    errors = Column(JSON, default=list)
    source_stats = Column(JSON, default=dict)


class DiscoveredCandidateModel(Base):
    __tablename__ = "discovered_candidates"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String(36), index=True, nullable=False)
    source_type = Column(String(64), index=True, nullable=False)
    
    name = Column(String(255), nullable=True)
    website = Column(String(512), nullable=True)
    domain = Column(String(255), nullable=True, index=True)
    data = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class DiscoveredLeadModel(Base):
    __tablename__ = "discovered_leads"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String(36), index=True, nullable=False)
    
    name = Column(String(255), nullable=True)
    domain = Column(String(255), nullable=True, index=True)
    website = Column(String(512), nullable=True)
    phone = Column(String(64), nullable=True)
    address = Column(Text, nullable=True)
    
    # Full normalized candidate structure including emails, phones, socials, evidence
    lead_data = Column(JSON, nullable=False)
    confidence_score = Column(Float, default=1.0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class DiscoveryRejectionModel(Base):
    __tablename__ = "discovery_rejections"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String(36), index=True, nullable=False)
    candidate_name = Column(String(255), nullable=True)
    candidate_url = Column(String(512), nullable=True)
    reason_code = Column(String(64), index=True, nullable=False)
    reason_detail = Column(Text, nullable=False)
    stage = Column(String(64), index=True, nullable=False)
    source = Column(String(128), nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class DiscoveryOutcomeModel(Base):
    __tablename__ = "discovery_outcomes"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String(36), index=True, nullable=False)
    candidate_name = Column(String(255), nullable=True)
    candidate_url = Column(String(512), nullable=True)
    outcome = Column(String(16), index=True, nullable=False)
    detail = Column(Text, nullable=True)
    source = Column(String(128), nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
