
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    job_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="queued")
    safe_to_send: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    combined_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    documents: Mapped[list["ScrubbedDocument"]] = relationship(
        back_populates="processing_job",
        cascade="all, delete-orphan",
    )


class ScrubbedDocument(Base):
    __tablename__ = "scrubbed_documents"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    processing_job_id: Mapped[int] = mapped_column(
        ForeignKey("processing_jobs.id"),
        nullable=False,
        index=True,
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="success")
    safe_to_send: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    redacted_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    warnings: Mapped[str | None] = mapped_column(Text, nullable=True)
    scrubbed_output: Mapped[str] = mapped_column(Text, nullable=False)

    processing_job: Mapped[ProcessingJob] = relationship(
        back_populates="documents"
    )
