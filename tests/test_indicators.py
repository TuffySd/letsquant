import unittest

from letsquant.indicators import max_drawdown, rate_of_change, sma


class IndicatorTests(unittest.TestCase):
    def test_sma_returns_latest_window_average(self) -> None:
        self.assertEqual(sma([1, 2, 3, 4], 2), 3.5)

    def test_rate_of_change_uses_prior_window_value(self) -> None:
        self.assertAlmostEqual(rate_of_change([10, 11, 12], 2), 0.2)

    def test_max_drawdown_returns_negative_drawdown(self) -> None:
        self.assertAlmostEqual(max_drawdown([100, 120, 90, 110]), -0.25)


if __name__ == "__main__":
    unittest.main()
