import json
import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from src.scripts.dados_painel import build_panel_data, latest_diff_day


def write(root: Path, relative: str, document: dict) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document), encoding="utf-8")


DIFF = {"tolerancia": 0.01, "resumo": {"api": None, "lake": None}, "contexto": {"web": "w"}, "contas": {}}


class LatestDiffDayTests(unittest.TestCase):
    def test_picks_the_most_recent_day_that_has_a_diff(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            write(root, "exports/buygoods/diff/2026/09/diff_ai_2026-09-30.json", DIFF)
            write(root, "exports/buygoods/diff/2026/10/diff_ai_2026-10-28.json", DIFF)
            # A web report without a diff is not a panel day yet.
            write(root, "exports/buygoods/web/2026/10/master_accounts_2026-10-29.json", {"contas": {}})

            self.assertEqual(latest_diff_day(root, "buygoods"), date(2026, 10, 28))
            self.assertIsNone(latest_diff_day(root, "pagamerican"))


class BuildPanelDataTests(unittest.TestCase):
    def test_missing_source_becomes_empty_and_diff_keeps_only_panel_keys(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            web = {"a": {"account_name": "A", "net_sales": 1.0}}
            write(root, "exports/pagamerican/web/2026/10/pagamerican_2026-10-29.json", {"contas": web})
            write(root, "exports/pagamerican/api/2026/10/pagamerican_2026-10-29.json", {"contas": web})
            write(
                root,
                "exports/pagamerican/diff/2026/10/diff_ai_2026-10-29.json",
                {**DIFF, "gateway": "Pagamerican", "fontes": {}},
            )

            data = build_panel_data(root, "pagamerican", date(2026, 10, 29))

            self.assertEqual(data["label"], "PagAmerican")
            self.assertEqual(data["tz"], "UTC")
            self.assertEqual(data["day"], "2026-10-29")
            self.assertEqual(data["sources"], {"web": web, "api": web, "lake": {}})
            self.assertEqual(sorted(data["diff"]), ["contas", "contexto", "resumo", "tolerancia"])

    def test_requires_the_diff_of_the_day(self):
        with TemporaryDirectory() as directory:
            with self.assertRaisesRegex(FileNotFoundError, "make diff GATEWAY=buygoods DATE=2026-10-28"):
                build_panel_data(Path(directory), "buygoods", date(2026, 10, 28))


if __name__ == "__main__":
    unittest.main()
