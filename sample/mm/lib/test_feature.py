import math

from .feature import BuySellRatioEstimator


class TestBuySellRatioEstimator:
    def test_estimate_by_orderbook(self):
        buys = [
            {
                "side": "BUY",
                "symbol": "BTCJPY",
                "price": 3,
                "size": 3,
                "size_cum": 3,
                "size_cum_exp": math.exp(-3),
                "size_cum_exp_cum": math.exp(-3),
            },
            {
                "side": "BUY",
                "symbol": "BTCJPY",
                "price": 2,
                "size": 2,
                "size_cum": 5,
                "size_cum_exp": math.exp(-5),
                "size_cum_exp_cum": math.exp(-3) + math.exp(-5),
            },
            {
                "side": "BUY",
                "symbol": "BTCJPY",
                "price": 1,
                "size": 1,
                "size_cum": 6,
                "size_cum_exp": math.exp(-6),
                "size_cum_exp_cum": math.exp(-3) + math.exp(-5) + math.exp(-6),
            },
        ]

        sells = [
            {
                "side": "SELL",
                "symbol": "BTCJPY",
                "price": 4,
                "size": 4,
                "size_cum": 4,
                "size_cum_exp": math.exp(-4),
                "size_cum_exp_cum": math.exp(-4),
            },
            {
                "side": "SELL",
                "symbol": "BTCJPY",
                "price": 5,
                "size": 5,
                "size_cum": 9,
                "size_cum_exp": math.exp(-9),
                "size_cum_exp_cum": math.exp(-4) + math.exp(-9),
            },
            {
                "side": "SELL",
                "symbol": "BTCJPY",
                "price": 6,
                "size": 6,
                "size_cum": 15,
                "size_cum_exp": math.exp(-15),
                "size_cum_exp_cum": math.exp(-4) + math.exp(-9) + math.exp(-15),
            },
        ]

        expected = (math.exp(-3) + math.exp(-5) + math.exp(-6)) / (
            math.exp(-3)
            + math.exp(-5)
            + math.exp(-6)
            + math.exp(-4)
            + math.exp(-9)
            + math.exp(-15)
        )

        assert math.isclose(expected, BuySellRatioEstimator(k=3).estimate_by_orderbook(buys, sells))  # type: ignore
