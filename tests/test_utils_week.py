# Run: python -m unittest discover -s tests
import os
import unittest
from datetime import date
from unittest.mock import patch

os.environ.setdefault("BOT_TOKEN", "test-token-placeholder")
os.environ.setdefault("GROUP_CHAT_ID", "-1001234567890")
os.environ.setdefault("ADMIN_TELEGRAM_ID", "1")
os.environ.setdefault("ROTATION_ANCHOR_DATE", "2025-01-05")

import utils


class TestCurrentSunday(unittest.TestCase):
    def test_wednesday_maps_to_prior_sunday(self):
        with patch.object(utils, "_today", return_value=date(2026, 4, 22)):
            self.assertEqual(utils.get_current_sunday(), date(2026, 4, 19))

    def test_sunday_is_today(self):
        d = date(2026, 4, 19)
        with patch.object(utils, "_today", return_value=d):
            self.assertEqual(utils.get_current_sunday(), d)


class TestWeekLabel(unittest.TestCase):
    def test_known_sunday_jan_2025(self):
        self.assertEqual(utils.week_label_for_sunday(date(2025, 1, 5)), "2025-S1")


class TestRotationGroup(unittest.TestCase):
    def test_anchor_week_is_group_1(self):
        with patch.object(utils, "ROTATION_ANCHOR_DATE", "2025-01-05"):
            self.assertEqual(utils.group_id_for_sunday(date(2025, 1, 5)), 1)

    def test_next_sunday_cycles(self):
        with patch.object(utils, "ROTATION_ANCHOR_DATE", "2025-01-05"):
            self.assertEqual(utils.group_id_for_sunday(date(2025, 1, 12)), 2)
            self.assertEqual(utils.group_id_for_sunday(date(2025, 2, 2)), 5)

    def test_next_sunday_helper(self):
        with patch.object(utils, "_today", return_value=date(2026, 4, 22)):
            self.assertEqual(utils.get_next_sunday(), date(2026, 4, 26))


if __name__ == "__main__":
    unittest.main()
