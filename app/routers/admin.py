from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import require_admin
from app.db.models import Analysis, Resume, User
from app.db.session import get_db
from app.schemas.admin import AdminResumeOut, AdminUserOut, AnalyticsOut, UploadsPerDay

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users")
async def list_users(
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    users = result.scalars().all()
    return {
        "users": [
            AdminUserOut(
                id=u.id,
                name=u.name,
                email=u.email,
                role=u.role.value,
                created_at=u.created_at.isoformat(),
            )
            for u in users
        ]
    }


@router.get("/resumes")
async def list_all_resumes(
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Resume).options(selectinload(Resume.user)).order_by(Resume.uploaded_at.desc())
    )
    resumes = result.scalars().all()
    return {
        "resumes": [
            AdminResumeOut(
                id=r.id,
                filename=r.filename,
                status=r.status.value,
                uploaded_at=r.uploaded_at.isoformat(),
                user_id=r.user_id,
                user_name=r.user.name,
                user_email=r.user.email,
            )
            for r in resumes
        ]
    }


@router.get("/analytics", response_model=AnalyticsOut)
async def get_analytics(
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    # --- total_users ---
    total_users_row = await db.execute(select(func.count(User.id)))
    total_users: int = total_users_row.scalar_one()

    # --- total_resumes ---
    total_resumes_row = await db.execute(select(func.count(Resume.id)))
    total_resumes: int = total_resumes_row.scalar_one()

    # --- avg_ats_score ---
    avg_row = await db.execute(select(func.avg(Analysis.ats_score)))
    avg_ats_score: Optional[float] = avg_row.scalar_one()
    if avg_ats_score is not None:
        avg_ats_score = round(avg_ats_score, 2)

    # --- uploads_by_day (last 30 days, SQL GROUP BY DATE_TRUNC) ---
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    uploads_rows = await db.execute(
        select(
            func.date_trunc("day", Resume.uploaded_at).label("day"),
            func.count(Resume.id).label("count"),
        )
        .where(Resume.uploaded_at >= thirty_days_ago)
        .group_by(text("day"))
        .order_by(text("day"))
    )
    uploads_by_day = [
        UploadsPerDay(date=row.day.date().isoformat(), count=row.count)
        for row in uploads_rows
    ]

    return AnalyticsOut(
        total_users=total_users,
        total_resumes=total_resumes,
        avg_ats_score=avg_ats_score,
        uploads_by_day=uploads_by_day,
    )
