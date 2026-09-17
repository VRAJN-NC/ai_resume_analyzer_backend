"""ATS scoring tool: scores keyword coverage and resume formatting."""
from __future__ import annotations

from typing import List

from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from app.core.config import get_settings

settings = get_settings()


class ATSScoringOutput(BaseModel):
    ats_score: float = Field(ge=0, le=100, description="Overall ATS compatibility score (0-100).")
    formatting_score: float = Field(ge=0, le=100, description="Resume formatting quality score (0-100).")
    keyword_score: float = Field(ge=0, le=100, description="Keyword coverage score (0-100).")
    matched_keywords: List[str] = Field(description="Industry-relevant keywords found in the resume.")
    missing_keywords: List[str] = Field(description="Important ATS keywords absent from the resume.")


@tool
async def ats_scoring_tool(resume_text: str, extracted_skills: List[str]) -> dict:
    """
    Score a resume for ATS compatibility.
    Returns ats_score, formatting_score, keyword_score, matched_keywords, missing_keywords.
    """
    llm = ChatOpenAI(
        model="gpt-4o",
        api_key=settings.openai_api_key,
        temperature=0,
    ).with_structured_output(ATSScoringOutput)

    skills_str = ", ".join(extracted_skills) if extracted_skills else "none detected"

    prompt = f"""You are an expert ATS (Applicant Tracking System) evaluator.
Analyse the resume below and provide:

1. ats_score (0-100): Overall ATS compatibility — considers keywords, formatting, structure, parsability.
2. formatting_score (0-100): Quality of formatting — clear sections, consistent bullet style, no tables/columns that break parsing.
3. keyword_score (0-100): How well the resume covers important industry keywords.
4. matched_keywords: List of important industry keywords FOUND in the resume.
5. missing_keywords: List of important ATS keywords that are MISSING but should be there.

Known extracted skills: {skills_str}

Resume text:
---
{resume_text[:8000]}
---

Be strict but fair. A score above 80 means the resume is well-optimised for ATS."""

    result: ATSScoringOutput = await llm.ainvoke(prompt)
    return result.model_dump()
