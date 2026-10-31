import unittest
from datetime import date

from src.scripts.diff_fontes import FIELDS, build_diff

DAY = date(2026, 10, 28)


def account(name, **values):
    return {"account_name": name, **{field: 0.0 for field in FIELDS}, **values}


def report(source, accounts):
    return {
        "gateway": "Buygoods",
        "report_date": DAY.isoformat(),
        "currency": "USD",
        "source": source,
        "contas": accounts,
    }


WEB = report(
    "web",
    {
        "same": account("Same", gross_sales=100.0),
        "diff": account("Diff", gross_sales=100.0, refunds=10.0),
        "lost": account("Lost", gross_sales=50.0),
    },
)
API = report(
    "api",
    {
        "same": account("Same", gross_sales=100.005),  # within the US$ 0.01 tolerance
        "diff": account("Diff", gross_sales=100.0, refunds=12.5),
        "extra": account("Extra", net_sales=-7.0),
    },
)
PATHS = {"web": "web.json", "api": "api.json", "lake": None}


class BuildDiffTests(unittest.TestCase):
    def setUp(self):
        self.ai, self.rows = build_diff("Buygoods", DAY, {"web": WEB, "api": API, "lake": None}, PATHS)

    def test_summary_counts_accounts_and_fields_against_the_base(self):
        summary = self.ai["resumo"]["api"]
        self.assertEqual((summary["contas_comparadas"], summary["contas_iguais"]), (2, 1))
        self.assertEqual((summary["faltando_na_fonte"], summary["extra_na_fonte"]), (["lost"], ["extra"]))
        self.assertEqual(
            summary["campos"]["refunds"],
            {"iguais": 1, "divergentes": 1, "total_base": 10.0, "total_fonte": 12.5, "delta": 2.5},
        )
        self.assertNotIn("lake", self.ai["resumo"])

    def test_ai_accounts_keep_only_divergent_or_missing(self):
        self.assertEqual(set(self.ai["contas"]), {"diff", "lost", "extra"})
        self.assertEqual(self.ai["contas"]["diff"]["campos"], {"refunds": {"web": 10.0, "api": 12.5}})
        self.assertEqual(self.ai["contas"]["lost"]["status"], {"api": "faltando_na_fonte"})
        # absent accounts show only their non-zero fields
        self.assertEqual(self.ai["contas"]["extra"]["campos"], {"net_sales": {"web": None, "api": -7.0}})

    def test_dashboard_has_one_row_per_account_field_source(self):
        self.assertEqual(len(self.rows), 4 * len(FIELDS))
        row = next(r for r in self.rows if r["conta"] == "diff" and r["campo"] == "refunds")
        self.assertEqual(
            (row["valor"], row["valor_base"], row["delta"], row["delta_pct"], row["status"]),
            (12.5, 10.0, 2.5, 25.0, "divergente"),
        )
        lost = next(r for r in self.rows if r["conta"] == "lost" and r["campo"] == "gross_sales")
        self.assertEqual((lost["valor"], lost["delta"], lost["status"]), (None, None, "faltando_na_fonte"))
        zero_base = next(r for r in self.rows if r["conta"] == "same" and r["campo"] == "refunds")
        self.assertEqual((zero_base["delta_pct"], zero_base["status"]), (None, "igual"))


if __name__ == "__main__":
    unittest.main()
