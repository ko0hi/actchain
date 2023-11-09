import math
import pytest

from .orderbook import ExtendOrderbookFunction, OrderbookData, OrderbookLoop


@pytest.mark.asyncio
@pytest.mark.skip(reason="This test is for manual testing")
async def test_orderbook():
    n = 0
    async for msg in OrderbookLoop().loop():
        print(n)
        print(msg["BUY"][0])
        print(msg["SELL"][0])
        n += 1
        if n == 5:
            break


class TestExtendOrderbookFunction:
    @pytest.fixture
    def orderbook_data(self) -> OrderbookData:
        return {
            "BUY": [
                {"side": "BUY", "symbol": "BTCJPY", "price": 3, "size": 3},
                {"side": "BUY", "symbol": "BTCJPY", "price": 2, "size": 2},
                {"side": "BUY", "symbol": "BTCJPY", "price": 1, "size": 1},
            ],
            "SELL": [
                {"side": "SELL", "symbol": "BTCJPY", "price": 4, "size": 4},
                {"side": "SELL", "symbol": "BTCJPY", "price": 5, "size": 5},
                {"side": "SELL", "symbol": "BTCJPY", "price": 6, "size": 6},
            ],
        }

    def test_extend_orderbook_data(self, orderbook_data: OrderbookData) -> None:
        expected = {
            "BUY": [
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
            ],
            "SELL": [
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
            ],
            "mid": (3 + 4) / 2,
            "spread": (4 - 3) / ((3 + 4) / 2),
            "buy_sell_ratio": (math.exp(-3) + math.exp(-5) + math.exp(-6))
            / (
                math.exp(-3)
                + math.exp(-5)
                + math.exp(-6)
                + math.exp(-4)
                + math.exp(-9)
                + math.exp(-15)
            ),
        }

        actual = ExtendOrderbookFunction(k=3).extend_orderbook_data(orderbook_data)

        assert expected["BUY"] == actual["BUY"]
        assert expected["SELL"] == actual["SELL"]
        assert expected["mid"] == actual["mid"]
        assert expected["spread"] == actual["spread"]
