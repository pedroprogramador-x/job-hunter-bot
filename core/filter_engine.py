# Motor de filtragem de vagas por palavras-chave, localização e critérios configuráveis

_POSITIVE_WEIGHTS: list[tuple[str, float]] = [
    ("python", 3),
    ("fastapi", 2),
    ("django", 2),
    ("flask", 2),
    ("javascript", 1),
    ("typescript", 1),
    ("react", 1),
    ("node", 1),
    ("full stack", 2),
    ("fullstack", 2),
    ("backend", 2),
    ("back-end", 2),
    ("sql", 1),
    ("postgresql", 2),
    ("automacao", 3),
    ("automação", 3),
    ("rpa", 3),
    ("n8n", 2),
    ("make", 1),
    ("ia", 2),
    ("inteligencia artificial", 2),
    ("qa", 2),
    ("testes", 1),
    ("qualidade", 1),
    ("dados", 1),
    ("data", 1),
    ("estagio", 3),
    ("estágio", 3),
    ("junior", 2),
    ("júnior", 2),
    ("remoto", 2),
    ("remote", 2),
]

_NEGATIVE_WEIGHTS: list[tuple[str, float]] = [
    ("sênior", -5),
    ("senior", -5),
    ("pleno", -3),
    (".net", -3),
    ("c#", -3),
    ("presencial", -3),
    ("híbrido", -1),
    ("hibrido", -1),
    ("3 anos", -3),
    ("4 anos", -3),
    ("são paulo", -2),
    ("rio de janeiro", -2),
    ("belo horizonte", -2),
    ("curitiba", -2),
    ("porto alegre", -2),
    ("são leopoldo", -2),
    ("campinas", -2),
    # áreas não técnicas
    ("vendas", -4),
    ("recrutamento", -4),
    ("seleção", -4),
    ("selecao", -4),
    ("recursos humanos", -4),
    ("rh ", -4),
    ("comercial", -3),
    ("sdr", -4),
    ("atendimento", -3),
    ("suporte", -2),
    ("financeiro", -3),
    ("contabil", -3),
    ("contábil", -3),
    ("marketing", -3),
    ("design", -2),
    ("produto", -1),
]


def _score_job(job: dict) -> float:
    text = " ".join([
        job.get("title", ""),
        job.get("company", ""),
        job.get("location", ""),
        job.get("workplace_type", ""),
        job.get("job_type", ""),
    ]).lower()

    score = 0.0
    for keyword, weight in _POSITIVE_WEIGHTS:
        if keyword in text:
            score += weight
    for keyword, weight in _NEGATIVE_WEIGHTS:
        if keyword in text:
            score += weight  # weight is already negative

    return score


def filter_jobs(
    jobs: list[dict],
    min_score: float = 3.0,
) -> list[tuple[dict, float]]:
    """Filtra e pontua vagas por relevância.

    Retorna lista de tuplas (vaga, score) ordenada por score decrescente,
    incluindo apenas vagas com score >= min_score.
    """
    scored = [(job, _score_job(job)) for job in jobs]
    passing = [(job, score) for job, score in scored if score >= min_score]
    passing.sort(key=lambda t: t[1], reverse=True)
    return passing


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    test_jobs = [
        {
            "title": "Estagiário Python Remoto",
            "company": "",
            "location": "",
            "workplace_type": "remote",
            "job_type": "intern",
        },
        {
            "title": "Desenvolvedor Automação RPA Júnior",
            "company": "",
            "location": "",
            "workplace_type": "remote",
            "job_type": "full-time",
        },
        {
            "title": "Sênior .NET São Paulo",
            "company": "",
            "location": "São Paulo",
            "workplace_type": "onsite",
            "job_type": "full-time",
        },
        {
            "title": "Python Developer - São Leopoldo, RS",
            "company": "",
            "location": "São Leopoldo, RS",
            "workplace_type": "onsite",
            "job_type": "full-time",
        },
        {
            "title": "Estágio Em Recrutamento E Seleção Remoto",
            "company": "",
            "location": "",
            "workplace_type": "remote",
            "job_type": "intern",
        },
        {
            "title": "Formação em Vendas SDR 100% Remoto",
            "company": "",
            "location": "",
            "workplace_type": "remote",
            "job_type": "full-time",
        },
        {
            "title": "Estágio Python Backend Remoto",
            "company": "",
            "location": "",
            "workplace_type": "remote",
            "job_type": "intern",
        },
    ]

    min_score = 3.0
    results = filter_jobs(test_jobs, min_score=min_score)
    result_ids = {id(job) for job, _ in results}

    print(f"Threshold: score >= {min_score}\n")
    print(f"{'Título':<45} {'Score':>6}  {'Status'}")
    print("-" * 65)
    for job in test_jobs:
        score = _score_job(job)
        status = "PASSOU" if id(job) in result_ids else "DESCARTADA"
        print(f"  {job['title']:<43} {score:>6.1f}  {status}")

    print(f"\nVagas aprovadas ({len(results)}/{len(test_jobs)}):")
    for job, score in results:
        print(f"  [{score:.1f}] {job['title']}")
