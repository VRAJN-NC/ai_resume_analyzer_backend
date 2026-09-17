from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Nested analysis sub-models (used in AnalysisOut)
# ---------------------------------------------------------------------------

class GrammarIssue(BaseModel):
    section: str
    original_text: str
    issue: str
    suggestion: str


class SectionFeedback(BaseModel):
    section: str
    feedback: str


class RecommendedRole(BaseModel):
    role_title: str
    match_percent: float
    reason: str


# ---------------------------------------------------------------------------
# Analysis response (GET /resumes/{id}/analysis)
# ---------------------------------------------------------------------------

class AnalysisOut(BaseModel):
    ats_score: float
    formatting_score: float
    keyword_score: float
    missing_keywords: List[str]
    matched_keywords: List[str]
    grammar_issues: List[GrammarIssue]
    section_feedback: List[SectionFeedback]
    extracted_skills: List[str]
    missing_skills: List[str]
    recommended_roles: List[RecommendedRole]

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Resume responses
# ---------------------------------------------------------------------------

class ResumeUploadResponse(BaseModel):
    resume_id: UUID
    status: str


class ResumeOut(BaseModel):
    id: UUID
    filename: str
    uploaded_at: datetime
    status: str
    analysis: Optional[AnalysisOut] = None

    model_config = {"from_attributes": True}


class ResumeListResponse(BaseModel):
    resumes: List[ResumeOut]


class DeleteResponse(BaseModel):
    success: bool
