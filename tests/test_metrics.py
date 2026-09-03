import unittest

from resmon.metrics import format_rate, format_temp


class FormatRateTests(unittest.TestCase):
    def test_bytes(self):
        self.assertEqual(format_rate(0), "0B")
        self.assertEqual(format_rate(512), "512B")
        self.assertEqual(format_rate(1023), "1023B")

    def test_kilobytes(self):
        self.assertEqual(format_rate(1024), "1.0KB")
        self.assertEqual(format_rate(1536), "1.5KB")

    def test_megabytes(self):
        self.assertEqual(format_rate(1024 * 1024), "1.0MB")
        self.assertEqual(format_rate(2.5 * 1024 * 1024), "2.5MB")

    def test_gigabytes_and_beyond(self):
        self.assertEqual(format_rate(1024**3), "1.0GB")
        # GB is the largest unit — a value that would round up to TB stays GB.
        self.assertEqual(format_rate(1536 * 1024**3), "1536.0GB")

    def test_negative_clamped_by_caller_not_here(self):
        # format_rate itself doesn't clamp; callers are expected to pass
        # non-negative deltas (metrics.py already does via max(0, ...)).
        self.assertEqual(format_rate(-1), "-1B")


class FormatTempTests(unittest.TestCase):
    def test_rounds_to_nearest_degree(self):
        self.assertEqual(format_temp(42.4), "42°C")
        self.assertEqual(format_temp(42.6), "43°C")

    def test_negative(self):
        self.assertEqual(format_temp(-5.0), "-5°C")


if __name__ == "__main__":
    unittest.main()
