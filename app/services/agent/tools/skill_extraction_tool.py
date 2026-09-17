"""Skill extraction tool: extracts a normalised skill list from resume text."""
from __future__ import annotations

from typing import List

from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from app.core.config import get_settings

settings = get_settings()


class SkillExtractionOutput(BaseModel):
    extracted_skills: List[str] = Field(
        description="List of technical and soft skills extracted from the resume."
    )
    missing_skills: List[str] = Field(
        default_factory=list,
        description="Common professional skills that appear absent from the resume.",
    )


@tool
async def skill_extraction_tool(resume_text: str) -> dict:
    """
    Extract a normalised list of skills from the given resume text.
    Returns extracted_skills and missing_skills.
    """
    llm = ChatOpenAI(
        model="gpt-4o",
        api_key=settings.openai_api_key,
        temperature=0,
    ).with_structured_output(SkillExtractionOutput)

    prompt = f"""You are an expert resume parser. Analyse the following resume text and:
1. Extract ALL technical skills, tools, frameworks, languages, and soft skills explicitly mentioned.
2. Identify up to 5 common professional skills that appear to be MISSING for a senior professional.

Resume text:
---
{resume_text[:8000]}
---

Return a JSON object with 'extracted_skills' (list of strings) and 'missing_skills' (list of strings)."""

    result: SkillExtractionOutput = await llm.ainvoke(prompt)
    return result.model_dump()
