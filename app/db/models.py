import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class UserRole(str, enum.Enum):
    user = "user"
    admin = "admin"


class ResumeStatus(str, enum.Enum):
    pending = "pending"
    analyzed = "analyzed"
    failed = "failed"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.user)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    resumes = relationship("Resume", back_populates="user", cascade="all, delete-orphan")


class Resume(Base):
    __tablename__ = "resumes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = Column(String(512), nullable=False)
    raw_text = Column(Text, nullable=True)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    status = Column(Enum(ResumeStatus), nullable=False, default=ResumeStatus.pending)

    user = relationship("User", back_populates="resumes")
    analysis = relationship("Analysis", back_populates="resume", uselist=False, cascade="all, delete-orphan")


class Analysis(Base):
    __tablename__ = "analyses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    resume_id = Column(
        UUID(as_uuid=True),
        ForeignKey("resumes.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    ats_score = Column(Float, nullable=True)
    formatting_score = Column(Float, nullable=True)
    keyword_score = Column(Float, nullable=True)
    matched_keywords = Column(JSON, nullable=True, default=list)
    missing_keywords = Column(JSON, nullable=True, default=list)
    grammar_issues = Column(JSON, nullable=True, default=list)
    section_feedback = Column(JSON, nullable=True, default=list)
    extracted_skills = Column(JSON, nullable=True, default=list)
    missing_skills = Column(JSON, nullable=True, default=list)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    resume = relationship("Resume", back_populates="analysis")
    recommendations = relationship("Recommendation", back_populates="analysis", cascade="all, delete-orphan")


class JobRole(Base):
    __tablename__ = "job_roles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(255), nullable=False, unique=True)
    required_skills = Column(JSON, nullable=False, default=list)
    description = Column(Text, nullable=True)

    recommendations = relationship("Recommendation", back_populates="job_role")


class Recommendation(Base):
    __tablename__ = "recommendations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id = Column(
        UUID(as_uuid=True),
        ForeignKey("analyses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_role_id = Column(
        UUID(as_uuid=True),
        ForeignKey("job_roles.id", ondelete="CASCADE"),
        nullable=False,
    )
    match_percent = Column(Float, nullable=False)
    reason = Column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("analysis_id", "job_role_id", name="uq_recommendation_analysis_role"),
    )

    analysis = relationship("Analysis", back_populates="recommendations")
    job_role = relationship("JobRole", back_populates="recommendations")
