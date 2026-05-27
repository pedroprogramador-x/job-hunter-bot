import hashlib
import logging

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# f_WT=2 → remoto | f_E=1,2 → estágio e júnior (entry/associate)
_SEARCH_URL = (
    "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
    "?keywords=python+junior&location=Brazil&f_WT=2&f_E=1%2C2&start=0"
)
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


def fetch_jobs() -> list[dict]:
    try:
        response = requests.get(_SEARCH_URL, headers=_HEADERS, timeout=15)
        if response.status_code in (429, 999):
            logger.warning(
                "LinkedIn bloqueou o acesso (%d). "
                "Retornando lista vazia.",
                response.status_code,
            )
            return []
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.error("LinkedIn: erro de rede — %s", exc)
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    cards = soup.select("li div.job-search-card")

    if not cards:
        # Fallback: tenta com seletor mais genérico
        cards = soup.select("li div.base-search-card")

    if not cards:
        logger.warning("LinkedIn: nenhum card encontrado no HTML retornado.")
        return []

    seen_ids: set[str] = set()
    jobs: list[dict] = []

    for card in cards:
        # URL canônica via <a class="base-card__full-link">
        link_el = card.select_one("a.base-card__full-link")
        url = link_el["href"].split("?")[0] if link_el and link_el.get("href") else ""
        if not url:
            continue

        job_id = _make_id(url)
        if job_id in seen_ids:
            continue
        seen_ids.add(job_id)

        # Título — <h3 class="base-search-card__title">
        title_el = card.select_one("h3.base-search-card__title")
        title = _clean(title_el.get_text()) if title_el else ""

        # Empresa — <h4 class="base-search-card__subtitle"> ou link aninhado
        company_el = card.select_one("h4.base-search-card__subtitle")
        company = _clean(company_el.get_text()) if company_el else ""

        # Localização — <span class="job-search-card__location">
        location_el = card.select_one("span.job-search-card__location")
        location = _clean(location_el.get_text()) if location_el else ""

        # Data de publicação — <time datetime="...">
        time_el = card.select_one("time")
        published_at = time_el.get("datetime", "") if time_el else ""

        jobs.append({
            "id": job_id,
            "source": "LinkedIn",
            "title": title,
            "company": company,
            "location": location,
            "workplace_type": "remote",  # f_WT=2 garante remoto upstream
            "job_type": "unknown",
            "url": url,
            "published_at": published_at,
            "applications_open": True,
        })

    logger.info("LinkedIn: %d vagas encontradas.", len(jobs))
    return jobs


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    results = fetch_jobs()
    print(f"\nTotal de vagas encontradas: {len(results)}\n")
    for job in results:
        print(f"  [{job['workplace_type']}] {job['title']} - {job['company']} ({job['location']})")
