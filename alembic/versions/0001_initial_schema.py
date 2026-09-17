"""initial schema

Revision ID: 0001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column(
            "role",
            sa.Enum("user", "admin", name="userrole"),
            nullable=False,
            server_default="user",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    # --- job_roles ---
    op.create_table(
        "job_roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("required_skills", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("title"),
    )

    # --- resumes ---
    op.create_table(
        "resumes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("filename", sa.String(512), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("pending", "analyzed", "failed", name="resumestatus"),
            nullable=False,
            server_default="pending",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_resumes_user_id"), "resumes", ["user_id"])

    # --- analyses ---
    op.create_table(
        "analyses",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("resume_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ats_score", sa.Float(), nullable=True),
        sa.Column("formatting_score", sa.Float(), nullable=True),
        sa.Column("keyword_score", sa.Float(), nullable=True),
        sa.Column("matched_keywords", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("missing_keywords", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("grammar_issues", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("section_feedback", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("extracted_skills", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("missing_skills", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["resume_id"], ["resumes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("resume_id"),
    )
    op.create_index(op.f("ix_analyses_resume_id"), "analyses", ["resume_id"])

    # --- recommendations ---
    op.create_table(
        "recommendations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("analysis_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_role_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("match_percent", sa.Float(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["analysis_id"], ["analyses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_role_id"], ["job_roles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("analysis_id", "job_role_id", name="uq_recommendation_analysis_role"),
    )
    op.create_index(op.f("ix_recommendations_analysis_id"), "recommendations", ["analysis_id"])

    # --- Seed job_roles ---
    op.execute("""
        INSERT INTO job_roles (id, title, required_skills, description) VALUES
        (gen_random_uuid(), 'Backend Engineer', '["Python", "FastAPI", "PostgreSQL", "REST API", "Docker", "SQL", "Git"]', 'Builds and maintains server-side applications and APIs.'),
        (gen_random_uuid(), 'Frontend Engineer', '["JavaScript", "TypeScript", "React", "HTML", "CSS", "REST API", "Git"]', 'Develops user-facing web applications.'),
        (gen_random_uuid(), 'Full Stack Engineer', '["Python", "JavaScript", "React", "FastAPI", "PostgreSQL", "Docker", "Git"]', 'Works across both backend and frontend systems.'),
        (gen_random_uuid(), 'Data Scientist', '["Python", "Machine Learning", "Pandas", "NumPy", "SQL", "Scikit-learn", "Statistics"]', 'Analyzes data and builds predictive models.'),
        (gen_random_uuid(), 'Machine Learning Engineer', '["Python", "TensorFlow", "PyTorch", "Machine Learning", "Docker", "SQL", "MLOps"]', 'Designs and deploys ML models at scale.'),
        (gen_random_uuid(), 'DevOps Engineer', '["Docker", "Kubernetes", "CI/CD", "AWS", "Terraform", "Linux", "Git", "Bash"]', 'Manages infrastructure, deployment pipelines, and reliability.'),
        (gen_random_uuid(), 'Cloud Engineer', '["AWS", "Azure", "GCP", "Terraform", "Docker", "Kubernetes", "Networking"]', 'Designs and manages cloud infrastructure.'),
        (gen_random_uuid(), 'Data Engineer', '["Python", "SQL", "Apache Spark", "Airflow", "AWS", "PostgreSQL", "ETL"]', 'Builds data pipelines and infrastructure.'),
        (gen_random_uuid(), 'Security Engineer', '["Cybersecurity", "Python", "Linux", "Networking", "SIEM", "Penetration Testing", "AWS"]', 'Protects systems from vulnerabilities and threats.'),
        (gen_random_uuid(), 'Mobile Engineer', '["React Native", "Swift", "Kotlin", "JavaScript", "REST API", "Git", "TypeScript"]', 'Develops iOS and Android mobile applications.')
    """)


def downgrade() -> None:
    op.drop_table("recommendations")
    op.drop_table("analyses")
    op.drop_table("resumes")
    op.drop_table("job_roles")
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS userrole")
    op.execute("DROP TYPE IF EXISTS resumestatus")
