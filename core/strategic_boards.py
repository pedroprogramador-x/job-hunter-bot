"""Configuração central das fontes estratégicas de vagas."""

from dataclasses import dataclass

from core.company_watchlist import CompanyCategory, CompanyPriority


@dataclass(frozen=True)
class GupyStrategicBoard:
    canonical_name: str
    slug: str
    company_id: int
    category: CompanyCategory
    priority: CompanyPriority
    active: bool = True


GUPY_STRATEGIC_BOARDS: tuple[GupyStrategicBoard, ...] = (
    GupyStrategicBoard(
        canonical_name="It4us Cyber Security",
        slug="vemprait4us",
        company_id=759,
        category="remote",
        priority="very_high",
    ),
    GupyStrategicBoard(
        canonical_name="Hand Talk by Sorenson",
        slug="handtalk",
        company_id=82339,
        category="maceio",
        priority="very_high",
    ),
    GupyStrategicBoard(
        canonical_name="Trakto",
        slug="trakto",
        company_id=51988,
        category="maceio",
        priority="very_high",
    ),
)
