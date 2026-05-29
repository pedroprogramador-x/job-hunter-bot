import hashlib
import logging

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# f_WT=2 → remoto | f_E=1,2 → estágio e júnior (entry/associate)
_BASE_URL = (
    "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
    "?location=Brazil&f_WT=2&f_E=1%2C2&start=0"
)
_SEARCH_TERMS = [
    "python junior",
    "backend python",
    "fastapi developer",
    "estagio desenvolvimento",
    "automacao python",
]
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    "Referer": "https://www.linkedin.com/jobs/search/",
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "same-origin",
}


def _make_id(url: str) -> str:
    return "linkedin_" + hashlib.md5(url.encode()).hexdigest()[:12]


def _clean(text: str) -> str:
    return " ".join(text.split())


def _parse_cards(html: str, seen_ids: set[str]) -> list[dict]:
    """Extrai vagas do HTML retornado pelo LinkedIn, ignorando IDs já vistos."""
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("li div.job-search-card") or soup.select("li div.base-search-card")
    jobs = []
    for card in cards:
        link_el = card.select_one("a.base-card__full-link")
        url = link_el["href"].split("?")[0] if link_el and link_el.get("href") else ""
        if not url:
            continue
        job_id = _make_id(url)
        if job_id in seen_ids:
            continue
        seen_ids.add(job_id)

        title_el    = card.select_one("h3.base-search-card__title")
        company_el  = card.select_one("h4.base-search-card__subtitle")
        location_el = card.select_one("span.job-search-card__location")
        time_el     = card.select_one("time")

        jobs.append({
            "id":             job_id,
            "source":         "LinkedIn",
            "title":          _clean(title_el.get_text())    if title_el    else "",
            "company":        _clean(company_el.get_text())  if company_el  else "",
            "location":       _clean(location_el.get_text()) if location_el else "",
            "workplace_type": "remote",  # f_WT=2 garante remoto upstream
            "job_type":       "unknown",
            "url":            url,
            "published_at":   time_el.get("datetime", "") if time_el else "",
            "applications_open": True,
        })
    return jobs


def _fetch_term(term: str) -> str | None:
    """Faz a requisição para um termo. Retorna o HTML ou None em caso de erro."""
    url = f"{_BASE_URL}&keywords={requests.utils.quote(term)}"
    try:
        response = requests.get(url, headers=_HEADERS, timeout=15)
        if response.status_code in (429, 999):
            logger.warning("LinkedIn bloqueou o acesso (%d) para '%s'.", response.status_code, term)
            return None
        response.raise_for_status()
        return response.text
    except requests.RequestException as exc:
        logger.error("LinkedIn: erro de rede para termo '%s': %s", term, exc)
        return None


def fetch_jobs() -> list[dict]:
    seen_ids: set[str] = set()
    jobs: list[dict] = []

    for term in _SEARCH_TERMS:
        html = _fetch_term(term)
        if not html:
            continue
        new = _parse_cards(html, seen_ids)
        if not new:
            logger.warning("LinkedIn: nenhum card encontrado para '%s'.", term)
        jobs.extend(new)

    logger.info("LinkedIn: %d vagas únicas em %d termos.", len(jobs), len(_SEARCH_TERMS))
    return jobs


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    results = fetch_jobs()
    print(f"\nTotal de vagas encontradas: {len(results)}\n")
    for job in results:
        print(f"  [{job['workplace_type']}] {job['title']} - {job['company']} ({job['location']})")
