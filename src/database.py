import logging
from contextlib import contextmanager
from typing import Generator
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker, Session
from src.config import settings
from src.models import Base, JobListingORM, JobListingSchema

logger = logging.getLogger(__name__)


class DatabaseManager:
    def __init__(self, db_url: str = settings.DATABASE_URL) -> None:
        self.engine = create_engine(
            db_url, connect_args={"check_same_thread": False}, echo=False
        )
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine
        )

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database transaction error: {e}")
            raise
        finally:
            session.close()

    def is_url_processed(self, apply_url: str) -> bool:
        """Check if a job URL already exists in the SQLite database."""
        with self.get_session() as session:
            stmt = select(JobListingORM.apply_url).where(
                JobListingORM.apply_url == apply_url
            )
            result = session.execute(stmt).scalar_one_or_none()
            return result is not None

    def save_job(
        self, job: JobListingSchema, score: float, alerted: bool = False
    ) -> None:
        """Persist a newly evaluated job listing to prevent future duplicate processing."""
        with self.get_session() as session:
            record = JobListingORM(
                apply_url=job.apply_url,
                title=job.title,
                company=job.company,
                location=job.location,
                description=job.description,
                source_platform=job.source_platform,
                similarity_score=score,
                alerted=alerted,
            )
            session.merge(record)
            logger.debug(f"Saved job to DB: {job.title} @ {job.company} ({score:.3f})")