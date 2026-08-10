import unittest
from unittest.mock import patch

from scrapers import gupy_scraper, linkedin_scraper


class ScraperSearchTests(unittest.TestCase):
    def test_gupy_has_separate_remote_and_alagoas_searches(self) -> None:
        with patch.object(gupy_scraper, "_fetch_term", return_value=[]) as fetch:
            gupy_scraper.fetch_jobs()

        params = [call.args[1] for call in fetch.call_args_list]
        self.assertTrue(any(item.get("workplaceType") == "remote" for item in params))
        self.assertTrue(
            any(
                item.get("state") == "Alagoas" and "workplaceType" not in item
                for item in params
            )
        )

    def test_linkedin_has_separate_remote_and_maceio_searches(self) -> None:
        with patch.object(linkedin_scraper, "_fetch_term", return_value=None) as fetch:
            linkedin_scraper.fetch_jobs()

        params = [call.args[1] for call in fetch.call_args_list]
        self.assertTrue(any(item.get("f_WT") == "2" for item in params))
        self.assertTrue(
            any(
                item.get("location") == "Maceió, Alagoas, Brasil"
                and "f_WT" not in item
                for item in params
            )
        )

    def test_expanded_remote_terms_cover_entry_level_technologies(self) -> None:
        required_terms = {
            "estagio desenvolvimento de software",
            "estagio backend",
            "estagio python",
            "desenvolvedor backend junior",
            "software engineer junior",
            "java junior",
            "javascript junior",
            "full stack junior",
            "qa automation junior",
            "rpa junior",
            "etl junior",
        }
        self.assertTrue(required_terms.issubset(gupy_scraper._REMOTE_SEARCH_TERMS))
        self.assertTrue(required_terms.issubset(linkedin_scraper._REMOTE_SEARCH_TERMS))


if __name__ == "__main__":
    unittest.main()
