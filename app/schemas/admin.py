from datetime import date
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr


class AdminUserOut(BaseModel):
    id: UUID
    name: str
    email: EmailStr
    role: str
    created_at: str

    model_config = {"from_attributes": True}


class AdminResumeOut(BaseModel):
    id: UUID
    filename: str
    status: str
    uploaded_at: str
    user_id: UUID
    user_name: str
    user_email: str

    model_config = {"from_attributes": True}


class UploadsPerDay(BaseModel):
    date: str
    count: int


class AnalyticsOut(BaseModel):
    total_users: int
    total_resumes: int
    avg_ats_score: Optional[float]
    uploads_by_day: List[UploadsPerDay]
