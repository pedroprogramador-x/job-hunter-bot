"""Deduplicação determinística das vagas coletadas no mesmo ciclo."""

from collections.abc import Iterable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_TRACKING_QUERY_KEYS = {
    "jobboardsource",
    "ref",
    "refid",
    "trackingid",
    "trk",
}


def canonicalize_job_url(value: object) -> str:
    """Remove diferenças cosméticas sem alterar a identidade da vaga."""
    raw_url = str(value or "").strip()
    if not raw_url:
        return ""

    try:
        parts = urlsplit(raw_url)
    except ValueError:
        return raw_url

    if not parts.netloc:
        return raw_url.rstrip("/")

    kept_query = [
        (key, item)
        for key, item in parse_qsl(parts.query, keep_blank_values=True)
        if key.casefold() not in _TRACKING_QUERY_KEYS
        and not key.casefold().startswith("utm_")
    ]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit(
        (
            parts.scheme.casefold(),
            parts.netloc.casefold(),
            path,
            urlencode(sorted(kept_query)),
            "",
        )
    )


def job_identity_keys(job: dict) -> tuple[str, ...]:
    """Retorna ID e URL quando disponíveis, ou um fallback conservador."""
    keys: list[str] = []
    job_id = str(job.get("id") or "").strip()
    if job_id:
        keys.append(f"id:{job_id}")

    canonical_url = canonicalize_job_url(job.get("url"))
    if canonical_url:
        keys.append(f"url:{canonical_url}")

    if keys:
        return tuple(keys)

    fallback_values = tuple(
        " ".join(str(job.get(field) or "").casefold().split())
        for field in ("source", "company", "title", "location")
    )
    if any(fallback_values):
        return ("fallback:" + "|".join(fallback_values),)
    return ()


def collect_identity_keys(jobs: Iterable[dict]) -> set[str]:
    return {key for job in jobs for key in job_identity_keys(job)}


def deduplicate_jobs(jobs: Iterable[dict]) -> list[dict]:
    """Preserva a primeira ocorrência e elimina IDs ou URLs repetidos."""
    unique_jobs: list[dict] = []
    seen: set[str] = set()

    for job in jobs:
        keys = job_identity_keys(job)
        if keys and any(key in seen for key in keys):
            continue
        seen.update(keys)
        unique_jobs.append(job)

    return unique_jobs
