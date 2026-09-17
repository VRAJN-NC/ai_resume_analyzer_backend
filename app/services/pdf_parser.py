"""PDF text extraction and section splitting utilities."""
from __future__ import annotations

import io
import re
from typing import Optional

import pdfplumber
import pypdf


# ---------------------------------------------------------------------------
# Known resume section headers (ordered by typical appearance)
# ---------------------------------------------------------------------------

_SECTION_PATTERNS = [
    "summary", "objective", "profile", "about",
    "experience", "work experience", "employment", "work history",
    "education", "academic",
    "skills", "technical skills", "core competencies",
    "projects", "personal projects",
    "certifications", "certificates", "licenses",
    "awards", "achievements", "honors",
    "publications", "research",
    "languages",
    "volunteer", "volunteering",
    "references",
]

_SECTION_REGEX = re.compile(
    r"^(" + "|".join(re.escape(s) for s in _SECTION_PATTERNS) + r")\s*[:\-]?\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def extract_text(file_bytes: bytes) -> str:
    """
    Extract plain text from a PDF byte stream.
    Tries pdfplumber first (better layout); falls back to pypdf.
    """
    text = _extract_with_pdfplumber(file_bytes)
    if not text or len(text.strip()) < 50:
        text = _extract_with_pypdf(file_bytes)
    return text or ""


def _extract_with_pdfplumber(file_bytes: bytes) -> Optional[str]:
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
        return "\n".join(pages).strip()
    except Exception:
        return None


def _extract_with_pypdf(file_bytes: bytes) -> Optional[str]:
    try:
        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(pages).strip()
    except Exception:
        return None


def split_sections(text: str) -> dict[str, str]:
    """
    Best-effort split of resume text into named sections.
    Returns a dict mapping section_name -> section_content.
    Keys are normalised to title case (e.g. "Work Experience").
    An "header" key captures everything before the first recognised section.
    """
    sections: dict[str, str] = {}
    matches = list(_SECTION_REGEX.finditer(text))

    if not matches:
        return {"full_text": text}

    # Content before the first section header
    pre = text[: matches[0].start()].strip()
    if pre:
        sections["header"] = pre

    for i, match in enumerate(matches):
        section_name = match.group(1).strip().title()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[start:end].strip()
        sections[section_name] = content

    return sections
