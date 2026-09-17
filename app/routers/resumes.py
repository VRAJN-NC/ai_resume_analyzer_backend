from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import get_current_user
from app.db.models import Analysis, Recommendation, Resume, ResumeStatus, User
from app.db.session import get_db
from app.schemas.resumes import (
    AnalysisOut,
    DeleteResponse,
    GrammarIssue,
    RecommendedRole,
    ResumeListResponse,
    ResumeOut,
    ResumeUploadResponse,
    SectionFeedback,
)
from app.services.agent.agent import _AnalysisError, safe_run_analysis
from app.services.pdf_parser import extract_text

router = APIRouter(prefix="/resumes", tags=["resumes"])

_MAX_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_analysis_out(analysis: Analysis, recs: list) -> AnalysisOut:
    return AnalysisOut(
        ats_score=analysis.ats_score or 0.0,
        formatting_score=analysis.formatting_score or 0.0,
        keyword_score=analysis.keyword_score or 0.0,
        matched_keywords=analysis.matched_keywords or [],
        missing_keywords=analysis.missing_keywords or [],
        grammar_issues=[GrammarIssue(**i) for i in (analysis.grammar_issues or [])],
        section_feedback=[SectionFeedback(**i) for i in (analysis.section_feedback or [])],
        extracted_skills=analysis.extracted_skills or [],
        missing_skills=analysis.missing_skills or [],
        recommended_roles=[
            RecommendedRole(
                role_title=r.job_role.title,
                match_percent=r.match_percent,
                reason=r.reason or "",
            )
            for r in recs
        ],
    )


async def _load_resume_for_user(
    resume_id: UUID, user_id: UUID, db: AsyncSession
) -> Resume:
    result = await db.execute(
        select(Resume)
        .options(
            selectinload(Resume.analysis).selectinload(Analysis.recommendations).selectinload(
                Recommendation.job_role
            )
        )
        .where(Resume.id == resume_id, Resume.user_id == user_id)
    )
    resume = result.scalar_one_or_none()
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RESUME_NOT_FOUND", "message": f"Resume {resume_id} not found."},
        )
    return resume


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/upload", response_model=ResumeUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_resume(
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Validate content type
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        if not (file.filename or "").lower().endswith(".pdf"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "INVALID_FILE_TYPE", "message": "Only PDF files are accepted."},
            )

    file_bytes = await file.read()

    # Validate size
    if len(file_bytes) > _MAX_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "FILE_TOO_LARGE", "message": "File exceeds the 5 MB limit."},
        )

    # Double-check PDF magic bytes
    if not file_bytes.startswith(b"%PDF"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_FILE_TYPE", "message": "Uploaded file is not a valid PDF."},
        )

    raw_text = extract_text(file_bytes)

    resume = Resume(
        user_id=current_user.id,
        filename=file.filename or "resume.pdf",
        raw_text=raw_text,
        status=ResumeStatus.pending,
    )
    db.add(resume)
    await db.flush()
    await db.refresh(resume)

    return ResumeUploadResponse(resume_id=resume.id, status=resume.status.value)


@router.get("", response_model=ResumeListResponse)
async def list_resumes(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Resume)
        .options(
            selectinload(Resume.analysis).selectinload(Analysis.recommendations).selectinload(
                Recommendation.job_role
            )
        )
        .where(Resume.user_id == current_user.id)
        .order_by(Resume.uploaded_at.desc())
    )
    resumes = result.scalars().all()

    resume_outs = []
    for r in resumes:
        analysis_out = None
        if r.analysis:
            analysis_out = _build_analysis_out(r.analysis, r.analysis.recommendations)
        resume_outs.append(
            ResumeOut(
                id=r.id,
                filename=r.filename,
                uploaded_at=r.uploaded_at,
                status=r.status.value,
                analysis=analysis_out,
            )
        )

    return ResumeListResponse(resumes=resume_outs)


@router.get("/{resume_id}", response_model=ResumeOut)
async def get_resume(
    resume_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    resume = await _load_resume_for_user(resume_id, current_user.id, db)
    analysis_out = None
    if resume.analysis:
        analysis_out = _build_analysis_out(resume.analysis, resume.analysis.recommendations)
    return ResumeOut(
        id=resume.id,
        filename=resume.filename,
        uploaded_at=resume.uploaded_at,
        status=resume.status.value,
        analysis=analysis_out,
    )


@router.delete("/{resume_id}", response_model=DeleteResponse)
async def delete_resume(
    resume_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Resume).where(Resume.id == resume_id, Resume.user_id == current_user.id)
    )
    resume = result.scalar_one_or_none()
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RESUME_NOT_FOUND", "message": f"Resume {resume_id} not found."},
        )
    await db.delete(resume)
    return DeleteResponse(success=True)


@router.post("/{resume_id}/analyze")
async def analyze_resume(
    resume_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Verify ownership
    result = await db.execute(
        select(Resume).where(Resume.id == resume_id, Resume.user_id == current_user.id)
    )
    resume = result.scalar_one_or_none()
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RESUME_NOT_FOUND", "message": f"Resume {resume_id} not found."},
        )

    if not resume.raw_text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "NO_TEXT", "message": "No text could be extracted from this PDF."},
        )

    try:
        result_dict = await safe_run_analysis(resume_id, db)
    except _AnalysisError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": exc.code, "message": exc.message},
        )

    analysis: Analysis = result_dict["analysis"]

    # Reload analysis with recommendations eagerly
    await db.refresh(analysis)
    recs_result = await db.execute(
        select(Recommendation)
        .options(selectinload(Recommendation.job_role))
        .where(Recommendation.analysis_id == analysis.id)
    )
    recs = recs_result.scalars().all()

    return {"analysis": _build_analysis_out(analysis, recs).model_dump()}


@router.get("/{resume_id}/analysis", response_model=AnalysisOut)
async def get_analysis(
    resume_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    resume = await _load_resume_for_user(resume_id, current_user.id, db)

    if not resume.analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "ANALYSIS_NOT_FOUND", "message": "No analysis found for this resume."},
        )

    return _build_analysis_out(resume.analysis, resume.analysis.recommendations)
