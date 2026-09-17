"""LangChain agent orchestrator for resume analysis."""
from __future__ import annotations

import asyncio
import logging
from uuid import UUID

import openai
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Analysis, Recommendation, Resume, ResumeStatus
from app.services.agent.tools.ats_scoring_tool import ats_scoring_tool
from app.services.agent.tools.grammar_tool import grammar_tool
from app.services.agent.tools.job_matching_tool import run_job_matching
from app.services.agent.tools.skill_extraction_tool import skill_extraction_tool

logger = logging.getLogger(__name__)


async def run_analysis_pipeline(resume_id: UUID, db: AsyncSession) -> Analysis:
    """
    Orchestrate the LangChain tool pipeline for a resume:
      1. skill_extraction_tool  (output feeds step 2 and job_matching)
      2. ats_scoring_tool + grammar_tool  (run concurrently)
      3. run_job_matching  (queries DB, generates reasons via LLM)
      4. Persist Analysis + Recommendations to DB.

    Raises on unexpected errors; caller should catch and set resume.status = failed.
    """
    # ------------------------------------------------------------------
    # 0. Load the resume
    # ------------------------------------------------------------------
    result = await db.execute(select(Resume).where(Resume.id == resume_id))
    resume: Resume | None = result.scalar_one_or_none()
    if not resume:
        raise ValueError(f"Resume {resume_id} not found.")

    raw_text = resume.raw_text or ""

    # ------------------------------------------------------------------
    # 1. Skill extraction (must run first — feeds ATS scoring & matching)
    # ------------------------------------------------------------------
    logger.info("Running skill_extraction_tool for resume %s", resume_id)
    skill_result: dict = await skill_extraction_tool.ainvoke({"resume_text": raw_text})
    extracted_skills: list[str] = skill_result.get("extracted_skills", [])
    missing_skills: list[str] = skill_result.get("missing_skills", [])

    # ------------------------------------------------------------------
    # 2. ATS scoring + grammar analysis (run concurrently)
    # ------------------------------------------------------------------
    logger.info("Running ats_scoring_tool and grammar_tool concurrently for resume %s", resume_id)
    ats_coro = ats_scoring_tool.ainvoke({
        "resume_text": raw_text,
        "extracted_skills": extracted_skills,
    })
    grammar_coro = grammar_tool.ainvoke({"resume_text": raw_text})

    ats_result, grammar_result = await asyncio.gather(ats_coro, grammar_coro)

    # ------------------------------------------------------------------
    # 3. Job matching (queries DB, calls LLM for reason strings)
    # ------------------------------------------------------------------
    logger.info("Running job_matching for resume %s", resume_id)
    job_match_output = await run_job_matching(extracted_skills, db)

    # ------------------------------------------------------------------
    # 4. Persist Analysis row
    # ------------------------------------------------------------------
    # Delete existing analysis if re-analysing
    existing = await db.execute(
        select(Analysis).where(Analysis.resume_id == resume_id)
    )
    existing_analysis = existing.scalar_one_or_none()
    if existing_analysis:
        await db.delete(existing_analysis)
        await db.flush()

    analysis = Analysis(
        resume_id=resume_id,
        ats_score=ats_result.get("ats_score", 0.0),
        formatting_score=ats_result.get("formatting_score", 0.0),
        keyword_score=ats_result.get("keyword_score", 0.0),
        matched_keywords=ats_result.get("matched_keywords", []),
        missing_keywords=ats_result.get("missing_keywords", []),
        grammar_issues=[i if isinstance(i, dict) else i.model_dump()
                        for i in grammar_result.get("grammar_issues", [])],
        section_feedback=[i if isinstance(i, dict) else i.model_dump()
                          for i in grammar_result.get("section_feedback", [])],
        extracted_skills=extracted_skills,
        missing_skills=missing_skills,
    )
    db.add(analysis)
    await db.flush()  # Get analysis.id

    # ------------------------------------------------------------------
    # 5. Persist Recommendations
    # ------------------------------------------------------------------
    # We need job_role IDs from the DB to link recommendations
    from app.db.models import JobRole  # local import to avoid circular
    for rec_item in job_match_output.recommended_roles:
        role_result = await db.execute(
            select(JobRole).where(JobRole.title == rec_item.role_title)
        )
        job_role = role_result.scalar_one_or_none()
        if not job_role:
            continue
        rec = Recommendation(
            analysis_id=analysis.id,
            job_role_id=job_role.id,
            match_percent=rec_item.match_percent,
            reason=rec_item.reason,
        )
        db.add(rec)

    # ------------------------------------------------------------------
    # 6. Mark resume as analyzed
    # ------------------------------------------------------------------
    resume.status = ResumeStatus.analyzed
    await db.flush()
    await db.refresh(analysis)

    return analysis


async def safe_run_analysis(resume_id: UUID, db: AsyncSession) -> dict:
    """
    Wrapper around run_analysis_pipeline with error handling.
    Catches OpenAI errors and marks the resume as failed.
    Returns {"analysis": Analysis} on success or raises HTTPException-compatible dict.
    """
    try:
        analysis = await run_analysis_pipeline(resume_id, db)
        return {"analysis": analysis}

    except openai.RateLimitError as exc:
        logger.warning("OpenAI rate limit hit for resume %s: %s", resume_id, exc)
        await _mark_failed(resume_id, db)
        raise _AnalysisError("RATE_LIMIT", "OpenAI rate limit reached. Please try again later.")

    except openai.APITimeoutError as exc:
        logger.warning("OpenAI timeout for resume %s: %s", resume_id, exc)
        await _mark_failed(resume_id, db)
        raise _AnalysisError("API_TIMEOUT", "OpenAI API timed out. Please try again.")

    except openai.APIError as exc:
        logger.error("OpenAI API error for resume %s: %s", resume_id, exc)
        await _mark_failed(resume_id, db)
        raise _AnalysisError("OPENAI_ERROR", "An error occurred with the AI service.")

    except Exception as exc:
        logger.exception("Unexpected error during analysis of resume %s: %s", resume_id, exc)
        await _mark_failed(resume_id, db)
        raise _AnalysisError("ANALYSIS_FAILED", "Analysis failed due to an unexpected error.")


async def _mark_failed(resume_id: UUID, db: AsyncSession) -> None:
    result = await db.execute(select(Resume).where(Resume.id == resume_id))
    resume = result.scalar_one_or_none()
    if resume:
        resume.status = ResumeStatus.failed
        await db.flush()


class _AnalysisError(Exception):
    """Internal error carrier for analysis failures."""
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)
