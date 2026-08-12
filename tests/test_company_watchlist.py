import unittest
from unittest.mock import patch

from core.company_watchlist import (
    COMPANY_WATCHLIST,
    WATCHLIST_BONUSES,
    match_target_company,
)
from core.filter_engine import _score_job, filter_jobs, is_job_blocked
from core.resume_analyzer import _build_prompt
from templates.email_template import render_email


def _job(
    title: str,
    company: str,
    *,
    location: str = "Brasil",
    workplace_type: str = "remote",
    description: str = "",
) -> dict:
    return {
        "id": f"{company}-{title}",
        "source": "Test",
        "title": title,
        "company": company,
        "location": location,
        "workplace_type": workplace_type,
        "job_type": "unknown",
        "description": description,
        "url": "https://example.com/job",
    }


class CompanyWatchlistMatchingTests(unittest.TestCase):
    def assert_match(
        self,
        company: str,
        canonical_name: str,
        *,
        priority: str | None = None,
        category: str | None = None,
    ) -> None:
        match = match_target_company(company)
        self.assertIsNotNone(match, company)
        assert match is not None
        self.assertEqual(match.canonical_name, canonical_name)
        if priority:
            self.assertEqual(match.priority, priority)
        if category:
            self.assertEqual(match.category, category)

    def test_v1_has_30_active_centralized_entries(self) -> None:
        self.assertEqual(len(COMPANY_WATCHLIST), 30)
        self.assertTrue(all(entry.active for entry in COMPANY_WATCHLIST))
        self.assertTrue(all(entry.aliases for entry in COMPANY_WATCHLIST))

    def test_magalu_cloud_aliases(self) -> None:
        for alias in ("Magalu Cloud", "Magazine Luiza", "LuizaLabs", "Luiza Labs"):
            with self.subTest(alias=alias):
                self.assert_match(
                    alias,
                    "Magalu Cloud",
                    priority="very_high",
                    category="remote",
                )

    def test_hand_talk_aliases(self) -> None:
        for alias in ("Hand Talk", "Hand Talk by Sorenson"):
            with self.subTest(alias=alias):
                self.assert_match(alias, "Hand Talk by Sorenson")

    def test_nuvemshop_aliases(self) -> None:
        for alias in ("Nuvemshop", "Tienda Nube", "Tiendanube"):
            with self.subTest(alias=alias):
                self.assert_match(alias, "Nuvemshop")

    def test_matching_normalizes_case_accents_spaces_and_legal_suffixes(self) -> None:
        cases = [
            ("  MAGAZINE   LUÍZA S.A.  ", "Magalu Cloud"),
            ("HAND   TÁLK BY SORENSON", "Hand Talk by Sorenson"),
            ("  TIÉNDANUBE  ", "Nuvemshop"),
            ("UNIMED   MACEIÓ", "Unimed Maceió"),
        ]
        for company, expected in cases:
            with self.subTest(company=company):
                self.assert_match(company, expected)

    def test_unknown_and_partial_names_do_not_match(self) -> None:
        for company in ("Empresa desconhecida", "Zupper", "Radixx"):
            with self.subTest(company=company):
                self.assertIsNone(match_target_company(company))

    def test_priority_bonus_mapping(self) -> None:
        self.assertEqual(WATCHLIST_BONUSES["very_high"], 3)
        self.assertEqual(WATCHLIST_BONUSES["high"], 2)
        self.assertEqual(WATCHLIST_BONUSES["medium"], 1)
        self.assertEqual(match_target_company("Magalu Cloud").bonus, 3)
        self.assertEqual(match_target_company("Gupy").bonus, 2)
        self.assertEqual(
            match_target_company("SoftwareS Automação Comercial").bonus,
            1,
        )


class CompanyWatchlistFilterIntegrationTests(unittest.TestCase):
    def assert_blocked(self, job: dict) -> None:
        self.assertTrue(is_job_blocked(job, final=True))
        self.assertEqual(filter_jobs([job], final=True), [])
        self.assertNotIn("watchlist_bonus", job)

    def test_watchlist_never_overrides_critical_hard_blocks(self) -> None:
        cases = [
            _job("Tech Lead Python", "Nuvemshop"),
            _job("Backend Senior", "Magalu Cloud"),
            _job(
                "Estágio Marketing",
                "Trakto",
                location="Maceió, AL",
                workplace_type="on-site",
            ),
            _job(
                "Backend Junior",
                "Gupy",
                location="São Paulo, SP",
                workplace_type="on-site",
            ),
        ]
        for job in cases:
            with self.subTest(title=job["title"], company=job["company"]):
                self.assert_blocked(job)

    def test_watchlist_does_not_help_a_job_reach_the_minimum_score(self) -> None:
        below_minimum = _job("Python", "Magalu Cloud")
        self.assertEqual(_score_job(below_minimum), 7.0)
        self.assertEqual(filter_jobs([below_minimum], min_score=10.0), [])
        self.assertNotIn("watchlist_bonus", below_minimum)

    def test_eligible_remote_magalu_job_gets_bonus_and_metadata(self) -> None:
        job = _job("Backend Junior", "Magazine Luiza")
        base_score = _score_job(job)

        results = filter_jobs([job], final=True)

        self.assertEqual(results, [(job, base_score + 3)])
        self.assertEqual(job["target_company"], "Magalu Cloud")
        self.assertEqual(job["target_company_priority"], "very_high")
        self.assertEqual(job["target_company_category"], "remote")
        self.assertEqual(job["watchlist_bonus"], 3)

    def test_eligible_maceio_roga_labs_internship_gets_bonus(self) -> None:
        job = _job(
            "Estágio Desenvolvimento de Software",
            "Roga Labs",
            location="Maceió, AL",
            workplace_type="on-site",
        )
        base_score = _score_job(job)

        results = filter_jobs([job], final=True)

        self.assertEqual(results, [(job, base_score + 3)])
        self.assertEqual(job["target_company"], "Roga Labs")
        self.assertEqual(job["target_company_category"], "maceio")

    def test_eligible_unknown_company_keeps_base_score_without_metadata(self) -> None:
        job = _job("Backend Junior", "Empresa desconhecida")
        base_score = _score_job(job)

        results = filter_jobs([job], final=True)

        self.assertEqual(results, [(job, base_score)])
        self.assertNotIn("target_company", job)
        self.assertNotIn("watchlist_bonus", job)

    def test_bonus_changes_ranking_only_after_both_jobs_pass(self) -> None:
        unknown = _job("Backend Junior", "Empresa desconhecida")
        watched = _job("Backend Junior", "Magalu Cloud")

        results = filter_jobs([unknown, watched], final=True)

        self.assertEqual([job for job, _ in results], [watched, unknown])
        self.assertEqual(results[0][1] - results[1][1], 3.0)


class CompanyWatchlistPresentationTests(unittest.TestCase):
    def test_email_adds_discreet_badge_only_to_watched_jobs(self) -> None:
        watched = _job("Backend Junior", "Magalu Cloud")
        filter_jobs([watched], final=True)
        unknown = _job("Backend Junior", "Empresa desconhecida")

        watched_html = render_email([(watched, 18.0)])
        unknown_html = render_email([(unknown, 15.0)])

        self.assertIn("⭐ Empresa monitorada", watched_html)
        self.assertNotIn("Empresa monitorada", unknown_html)

    @patch("core.resume_analyzer._load_resume", return_value="")
    def test_gemini_prompt_receives_watchlist_context(self, _load_resume) -> None:
        watched = _job("Backend Junior", "Magalu Cloud")
        scored = filter_jobs([watched], final=True)

        prompt = _build_prompt(scored)

        self.assertIn("Empresa estratégica monitorada: sim", prompt)
        self.assertIn("Categoria: remote", prompt)
        self.assertIn("Prioridade: very_high", prompt)
        self.assertIn("Não faça afirmações sobre a qualidade da empresa", prompt)


if __name__ == "__main__":
    unittest.main()
