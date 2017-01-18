import unittest

from .time import *


class TestTime(unittest.TestCase):
    def test_human_duration_zero(self):
        got = human_duration(0)
        self.assertEqual("00:00", got, "zero should be valid")
        got = human_duration(0.0)
        self.assertEqual("00:00", got, "zero should be valid")
        got = human_duration("0")
        self.assertEqual("00:00", got, "zero should be valid")
        got = human_duration("0.0")
        self.assertEqual("00:00", got, "zero should be valid")

    def test_human_duration_none(self):
        got = human_duration(None)
        self.assertEqual("??:??", got, "None should return unknown value")

    def test_human_duration_empty(self):
        got = human_duration("")
        self.assertEqual("??:??", got, "None should return unknown value")

    def test_human_duration_floor(self):
        got = human_duration(34.123, floor=True)
        self.assertEqual("00:34", got, "flooring should not produce fractional seconds")
        got = human_duration("34.123", floor=True)
        self.assertEqual("00:34", got, "flooring should not produce fractional seconds")

    def test_human_duration_normal(self):
        got = human_duration(34.123)
        self.assertEqual("00:34.123", got, "normal should produce fractional seconds")
        got = human_duration("34.123")
        self.assertEqual("00:34.123", got, "normal should produce fractional seconds")

    def test_reasonable_time_zero(self):
        got = reasonable_time(0, local=False)
        self.assertEqual("(Thu) 1970-01-01 00:00", got, "Should get expected time")

    def test_reasonable_time_number(self):
        got = reasonable_time(1234567.89, local=False)
        self.assertEqual("(Thu) 1970-01-15 06:56", got, "Should get expected time")

    def test_reasonable_time_str(self):
        got = reasonable_time("1234567.89", local=False)
        self.assertEqual("(Thu) 1970-01-15 06:56", got, "Should get expected time")

    def test_from_human_duration_minutes(self):
        got = from_human_duration("1:23.34")
        self.assertEqual(60 + 23.34, got)

    def test_from_human_duration_seconds(self):
        got = from_human_duration("23.34")
        self.assertEqual(23.34, got)

    def test_from_human_duration_hours(self):
        got = from_human_duration("1:00:23")
        self.assertEqual((60 * 60) + 23, got)

    def test_from_human_duration_days(self):
        got = from_human_duration("1:00:00:00")
        self.assertEqual(24 * 60 * 60, got)

if __name__ == '__main__':
    unittest.main()
