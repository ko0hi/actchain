import asyncio

import pytest
import pytest_mock

from .order_request import (
    CancelOrderCommander,
    LimitOrderCommander,
    OrderCanceler,
    OrderPricer,
)


class TestOrderPricer:
    @pytest.mark.parametrize(
        "max_position_size, buy_sell_ratio, net_position_float, expected",
        [
            (2, 0.5, 0, {"buy_price": 9.5, "sell_price": 10.5}),
            (2, 0.5, 2, {"buy_price": 9.75, "sell_price": 10.75}),
            (2, 0.5, -2, {"buy_price": 9.25, "sell_price": 10.25}),
            (2, 1.0, 2, {"buy_price": 10, "sell_price": 11}),
            (2, 0, -2, {"buy_price": 9, "sell_price": 10}),
            (2, 0, -3, {"buy_price": 8.875, "sell_price": 9.875}),
        ],
    )
    def test_estimate_prices1(
        self,
        max_position_size: float,
        buy_sell_ratio: float,
        net_position_float,
        expected: dict,
    ) -> None:
        actual = OrderPricer(max_position_size=max_position_size).estimate_prices(
            vola=1,
            mid=10,
            buy_sell_ratio=buy_sell_ratio,
            net_position=net_position_float,
        )
        assert actual == expected


class TestLimitOrderCommander:
    def test_new_commands(self) -> None:
        limit_order_commands = LimitOrderCommander(
            "FX_BTC_JPY", 1, 2, 1
        ).create_commands(
            orders=[],
            buy_price=95,
            sell_price=105,
            best_ask=103,
            best_bid=98,
            buy_position=0,
            sell_position=0,
        )

        assert limit_order_commands == [
            {
                "symbol": "FX_BTC_JPY",
                "side": "BUY",
                "size": 1,
                "price": 95,
            },
            {
                "symbol": "FX_BTC_JPY",
                "side": "SELL",
                "size": 1,
                "price": 105,
            },
        ]

    def test_no_commands(self) -> None:
        limit_order_commands = LimitOrderCommander(
            "FX_BTC_JPY", 1, 2, 1
        ).create_commands(
            orders=[
                {
                    "id": "0",
                    "symbol": "FX_BTC_JPY",
                    "side": "SELL",
                    "size": 0.01,
                    "price": 105,
                },
                {
                    "id": "1",
                    "symbol": "FX_BTC_JPY",
                    "side": "BUY",
                    "size": 0.01,
                    "price": 95,
                },
            ],
            buy_price=95,
            sell_price=105,
            best_ask=103,
            best_bid=98,
            buy_position=0,
            sell_position=0,
        )

        assert limit_order_commands == []

    def test_order_sell_only(self) -> None:
        limit_order_commands = LimitOrderCommander(
            "FX_BTC_JPY", 1, 2, 1
        ).create_commands(
            orders=[
                {
                    "id": "0",
                    "symbol": "FX_BTC_JPY",
                    "side": "SELL",
                    "size": 0.01,
                    "price": 105,
                },
                {
                    "id": "1",
                    "symbol": "FX_BTC_JPY",
                    "side": "BUY",
                    "size": 0.01,
                    "price": 95,
                },
            ],
            buy_price=95,
            sell_price=104,
            best_ask=103,
            best_bid=98,
            buy_position=0,
            sell_position=0,
        )

        assert limit_order_commands == [
            {"symbol": "FX_BTC_JPY", "side": "SELL", "size": 1, "price": 104}
        ]

    def test_order_buy_only(self) -> None:
        limit_order_commands = LimitOrderCommander(
            "FX_BTC_JPY", 1, 2, 1
        ).create_commands(
            orders=[
                {
                    "id": "0",
                    "symbol": "FX_BTC_JPY",
                    "side": "SELL",
                    "size": 0.01,
                    "price": 105,
                },
                {
                    "id": "1",
                    "symbol": "FX_BTC_JPY",
                    "side": "BUY",
                    "size": 0.01,
                    "price": 95,
                },
            ],
            buy_price=96,
            sell_price=105,
            best_ask=103,
            best_bid=98,
            buy_position=0,
            sell_position=0,
        )

        assert limit_order_commands == [
            {"symbol": "FX_BTC_JPY", "side": "BUY", "size": 1, "price": 96}
        ]

    def test_use_best_prices(self) -> None:
        limit_order_commands = LimitOrderCommander(
            "FX_BTC_JPY", 1, 2, 1
        ).create_commands(
            orders=[],
            buy_price=95,
            sell_price=105,
            best_ask=106,
            best_bid=94,
            buy_position=0,
            sell_position=0,
        )

        assert limit_order_commands == [
            {"symbol": "FX_BTC_JPY", "side": "BUY", "size": 1, "price": 94},
            {"symbol": "FX_BTC_JPY", "side": "SELL", "size": 1, "price": 106},
        ]

    def test_no_command_due_to_position(self) -> None:
        limit_order_commands = LimitOrderCommander(
            "FX_BTC_JPY", 1, 2, 1
        ).create_commands(
            orders=[],
            buy_price=95,
            sell_price=105,
            best_ask=106,
            best_bid=94,
            buy_position=2,
            sell_position=2,
        )

        assert limit_order_commands == []


class TestCancelOrderCommander:
    def test_cancel_sell(self) -> None:
        cancel_order_commands = CancelOrderCommander(
            "FX_BTC_JPY", 2, 1
        ).create_commands(
            orders=[
                {
                    "id": "0",
                    "symbol": "FX_BTC_JPY",
                    "side": "SELL",
                    "size": 0.01,
                    "price": 105,
                },
                {
                    "id": "1",
                    "symbol": "FX_BTC_JPY",
                    "side": "BUY",
                    "size": 0.01,
                    "price": 95,
                },
            ],
            buy_price=95,
            sell_price=104,
            buy_position=0,
            sell_position=0,
        )

        assert cancel_order_commands == [{"symbol": "FX_BTC_JPY", "order_id": "0"}]

    def test_cancel_buy(self) -> None:
        cancel_order_commands = CancelOrderCommander(
            "FX_BTC_JPY", 2, 1
        ).create_commands(
            orders=[
                {
                    "id": "0",
                    "symbol": "FX_BTC_JPY",
                    "side": "SELL",
                    "size": 0.01,
                    "price": 105,
                },
                {
                    "id": "1",
                    "symbol": "FX_BTC_JPY",
                    "side": "BUY",
                    "size": 0.01,
                    "price": 95,
                },
            ],
            buy_price=96,
            sell_price=105,
            buy_position=0,
            sell_position=0,
        )

        assert cancel_order_commands == [{"symbol": "FX_BTC_JPY", "order_id": "1"}]

    def test_cancel_commands_when_reaching_maximum_positions_buy(self) -> None:
        cancel_order_commands = CancelOrderCommander(
            "FX_BTC_JPY", 2, 1
        ).create_commands(
            orders=[
                {
                    "id": "0",
                    "symbol": "FX_BTC_JPY",
                    "side": "SELL",
                    "size": 0.01,
                    "price": 105,
                },
                {
                    "id": "1",
                    "symbol": "FX_BTC_JPY",
                    "side": "BUY",
                    "size": 0.01,
                    "price": 95,
                },
            ],
            buy_price=95,
            sell_price=105,
            buy_position=2,
            sell_position=0,
        )

        assert cancel_order_commands == [
            {"symbol": "FX_BTC_JPY", "order_id": "1"},
        ]

    def test_cancel_commands_when_reaching_maximum_positions_sell(self) -> None:
        cancel_order_commands = CancelOrderCommander(
            "FX_BTC_JPY", 2, 1
        ).create_commands(
            orders=[
                {
                    "id": "0",
                    "symbol": "FX_BTC_JPY",
                    "side": "SELL",
                    "size": 0.01,
                    "price": 105,
                },
                {
                    "id": "1",
                    "symbol": "FX_BTC_JPY",
                    "side": "BUY",
                    "size": 0.01,
                    "price": 95,
                },
            ],
            buy_price=95,
            sell_price=105,
            buy_position=0,
            sell_position=2,
        )

        assert cancel_order_commands == [
            {"symbol": "FX_BTC_JPY", "order_id": "0"},
        ]


class TestOrderCanceler:
    @pytest.mark.asyncio
    async def test_no_doubled_cancel_request(
        self, mocker: pytest_mock.MockerFixture
    ) -> None:
        canceler = OrderCanceler()

        async def _patch_cancel_order(*args, **kwargs) -> int:
            await asyncio.sleep(0.5)
            return 1

        mocker.patch.object(canceler, "_cancel_order", _patch_cancel_order)

        res1, res2 = await asyncio.gather(
            canceler.cancel_order({"symbol": "FX_BTC_JPY", "order_id": "1"}),
            canceler.cancel_order({"symbol": "FX_BTC_JPY", "order_id": "1"}),
        )
        res3 = await canceler.cancel_order({"symbol": "FX_BTC_JPY", "order_id": "1"})

        # 同じid取り消し注文が入っている場合はスキップされる
        assert (res1 == 1 and res2 is None) or (res1 is None and res2 == 1)
        # 注文が終わっていれば再度取り消し注文が入る
        assert res3 == 1
        assert len(canceler._canceling) == 0
