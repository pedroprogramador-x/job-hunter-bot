import unittest

from core.filter_engine import (
    _score_job,
    filter_jobs,
    is_job_blocked,
    normalize_description,
    normalize_location,
    normalize_title,
)


def _job(
    title: str,
    *,
    location: str = "Brasil",
    workplace_type: str = "remote",
    description: str = "",
) -> dict:
    return {
        "id": title,
        "title": title,
        "company": "Empresa",
        "location": location,
        "workplace_type": workplace_type,
        "job_type": "unknown",
        "description": description,
    }


class FilterEngineTests(unittest.TestCase):
    def assert_passes(self, job: dict, minimum_score: float = 10.0) -> float:
        results = filter_jobs([job], final=True)
        self.assertEqual(len(results), 1, job["title"])
        score = results[0][1]
        self.assertGreaterEqual(score, minimum_score)
        return score

    def assert_blocked(self, job: dict) -> None:
        self.assertTrue(is_job_blocked(job, final=True), job["title"])
        self.assertEqual(filter_jobs([job], final=True), [])

    def test_priority_jobs_pass_with_high_scores(self) -> None:
        cases = [
            _job("Estágio Backend Python — Remoto"),
            _job("Backend Developer Junior — Remoto"),
            _job(
                "Estágio Java — Maceió",
                location="Maceió, AL",
                workplace_type="on-site",
            ),
            _job("Full Stack Junior JavaScript — Remoto"),
        ]
        for job in cases:
            with self.subTest(title=job["title"]):
                self.assert_passes(job)

    def test_generic_it_internship_requires_technical_description(self) -> None:
        technical = _job(
            "Estágio TI — Maceió",
            location="Maceió - AL",
            workplace_type="on-site",
            description="Atuação com programação e integração de APIs.",
        )
        non_technical = _job(
            "Estágio TI — Maceió",
            location="Maceió - AL",
            workplace_type="on-site",
            description="Apoio administrativo, planilhas e atendimento.",
        )

        self.assert_passes(technical)
        self.assert_blocked(non_technical)

    def test_incompatible_seniority_is_hard_blocked(self) -> None:
        titles = [
            "Lead Data Platform Engineer — Remoto",
            "Tech Lead Python — Remoto",
            "Team Lead Python — Remoto",
            "Desenvolvedor Backend Pleno",
            "Backend Python Senior — Remoto",
            "Backend Python Sênior — Remoto",
            "Backend Python SR",
            "Backend Python SR.",
            "Desenvolvedor Backend PL",
            "Desenvolvedor Backend PL.",
            "Especialista Python",
            "Specialist Python",
            "Staff Engineer",
            "Principal Engineer",
            "Software Architect",
            "Arquiteto de Software",
            "Engineering Coordinator",
            "Coordenador de Engenharia",
            "Engineering Manager",
            "Gerente de Engenharia",
            "Analista de Dados Sr",
        ]
        for title in titles:
            with self.subTest(title=title):
                self.assert_blocked(_job(title))

    def test_pl_sql_junior_is_not_blocked_by_pl(self) -> None:
        self.assert_passes(_job("Desenvolvedor PL/SQL Junior — Remoto"))

    def test_sr_and_pl_do_not_match_inside_other_words(self) -> None:
        self.assert_passes(_job("Spring Developer Junior — Remoto"))
        self.assert_passes(_job("Platform Developer Junior — Remoto"))

    def test_location_rules(self) -> None:
        self.assert_blocked(
            _job(
                "Estágio Backend Python",
                location="São Paulo, SP",
                workplace_type="on-site",
            )
        )
        self.assert_blocked(
            _job(
                "Backend Python Junior",
                location="São Paulo, SP",
                workplace_type="hybrid",
            )
        )
        self.assert_passes(
            _job(
                "Estágio Backend Python",
                location="Maceió, AL",
                workplace_type="presencial",
            )
        )
        self.assert_passes(
            _job(
                "Backend Python Junior",
                location="Maceio - AL",
                workplace_type="híbrido",
            )
        )
        self.assert_passes(
            _job(
                "Backend Python Junior",
                location="Brazil",
                workplace_type="remote",
            )
        )

    def test_al_is_not_detected_as_arbitrary_substring(self) -> None:
        california = _job(
            "Backend Python Junior",
            location="California",
            workplace_type="on-site",
        )
        self.assert_blocked(california)
        self.assertNotIn("alagoas", normalize_location(california))

    def test_required_experience_rules(self) -> None:
        base = _job(
            "Backend Python Junior — Remoto",
            description="Requisito obrigatório: 1 ano de experiência.",
        )
        two_years = _job(
            "Backend Python Junior — Remoto",
            description="Mínimo de 2 anos de experiência.",
        )
        self.assert_passes(base)
        self.assert_passes(two_years)
        self.assertEqual(_score_job(base) - _score_job(two_years), 2.0)

        blocking_descriptions = [
            "Mínimo de 3 anos de experiência.",
            "3+ anos de experiência.",
            "Experiência mínima de 4 anos.",
            "At least 3 years of experience.",
            "5+ years required.",
            ("texto introdutório " * 40) + "Mínimo de 3 anos de experiência.",
        ]
        for description in blocking_descriptions:
            with self.subTest(description=description):
                self.assert_blocked(
                    _job(
                        "Backend Python Junior — Remoto",
                        description=description,
                    )
                )

    def test_non_requirement_year_mentions_do_not_block(self) -> None:
        descriptions = [
            "Empresa com 5 anos de mercado.",
            "Projeto criado há 3 anos.",
            "Benefício adicional após 3 anos.",
        ]
        for description in descriptions:
            with self.subTest(description=description):
                self.assert_passes(
                    _job(
                        "Backend Python Junior — Remoto",
                        description=description,
                    )
                )

    def test_description_technology_score_is_capped(self) -> None:
        job = _job(
            "Estágio TI — Remoto",
            description=(
                "Python FastAPI Django Flask automação APIs integração RPA "
                "full stack QA automation sistemas dados ETL REST SQL PostgreSQL "
                "Java JavaScript Git Docker AWS Azure GCP"
            ),
        )
        score = self.assert_passes(job)
        self.assertLessEqual(score, 17.0)  # estágio 8 + remoto 4 + descrição 5

    def test_ia_does_not_match_inside_especialista(self) -> None:
        job = _job("Especialista", description="")
        self.assertEqual(_score_job(job), 4.0)  # apenas localização remota

    def test_normalization_handles_accents_and_casing(self) -> None:
        job = _job(
            "ESTÁGIO PYTHON",
            location="MACEIÓ, AL",
            workplace_type="HÍBRIDO",
            description="PROGRAMAÇÃO E APIs",
        )
        self.assertEqual(normalize_title(job), "estagio python")
        self.assertEqual(normalize_location(job), "maceio, al")
        self.assertEqual(normalize_description(job), "programacao e apis")
        self.assert_passes(job)

    def test_remote_variations_are_accepted_once(self) -> None:
        remote = _job(
            "Backend Developer Junior — Remote Brazil",
            location="Brazil",
            workplace_type="unknown",
        )
        home_office = _job(
            "Backend Developer Junior — Home Office Brasil",
            location="Brasil",
            workplace_type="unknown",
        )
        structured_home_office = _job(
            "Full Stack Junior JavaScript",
            location="Brasil",
            workplace_type="Home office",
        )
        self.assert_passes(remote)
        self.assert_passes(home_office)
        self.assert_passes(structured_home_office)
        self.assertEqual(_score_job(remote), _score_job(home_office))

    def test_card_stage_allows_description_rules_only_in_final_stage(self) -> None:
        job = _job(
            "Backend Python Junior — Remoto",
            description="Mínimo de 3 anos de experiência.",
        )
        self.assertFalse(is_job_blocked(job, final=False))
        self.assertTrue(is_job_blocked(job, final=True))

    def test_clear_non_technical_internships_are_blocked(self) -> None:
        titles = [
            "Estagiário Administrativo - Maceió",
            "Estágio em Administração - Maceió",
            "Estágio RH - Remoto",
            "Estágio Marketing - Maceió",
            "Estágio Financeiro - Maceió",
        ]
        for title in titles:
            with self.subTest(title=title):
                self.assert_blocked(_job(title, location="Maceió, AL"))

    def test_target_technical_entry_level_titles_still_pass(self) -> None:
        jobs = [
            _job(
                "Estágio Desenvolvimento de Software - Maceió",
                location="Maceió, AL",
                workplace_type="on-site",
            ),
            _job(
                "Estágio Backend - Maceió",
                location="Maceió, AL",
                workplace_type="on-site",
            ),
            _job("QA Junior"),
            _job("Analista de Automação de Testes Junior"),
        ]
        for job in jobs:
            with self.subTest(title=job["title"]):
                self.assert_passes(job)

    def test_generic_it_internship_needs_strong_description_signal(self) -> None:
        technical = _job(
            "Estágio TI - Maceió",
            location="Maceió, AL",
            workplace_type="on-site",
            description="Desenvolvimento com programação e APIs REST.",
        )
        administrative = _job(
            "Estágio TI - Maceió",
            location="Maceió, AL",
            workplace_type="on-site",
            description="Atualização de sistemas internos, planilhas e bases de dados.",
        )
        dotted_ti = _job(
            "Estágio T.I. - Maceió",
            location="Maceió, AL",
            workplace_type="on-site",
            description="Programação Python e integração com APIs.",
        )
        ti_inside_word = _job(
            "Estágio Garantia da Qualidade - Maceió",
            location="Maceió, AL",
            workplace_type="on-site",
            description="Planilhas e atendimento administrativo.",
        )

        self.assert_passes(technical)
        self.assert_passes(dotted_ti)
        self.assert_blocked(administrative)
        self.assert_blocked(ti_inside_word)

    def test_ambiguous_operations_title_requires_strong_technical_signal(self) -> None:
        technical = _job(
            "Estágio Operações de TI",
            description="Automação de rotinas e consultas SQL.",
        )
        administrative = _job(
            "Estágio Operações Administrativas",
            description="Planilhas, relatórios e atendimento interno.",
        )

        self.assert_passes(technical)
        self.assert_blocked(administrative)

    def test_real_non_technical_false_positives_are_blocked(self) -> None:
        origem = _job(
            "Estagiário Administrativo - Polo Alagoas",
            location="Pilar, AL",
            workplace_type="on-site",
            description=(
                "Integração energética. Apoiar na atualização de sistemas internos "
                "e bases de dados, planilhas, relatórios e atendimento interno."
            ),
        )
        jobbol = _job(
            "Estagiário na área Administrativa",
            location="Maceió, AL",
            workplace_type="on-site",
            description=(
                "Organizar documentos, apoiar informações em sistemas internos "
                "e elaborar relatórios administrativos."
            ),
        )
        generic_operations = _job(
            "Estagiário(a) Superior - Centro de Operações",
            location="Maceió, AL",
            workplace_type="on-site",
            description=(
                "Soluções que impulsionam o desenvolvimento. Atualizações de dados "
                "em sistemas corporativos e relatórios gerenciais."
            ),
        )
        distributed_generation = _job(
            "Estagiário(a) Superior - Geração Distribuída",
            location="Maceió, AL",
            workplace_type="on-site",
            description=(
                "Soluções que impulsionam o desenvolvimento. Tratamento de dados, "
                "conexão de sistemas elétricos e planilhas."
            ),
        )

        self.assertEqual(_score_job(origem), 17.0)
        self.assertEqual(_score_job(jobbol), 14.0)
        self.assertEqual(_score_job(generic_operations), 14.0)
        self.assertEqual(_score_job(distributed_generation), 14.0)
        for job in (origem, jobbol, generic_operations, distributed_generation):
            with self.subTest(title=job["title"]):
                self.assert_blocked(job)


if __name__ == "__main__":
    unittest.main()
