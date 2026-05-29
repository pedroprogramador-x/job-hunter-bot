import logging
from datetime import datetime, timezone
import requests

logger = logging.getLogger(__name__)

# A Gupy migrou do endpoint público portal.gupy.io/api para este BFF interno
_API_URL = "https://employability-portal.gupy.io/api/v1/jobs"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://portal.gupy.io/",
    "Origin": "https://portal.gupy.io",
}
_SEARCH_TERMS = [
    "python",
    "fastapi",
    "backend",
    "estagio tecnologia",
    "desenvolvedor junior",
    "automacao",
    "django",
    "flask",
]
_BASE_PARAMS = {
    "workplaceType": "remote",
    "limit": 20,
    "sortBy": "publishedDate",
}


def _is_application_open(job: dict) -> bool:
    deadline = job.get("applicationDeadline")
    if not deadline:
        return True
    try:
        dl = datetime.fromisoformat(deadline)
        now = datetime.now(tz=timezone.utc) if dl.tzinfo else datetime.now()
        return dl >= now
    except ValueError:
        return True


def _parse_job(job: dict) -> dict:
    city = job.get("city") or ""
    state = job.get("state") or ""
    if city and state:
        location = f"{city}, {state}"
    else:
        location = city or state or ""

    return {
        "id": "gupy_" + str(job.get("id", "")),
        "source": "Gupy",
        "title": job.get("name", ""),
        "company": job.get("careerPageName", ""),
        "location": location,
        "workplace_type": job.get("workplaceType", ""),
        "job_type": job.get("type", ""),
        "url": job.get("jobUrl", ""),
        "published_at": job.get("publishedDate", ""),
        "applications_open": _is_application_open(job),
    }


def _fetch_term(term: str) -> list[dict]:
    """Busca vagas para um único termo. Retorna lista vazia em caso de erro."""
    params = {**_BASE_PARAMS, "jobName": term}
    try:
        response = requests.get(_API_URL, params=params, headers=_HEADERS, timeout=15)
        response.raise_for_status()
        data = response.json()
    except ValueError as exc:
        logger.error("Gupy: JSON inválido para termo '%s': %s", term, exc)
        return []
    except requests.RequestException as exc:
        logger.error("Gupy: erro de rede para termo '%s': %s", term, exc)
        return []
    return data.get("data") or []


def fetch_jobs(params: dict | None = None) -> list[dict]:
    terms = _SEARCH_TERMS
    # Permite sobrescrever tudo via params legado (retrocompatibilidade)
    if params and "jobName" in params:
        terms = [params["jobName"]]

    seen_ids: set[str] = set()
    jobs: list[dict] = []

    for term in terms:
        for raw in _fetch_term(term):
            parsed = _parse_job(raw)
            if not parsed["id"] or parsed["id"] == "gupy_":
                continue
            if parsed["id"] not in seen_ids:
                seen_ids.add(parsed["id"])
                jobs.append(parsed)

    logger.info("Gupy: %d vagas únicas em %d termos", len(jobs), len(terms))
    return jobs


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    results = fetch_jobs()
    print(f"\nTotal de vagas encontradas: {len(results)}\n")
    for job in results:
        status = "aberta" if job["applications_open"] else "fechada"
        print(f"  [{status}] {job['title']} - {job['company']} ({job['location'] or 'remoto'})")
