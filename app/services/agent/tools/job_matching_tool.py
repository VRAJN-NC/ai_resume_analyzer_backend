"""Job matching tool: compares extracted skills against job_roles table."""
from __future__ import annotations

from typing import List
from uuid import UUID

from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import JobRole

settings = get_settings()


class RoleReasonOutput(BaseModel):
    reason: str = Field(description="A 1-2 sentence human-readable explanation of why this role matches.")


class RecommendedRoleItem(BaseModel):
    role_title: str
    match_percent: float
    reason: str


class JobMatchingOutput(BaseModel):
    recommended_roles: List[RecommendedRoleItem]


async def _generate_reason(
    role_title: str,
    matched: List[str],
    missing: List[str],
    match_percent: float,
) -> str:
    """Ask GPT-4o to produce one human-readable reason string for a role match."""
    llm = ChatOpenAI(
        model="gpt-4o",
        api_key=settings.openai_api_key,
        temperature=0.3,
    ).with_structured_output(RoleReasonOutput)

    prompt = f"""A resume has been matched to the job role "{role_title}" with a {match_percent:.0f}% skill match.

Matched skills: {", ".join(matched) if matched else "none"}
Missing skills: {", ".join(missing) if missing else "none"}

Write 1-2 sentences explaining why this role is a good fit (or partial fit) based on these matched/missing skills.
Be specific and professional."""

    result: RoleReasonOutput = await llm.ainvoke(prompt)
    return result.reason


async def run_job_matching(
    extracted_skills: List[str],
    db: AsyncSession,
    top_n: int = 5,
) -> JobMatchingOutput:
    """
    Core matching logic (not a LangChain tool decorator — called directly by the agent).
    Queries job_roles from DB, computes match_percent in Python, calls LLM only for reason.
    """
    result = await db.execute(select(JobRole))
    job_roles = result.scalars().all()

    if not job_roles:
        return JobMatchingOutput(recommended_roles=[])

    # Normalise extracted skills to lowercase for comparison
    candidate_skills_lower = {s.strip().lower() for s in extracted_skills}

    scored: list[tuple[float, JobRole, list[str], list[str]]] = []

    for role in job_roles:
        required: List[str] = role.required_skills or []
        if not required:
            continue

        required_lower = [r.strip().lower() for r in required]
        matched = [r for r in required if r.strip().lower() in candidate_skills_lower]
        missing = [r for r in required if r.strip().lower() not in candidate_skills_lower]
        match_percent = (len(matched) / len(required)) * 100.0
        scored.append((match_percent, role, matched, missing))

    # Sort by match_percent descending, take top N with > 0% match
    scored.sort(key=lambda x: x[0], reverse=True)
    top = [(mp, role, m, mis) for mp, role, m, mis in scored if mp > 0][:top_n]

    recommended: List[RecommendedRoleItem] = []
    for match_percent, role, matched, missing in top:
        reason = await _generate_reason(role.title, matched, missing, match_percent)
        recommended.append(
            RecommendedRoleItem(
                role_title=role.title,
                match_percent=round(match_percent, 1),
                reason=reason,
            )
        )

    return JobMatchingOutput(recommended_roles=recommended)
