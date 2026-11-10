from datetime import datetime, timezone
from typing import Literal, Optional
from urllib.parse import urlparse, urlunparse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import Column, String, Float, DateTime, Text, Boolean
from sqlalchemy.orm import declarative_base

Base = declarative_base()

PlatformType = Literal["Handshake", "LinkedIn", "Indeed"]


class JobListingSchema(BaseModel):
    """Unified Pydantic schema for incoming job listings across all platforms."""

    title: str = Field(..., min_length=2, description="Job title")
    company: str = Field(..., min_length=1, description="Hiring organization name")
    location: str = Field(default="Remote / Unspecified", description="Job location")
    description: str = Field(..., min_length=20, description="Full text job description")
    apply_url: str = Field(..., description="Canonical URL to the job posting")
    source_platform: PlatformType = Field(..., description="Origin platform")
    similarity_score: Optional[float] = Field(default=None)

    @field_validator("apply_url")
    @classmethod
    def normalize_url(cls, v: str) -> str:
        """Strip tracking query parameters where appropriate to enforce clean deduplication."""
        v = v.strip()
        parsed = urlparse(v)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError(f"Invalid URL provided: {v}")
        # Keep query params only for Indeed (jk=...) where job ID lives in query string
        if "indeed.com" in parsed.netloc:
            return v
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))

    @field_validator("title", "company", "location")
    @classmethod
    def clean_whitespace(cls, v: str) -> str:
        return " ".join(v.split())


class JobListingORM(Base):
    """SQLAlchemy ORM model for SQLite persistence and deduplication."""

    __tablename__ = "job_listings"

    apply_url = Column(String(1024), primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    company = Column(String(255), nullable=False)
    location = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    source_platform = Column(String(50), nullable=False)
    similarity_score = Column(Float, nullable=False, default=0.0)
    alerted = Column(Boolean, default=False)
    discovered_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )