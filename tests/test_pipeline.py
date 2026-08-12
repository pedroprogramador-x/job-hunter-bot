import unittest
from unittest.mock import patch

import main


def _jobs(count: int) -> list[dict]:
    return [
        {
            "id": f"job-{index}",
            "source": "Test",
            "title": f"Backend Python Junior {index}",
            "company": "Empresa",
            "location": "Brasil",
            "workplace_type": "remote",
            "job_type": "full-time",
            "url": f"https://example.com/{index}",
        }
        for index in range(count)
    ]


class PipelineTests(unittest.TestCase):
    def _run_pipeline(self, *, email_sent: bool):
        jobs = _jobs(45)
        initial = [(job, float(100 - index)) for index, job in enumerate(jobs)]

        def filter_side_effect(received, min_score, *, final):
            self.assertEqual(min_score, 10.0)
            if not final:
                self.assertEqual(received, jobs)
                return initial
            self.assertEqual(len(received), 40)
            return [(job, float(80 - index)) for index, job in enumerate(received)]

        def enrich(received):
            self.assertEqual(len(received), 40)
            return [({**job, "description": "Python APIs"}, score) for job, score in received]

        patches = [
            patch("main.gupy_fetch", return_value=jobs),
            patch("main.linkedin_fetch", return_value=[]),
            patch("main.programathor_fetch", return_value=[]),
            patch("main.filter_jobs", side_effect=filter_side_effect),
            patch("main.filter_new_jobs", return_value=(jobs, {job["id"] for job in jobs})),
            patch("main.fetch_descriptions", side_effect=enrich),
            patch("main.analyze_jobs", return_value=""),
            patch("main.send_jobs_email", return_value=email_sent),
            patch("main.save_seen_ids"),
            patch("main.logger"),
        ]

        mocks = [item.start() for item in patches]
        try:
            main.run_pipeline()
        finally:
            for item in reversed(patches):
                item.stop()
        return mocks

    def test_enriches_top_40_and_emails_top_20(self) -> None:
        mocks = self._run_pipeline(email_sent=True)
        send_email = mocks[7]
        save_seen = mocks[8]

        sent_jobs = send_email.call_args.args[0]
        self.assertEqual(len(sent_jobs), 20)
        save_seen.assert_called_once()

    def test_does_not_save_state_when_email_fails(self) -> None:
        mocks = self._run_pipeline(email_sent=False)
        save_seen = mocks[8]
        save_seen.assert_not_called()

    def test_watchlist_telemetry_reports_sources_unique_companies_and_top_20(
        self,
    ) -> None:
        magalu = {
            **_jobs(1)[0],
            "source": "Gupy",
            "company": "Magazine Luiza",
            "target_company": "Magalu Cloud",
        }
        magalu_alias = {
            **_jobs(1)[0],
            "id": "job-1",
            "source": "Gupy",
            "company": "LuizaLabs",
        }
        roga = {
            **_jobs(1)[0],
            "id": "job-2",
            "source": "LinkedIn",
            "company": "Roga Labs",
        }

        with self.assertLogs("main", level="INFO") as captured:
            main._log_watchlist_presence([magalu, magalu_alias, roga])
            main._log_watchlist_summary(
                [magalu, magalu_alias, roga],
                [(magalu, 18.0), (roga, 19.0)],
            )

        output = "\n".join(captured.output)
        self.assertIn(
            "WATCHLIST PRESENCE | fonte=Gupy | empresa=Magalu Cloud | vagas=2",
            output,
        )
        self.assertIn(
            "WATCHLIST PRESENCE | fonte=LinkedIn | empresa=Roga Labs | vagas=1",
            output,
        )
        self.assertIn("matches encontrados: 3", output)
        self.assertIn("empresas únicas: 2", output)
        self.assertIn("vagas da watchlist no top 20: 2", output)


if __name__ == "__main__":
    unittest.main()
