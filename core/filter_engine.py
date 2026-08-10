# Motor de filtragem de vagas por senioridade, localização e relevância técnica

import re
import unicodedata

_DESCRIPTION_TECH_SCORE_CAP = 5.0

_SENIORITY_PATTERNS = [
    re.compile(pattern)
    for pattern in (
        r"\bpleno\b",
        r"(?<!\w)pl\.?(?!\w)",
        r"\bsenior\b",
        r"(?<!\w)sr\.?(?!\w)",
        r"\bespecialista\b",
        r"\bspecialist\b",
        r"\blead\b",
        r"\bstaff\b",
        r"\bprincipal\b",
        r"\barchitect\b",
        r"\barquiteto\b",
        r"\bcoordinator\b",
        r"\bcoordenador\b",
        r"\bmanager\b",
        r"\bgerente\b",
    )
]
_PL_SQL_PATTERN = re.compile(r"(?<!\w)pl\s*/\s*sql(?!\w)")

_REMOTE_PATTERN = re.compile(
    r"\b(?:remoto|remote|home[ -]office|anywhere\s+in\s+brazil|brazil\s+remote)\b"
)
_LOCAL_WORKPLACE_PATTERN = re.compile(
    r"\b(?:presencial|hibrido|hybrid|on[ -]?site|onsite)\b"
)
_ALAGOAS_PATTERN = re.compile(
    r"\bmaceio\b|\balagoas\b|(?:^|[,/\-]\s*)al(?:\s|$)"
)

_INTERNSHIP_PATTERN = re.compile(r"\b(?:estagio|estagiari[oa]|intern|internship)\b")
_JUNIOR_PATTERN = re.compile(r"\b(?:junior|jr\.?|entry\s+level)\b")
_ROLE_PATTERN = re.compile(
    r"\b(?:backend|back\s*end|software\s+developer|software\s+engineer|"
    r"desenvolvedor(?:a)?\s+de\s+software|desenvolvimento\s+de\s+software|"
    r"engenharia\s+de\s+software)\b"
)

_TECH_CATEGORIES: list[tuple[re.Pattern[str], float]] = [
    (re.compile(r"\bpython\b"), 3.0),
    (
        re.compile(
            r"\b(?:automacao|api(?:s)?|integracao|integracoes|rpa)\b"
        ),
        3.0,
    ),
    (re.compile(r"\b(?:fastapi|django|flask)\b"), 2.0),
    (
        re.compile(
            r"\b(?:full\s*stack|qa\s+automation|sistemas?|dados|data|etl)\b"
        ),
        2.0,
    ),
    (re.compile(r"\b(?:rest|sql|postgresql)\b"), 2.0),
    (re.compile(r"\b(?:java|javascript)\b"), 1.5),
    (re.compile(r"\b(?:git|docker|cloud|aws|azure|gcp)\b"), 1.0),
]

_TECHNICAL_RELEVANCE_PATTERN = re.compile(
    r"\b(?:python|java|javascript|typescript|backend|back\s*end|fastapi|django|"
    r"flask|api(?:s)?|rest|integracao|integracoes|automacao|rpa|programacao|"
    r"programador|desenvolvedor|developer|software\s+engineer|"
    r"desenvolvimento\s+de\s+software|engenharia\s+de\s+software|full\s*stack|"
    r"qa\s+automation|testes?\s+automatizados?|sistemas?|dados|data|etl|sql|"
    r"postgresql|scraping|scripts?)\b"
)
_PROGRAMMING_PATTERN = re.compile(
    r"\b(?:python|java|javascript|typescript|programacao|programador|"
    r"desenvolvedor|developer|software|api(?:s)?|automacao|integracao|"
    r"integracoes|scripts?)\b"
)
_SUPPORT_PATTERN = re.compile(r"\b(?:suporte|support)\b")
_NON_TECH_TITLE_PATTERN = re.compile(
    r"\b(?:recrutamento|recursos\s+humanos|vendas|comercial|sdr|financeiro|"
    r"contabil|marketing|designer\s+grafico|operador\s+de\s+caixa)\b"
)

_REQUIRED_EXPERIENCE_PATTERNS = [
    re.compile(pattern)
    for pattern in (
        (
            r"(?:minimo|minima)(?:\s+de)?\s*(\d+)\s*\+?\s*anos?"
            r"(?:\s+de)?\s+experiencia"
        ),
        r"experiencia\s+(?:minima|minimo)(?:\s+de)?\s*(\d+)\s*\+?\s*anos?",
        r"(\d+)\s*\+\s*anos?(?:\s+de)?\s+experiencia",
        (
            r"(?:pelo\s+menos|ao\s+menos)\s*(\d+)\s*anos?"
            r"(?:\s+de)?\s+experiencia"
        ),
        r"at\s+least\s+(\d+)\s+years?(?:\s+of)?\s+experience",
        r"minimum(?:\s+of)?\s+(\d+)\s+years?(?:\s+of)?\s+experience",
        r"(\d+)\s*\+\s*years?(?:\s+(?:of\s+)?experience|\s+required)",
        (
            r"(\d+)\s+anos?\s+de\s+experiencia\s+"
            r"(?:obrigatoria|obrigatorio|necessaria|necessario|required)"
        ),
    )
]


def normalize_text(value: object) -> str:
    """Normaliza casing, acentos, espaços e variações de travessão."""
    text = unicodedata.normalize("NFKD", str(value or "").casefold())
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", text).strip()


def normalize_title(job: dict) -> str:
    return normalize_text(job.get("title", ""))


def normalize_location(job: dict) -> str:
    return normalize_text(job.get("location", ""))


def normalize_workplace(job: dict) -> str:
    return normalize_text(job.get("workplace_type", ""))


def normalize_description(job: dict) -> str:
    return normalize_text(job.get("description", ""))


def _has_incompatible_seniority(title: str) -> bool:
    title_without_pl_sql = _PL_SQL_PATTERN.sub("", title)
    return any(pattern.search(title_without_pl_sql) for pattern in _SENIORITY_PATTERNS)


def _is_alagoas_location(location: str) -> bool:
    return bool(_ALAGOAS_PATTERN.search(location))


def _is_remote(job: dict) -> bool:
    workplace = normalize_workplace(job)
    title_location = f"{normalize_title(job)} {normalize_location(job)}"
    return workplace in {"remote", "remoto"} or bool(
        _REMOTE_PATTERN.search(f"{workplace} {title_location}")
    )


def _has_incompatible_location(job: dict) -> bool:
    location = normalize_location(job)
    workplace = normalize_workplace(job)
    title_location = f"{normalize_title(job)} {location}"

    if _is_alagoas_location(location):
        return False
    if _LOCAL_WORKPLACE_PATTERN.search(workplace):
        return True
    if _LOCAL_WORKPLACE_PATTERN.search(title_location):
        return True
    return not _is_remote(job)


def _required_experience_years(description: str) -> int | None:
    years = [
        int(match.group(1))
        for pattern in _REQUIRED_EXPERIENCE_PATTERNS
        if (match := pattern.search(description))
    ]
    return max(years) if years else None


def _has_technical_relevance(job: dict) -> bool:
    title = normalize_title(job)
    description = normalize_description(job)
    if _NON_TECH_TITLE_PATTERN.search(title) and not _TECHNICAL_RELEVANCE_PATTERN.search(
        title
    ):
        return False
    return bool(_TECHNICAL_RELEVANCE_PATTERN.search(f"{title} {description}"))


def is_job_blocked(job: dict, *, final: bool = True) -> bool:
    """Aplica hard blocks de título, localização e requisitos obrigatórios."""
    if _has_incompatible_seniority(normalize_title(job)):
        return True
    if _has_incompatible_location(job):
        return True
    if not final:
        return False

    description = normalize_description(job)
    required_years = _required_experience_years(description)
    if required_years is not None and required_years >= 3:
        return True
    return not _has_technical_relevance(job)


def _score_job(job: dict) -> float:
    title = normalize_title(job)
    description = normalize_description(job)
    score = 0.0

    if _INTERNSHIP_PATTERN.search(title):
        score += 8.0
    elif _JUNIOR_PATTERN.search(title):
        score += 7.0

    if _ROLE_PATTERN.search(title):
        score += 4.0

    description_score = 0.0
    for pattern, weight in _TECH_CATEGORIES:
        if pattern.search(title):
            score += weight
        elif pattern.search(description):
            description_score += weight
    score += min(description_score, _DESCRIPTION_TECH_SCORE_CAP)

    if _is_remote(job) or _is_alagoas_location(normalize_location(job)):
        score += 4.0

    combined = f"{title} {description}"
    if _SUPPORT_PATTERN.search(title) and not _PROGRAMMING_PATTERN.search(combined):
        score -= 2.0

    if _required_experience_years(description) == 2:
        score -= 2.0

    return score


def filter_jobs(
    jobs: list[dict],
    min_score: float = 10.0,
    *,
    final: bool = True,
) -> list[tuple[dict, float]]:
    """Bloqueia vagas incompatíveis e retorna as aprovadas por score."""
    passing: list[tuple[dict, float]] = []
    for job in jobs:
        if is_job_blocked(job, final=final):
            continue
        score = _score_job(job)
        if score >= min_score:
            passing.append((job, score))
    passing.sort(key=lambda item: item[1], reverse=True)
    return passing
