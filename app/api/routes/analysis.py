
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.models import ProcessingJob
from app.domain.finance.transaction_parser import parse_transactions
from app.domain.finance.budget_analyzer import analyze_budget
from app.services.groq_analysis_service import (
    GroqAnalysisError,
    GroqAnalysisService,
)

router = APIRouter(tags=["analysis"])


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)


def get_safe_job(
    job_id: int,
    db: Session,
) -> ProcessingJob:
    """Return a job only when it passes all processing safety checks."""

    job = db.get(ProcessingJob, job_id)

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Processing job not found.",
        )

    if (
        job.status != "success"
        or job.safe_to_send is not True
        or job.failed_count != 0
        or job.success_count <= 0
    ):
        raise HTTPException(
            status_code=400,
            detail="Request blocked: processing job did not pass safety checks.",
        )

    if not job.documents:
        raise HTTPException(
            status_code=400,
            detail="Request blocked: no processed documents were found.",
        )

    return job


def create_budget_analysis(job: ProcessingJob) -> dict[str, object]:
    """Calculate financial totals locally from validated scrubbed documents."""

    transactions = []

    for document in job.documents:
        if (
            document.status != "success"
            or document.safe_to_send is not True
            or document.warnings
            or not document.scrubbed_output
        ):
            continue

        parsed = parse_transactions(
            document.scrubbed_output,
            document.file_name,
        )
        transactions.extend(parsed)

    return analyze_budget(transactions)


@router.post("/jobs/{job_id}/analysis")
async def analyze_job(
    job_id: int,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    job = get_safe_job(job_id, db)

    # Financial calculations are performed locally by Python.
    budget_analysis = create_budget_analysis(job)

    service = GroqAnalysisService()

    try:
        result = await service.analyze(job.documents)

        return {
            "status": "success",
            "job_id": job.id,
            "model": result["model"],
            "budget_analysis": budget_analysis,
            "analysis": result["analysis"],
        }

    except GroqAnalysisError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="The financial analysis could not be completed.",
        ) from exc


@router.post("/jobs/{job_id}/chat")
async def chat_with_job(
    job_id: int,
    request: ChatRequest,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """Answer a question using validated scrubbed documents."""

    job = get_safe_job(job_id, db)

    service = GroqAnalysisService()

    try:
        result = await service.chat(
            job.documents,
            request.question,
        )

        return {
            "status": "success",
            "job_id": job.id,
            "model": result["model"],
            "answer": result["answer"],
        }

    except GroqAnalysisError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="The financial chat request could not be completed.",
        ) from exc
