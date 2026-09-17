"""Grammar tool: flags syntax errors, weak/passive verbs, and returns suggestions."""
from __future__ import annotations

from typing import List

from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from app.core.config import get_settings

settings = get_settings()


class GrammarIssueItem(BaseModel):
    section: str = Field(description="Resume section where the issue was found (e.g. Experience).")
    original_text: str = Field(description="The original problematic text snippet.")
    issue: str = Field(description="Brief description of the grammar or style issue.")
    suggestion: str = Field(description="Improved replacement text or advice.")


class SectionFeedbackItem(BaseModel):
    section: str = Field(description="Name of the resume section.")
    feedback: str = Field(description="Qualitative feedback about this section.")


class GrammarToolOutput(BaseModel):
    grammar_issues: List[GrammarIssueItem] = Field(
        description="List of grammar, style, and language issues found."
    )
    section_feedback: List[SectionFeedbackItem] = Field(
        description="High-level qualitative feedback per section."
    )


@tool
async def grammar_tool(resume_text: str) -> dict:
    """
    Analyse resume text for grammar issues, weak/passive verbs, and provide
    per-section qualitative feedback. Returns grammar_issues and section_feedback.
    """
    llm = ChatOpenAI(
        model="gpt-4o",
        api_key=settings.openai_api_key,
        temperature=0,
    ).with_structured_output(GrammarToolOutput)

    prompt = f"""You are an expert resume editor and career coach.
Analyse the following resume text and return:

1. grammar_issues: Up to 10 specific grammar, spelling, punctuation, passive voice, or weak verb issues.
   For each: identify the section, the original text, the issue type, and a suggested fix.
2. section_feedback: For each resume section (Summary, Experience, Education, Skills, etc.),
   provide 1-2 sentences of qualitative feedback on clarity, impact, and professionalism.

Focus on:
- Passive voice ("was responsible for" -> "Led", "Managed")
- Weak openers ("Helped with", "Assisted in")
- Missing quantification of achievements
- Spelling and grammar errors
- Inconsistent tense (past tense for past roles, present for current)

Resume text:
---
{resume_text[:8000]}
---"""

    result: GrammarToolOutput = await llm.ainvoke(prompt)
    return result.model_dump()
