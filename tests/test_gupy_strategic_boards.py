import unittest
from unittest.mock import Mock, patch

import requests

from core import description_fetcher
from core.filter_engine import filter_jobs, is_job_blocked
from core.job_deduplication import deduplicate_jobs
from core.strategic_boards import GUPY_STRATEGIC_BOARDS
from scrapers import gupy_scraper


def _raw_job(
    job_id: int,
    title: str,
    *,
    company: str = "Nome vindo da API",
    city: str = "",
    state: str = "",
    workplace_type: str = "remote",
    url_query: str = "jobBoardSource=gupy_portal",
) -> dict:
    return {
        "id": job_id,
        "name": title,
        "careerPageName": company,
        "city": city,
        "state": state,
        "workplaceType": workplace_type,
        "type": "vacancy_type_effective",
        "jobUrl": f"https://example.gupy.io/job/{job_id}?{url_query}",
        "publishedDate": "2026-08-17T12:00:00Z",
        "applicationDeadline": "2099-12-31T23:59:59Z",
    }


def _response(payload: object) -> Mock:
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = payload
    return response


class StrategicBoardsConfigTests(unittest.TestCase):
    def test_required_boards_are_centralized_and_active(self) -> None:
        configured = {
            board.slug: (
                board.canonical_name,
                board.company_id,
                board.category,
                board.priority,
            )
            for board in GUPY_STRATEGIC_BOARDS
            if board.active
        }

        self.assertEqual(
            configured,
            {
                "vemprait4us": (
                    "It4us Cyber Security",
                    759,
                    "remote",
                    "very_high",
                ),
                "handtalk": (
                    "Hand Talk by Sorenson",
                    82339,
                    "maceio",
                    "very_high",
                ),
                "trakto": ("Trakto", 51988, "maceio", "very_high"),
            },
        )


class StrategicBoardCollectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.it4us = GUPY_STRATEGIC_BOARDS[0]

    @patch("scrapers.gupy_scraper.requests.get")
    def test_collects_and_normalizes_real_gupy_fields(self, get: Mock) -> None:
        get.return_value = _response(
            {
                "data": [
                    _raw_job(
                        11644703,
                        "Estagiário(a) em Desenvolvimento com IA",
                        company="#VEMPRAIT4US",
                        city="Maceió",
                        state="Alagoas",
                    )
                ],
                "pagination": {"total": 1},
            }
        )

        jobs = gupy_scraper._fetch_strategic_board(self.it4us)

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["id"], "gupy_11644703")
        self.assertEqual(
            jobs[0]["title"],
            "Estagiário(a) em Desenvolvimento com IA",
        )
        self.assertEqual(jobs[0]["source"], "Gupy")
        self.assertEqual(jobs[0]["company"], "It4us Cyber Security")
        self.assertEqual(jobs[0]["location"], "Maceió, Alagoas")
        self.assertEqual(jobs[0]["workplace_type"], "remote")
        self.assertEqual(jobs[0]["job_type"], "vacancy_type_effective")
        self.assertEqual(
            jobs[0]["url"],
            "https://example.gupy.io/job/11644703?jobBoardSource=gupy_portal",
        )
        self.assertTrue(jobs[0]["applications_open"])
        self.assertEqual(get.call_args.kwargs["params"]["companyId"], 759)
        self.assertEqual(get.call_args.kwargs["timeout"], 15)

    @patch("scrapers.gupy_scraper.requests.get")
    def test_empty_board_returns_empty_list(self, get: Mock) -> None:
        get.return_value = _response(
            {"data": [], "pagination": {"total": 0}}
        )
        self.assertEqual(gupy_scraper._fetch_strategic_board(self.it4us), [])

    @patch("scrapers.gupy_scraper.requests.get")
    def test_paginates_until_all_jobs_are_collected(self, get: Mock) -> None:
        first_page = [_raw_job(index, f"Backend Junior {index}") for index in range(100)]
        get.side_effect = [
            _response({"data": first_page, "pagination": {"total": 101}}),
            _response(
                {
                    "data": [_raw_job(100, "Backend Junior 100")],
                    "pagination": {"total": 101},
                }
            ),
        ]

        jobs = gupy_scraper._fetch_strategic_board(self.it4us)

        self.assertEqual(len(jobs), 101)
        self.assertEqual(
            [call.kwargs["params"]["offset"] for call in get.call_args_list],
            [0, 100],
        )

    @patch("scrapers.gupy_scraper.requests.get")
    def test_timeout_is_isolated(self, get: Mock) -> None:
        get.side_effect = requests.Timeout("demorou")
        with self.assertLogs("scrapers.gupy_scraper", level="WARNING") as logs:
            jobs = gupy_scraper._fetch_strategic_board(self.it4us)
        self.assertEqual(jobs, [])
        self.assertIn("timeout", "\n".join(logs.output))

    @patch("scrapers.gupy_scraper.requests.get")
    def test_http_429_is_logged_without_retrying_forever(self, get: Mock) -> None:
        error_response = Mock(status_code=429)
        get.side_effect = requests.HTTPError("rate limit", response=error_response)
        with self.assertLogs("scrapers.gupy_scraper", level="ERROR") as logs:
            jobs = gupy_scraper._fetch_strategic_board(self.it4us)
        self.assertEqual(jobs, [])
        self.assertEqual(get.call_count, 1)
        self.assertIn("HTTP=429", "\n".join(logs.output))

    @patch("scrapers.gupy_scraper.requests.get")
    def test_invalid_payload_is_rejected(self, get: Mock) -> None:
        get.return_value = _response({"data": "não é uma lista"})
        with self.assertLogs("scrapers.gupy_scraper", level="ERROR") as logs:
            jobs = gupy_scraper._fetch_strategic_board(self.it4us)
        self.assertEqual(jobs, [])
        self.assertIn("payload inválido", "\n".join(logs.output))

    def test_one_board_failure_does_not_stop_the_others(self) -> None:
        hand_talk_job = gupy_scraper._parse_job(
            _raw_job(2, "Backend Junior", company="Hand Talk")
        )
        trakto_job = gupy_scraper._parse_job(
            _raw_job(3, "QA Junior", company="Trakto")
        )
        hand_talk_job["company"] = "Hand Talk by Sorenson"
        trakto_job["company"] = "Trakto"

        with patch.object(
            gupy_scraper,
            "_fetch_strategic_board",
            side_effect=[RuntimeError("falha"), [hand_talk_job], [trakto_job]],
        ):
            jobs = gupy_scraper.fetch_strategic_gupy_boards([])

        self.assertEqual([job["id"] for job in jobs], ["gupy_2", "gupy_3"])

    def test_strategic_job_reuses_existing_gupy_description_flow(self) -> None:
        job = gupy_scraper._parse_job(_raw_job(4, "Backend Junior"))

        with patch.object(
            description_fetcher,
            "_fetch_gupy",
            return_value="Python e APIs",
        ) as fetch:
            description = description_fetcher._fetch_description(job)

        self.assertEqual(description, "Python e APIs")
        fetch.assert_called_once_with(job["url"])


class StrategicBoardDeduplicationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.it4us = GUPY_STRATEGIC_BOARDS[0]

    def test_global_and_strategic_copy_is_not_added_twice(self) -> None:
        global_job = gupy_scraper._parse_job(
            _raw_job(11644703, "Estagiário(a) em Desenvolvimento com IA")
        )
        strategic_copy = {
            **global_job,
            "company": "It4us Cyber Security",
        }

        with (
            patch.object(gupy_scraper, "GUPY_STRATEGIC_BOARDS", (self.it4us,)),
            patch.object(
                gupy_scraper,
                "_fetch_strategic_board",
                return_value=[strategic_copy],
            ),
            self.assertLogs("scrapers.gupy_scraper", level="INFO") as logs,
        ):
            added = gupy_scraper.fetch_strategic_gupy_boards([global_job])

        self.assertEqual(added, [])
        output = "\n".join(logs.output)
        self.assertIn("duplicadas_global=1", output)
        self.assertIn("exclusivas=0", output)

    def test_two_distinct_jobs_from_same_company_are_preserved(self) -> None:
        jobs = [
            gupy_scraper._parse_job(_raw_job(10, "Backend Junior")),
            gupy_scraper._parse_job(_raw_job(11, "QA Junior")),
        ]
        for job in jobs:
            job["company"] = "It4us Cyber Security"

        with (
            patch.object(gupy_scraper, "GUPY_STRATEGIC_BOARDS", (self.it4us,)),
            patch.object(
                gupy_scraper,
                "_fetch_strategic_board",
                return_value=jobs,
            ),
        ):
            added = gupy_scraper.fetch_strategic_gupy_boards([])

        self.assertEqual([job["id"] for job in added], ["gupy_10", "gupy_11"])

    def test_cosmetic_gupy_url_differences_are_deduplicated(self) -> None:
        first = gupy_scraper._parse_job(
            _raw_job(20, "Backend Junior", url_query="jobBoardSource=gupy_portal")
        )
        second = gupy_scraper._parse_job(
            _raw_job(21, "Backend Junior", url_query="jobBoardSource=gupy_public_page")
        )
        second["url"] = first["url"].replace(
            "gupy_portal", "gupy_public_page"
        )

        self.assertEqual(deduplicate_jobs([first, second]), [first])


class StrategicBoardFilterIntegrationTests(unittest.TestCase):
    def test_eligible_it4us_internship_keeps_watchlist_behavior(self) -> None:
        job = gupy_scraper._parse_job(
            _raw_job(11644703, "Estagiário(a) em Desenvolvimento com IA")
        )
        job["company"] = "It4us Cyber Security"
        job["description"] = "Desenvolvimento Python, APIs e automação com IA."

        results = filter_jobs([job], final=True)

        self.assertEqual(len(results), 1)
        self.assertEqual(job["target_company"], "It4us Cyber Security")
        self.assertEqual(job["target_company_priority"], "very_high")
        self.assertEqual(job["target_company_category"], "remote")
        self.assertEqual(job["watchlist_bonus"], 3)

    def test_senior_and_non_technical_jobs_remain_blocked(self) -> None:
        senior = {
            **gupy_scraper._parse_job(
                _raw_job(30, "Pessoa Engenheira de Machine Learning Senior")
            ),
            "company": "Hand Talk by Sorenson",
        }
        non_technical = {
            **gupy_scraper._parse_job(
                _raw_job(
                    31,
                    "Analista de Customer Success Pleno",
                    city="Maceió",
                    state="Alagoas",
                    workplace_type="on-site",
                )
            ),
            "company": "Trakto",
        }

        self.assertTrue(is_job_blocked(senior, final=True))
        self.assertTrue(is_job_blocked(non_technical, final=True))
        self.assertEqual(filter_jobs([senior, non_technical], final=True), [])

    def test_eligible_trakto_qa_junior_can_pass(self) -> None:
        job = {
            **gupy_scraper._parse_job(
                _raw_job(32, "QA Automation Junior — Remoto")
            ),
            "company": "Trakto",
            "description": "Automação de testes com Python e APIs.",
        }

        results = filter_jobs([job], final=True)

        self.assertEqual(len(results), 1)
        self.assertEqual(job["target_company"], "Trakto")


if __name__ == "__main__":
    unittest.main()
