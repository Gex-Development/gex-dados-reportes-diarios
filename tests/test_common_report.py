import unittest
from datetime import date, datetime, timedelta, timezone

from src.common.report import BUYGOODS_TZ, PAGAMERICAN_TZ, yesterday

BRAZIL = timezone(timedelta(hours=-3))


class YesterdayTests(unittest.TestCase):
    def test_pagamerican_uses_the_utc_day_not_the_machine_day(self):
        # 22:30 in Brazil on 10/30 is 01:30 UTC on 10/31: UTC "yesterday" is 10/30, local would say 10/29.
        self.assertEqual(yesterday(datetime(2026, 10, 30, 22, 30, tzinfo=BRAZIL), PAGAMERICAN_TZ), date(2026, 10, 30))

    def test_buygoods_uses_the_gmt4_day_not_the_machine_day(self):
        # 00:30 in Brazil on 10/31 is still 23:30 of 10/30 in GMT-4: 10/30 is not over, so yesterday is 10/29.
        self.assertEqual(yesterday(datetime(2026, 10, 31, 0, 30, tzinfo=BRAZIL), BUYGOODS_TZ), date(2026, 10, 29))


if __name__ == "__main__":
    unittest.main()
