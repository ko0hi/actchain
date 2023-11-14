import asyncio
import time
from dataclasses import dataclass
from typing import TypedDict

import pandas as pd
import pybotters_wrapper as pbw
from loguru import logger
from pybotters_wrapper.core.api import CancelOrderAPIResponse, LimitOrderAPIResponse
from pybotters_wrapper.core.typedefs import OrderItem

import actchain
from actchain import Event

from .config import config
from .feature import BuySellRatioEstimatorSendData
from .ohlcv import OHLCVData
from .order_status import OrderStatusData
from .position_status import ExtendedPositionStatusData


@dataclass
class RateLimitState(actchain.State):
    last_order_ts: float = 0
    last_penalized_ts: float = 0

    @classmethod
    def suspended(cls) -> None:
        cls().last_order_ts = time.monotonic()

    @classmethod
    def penalized(cls) -> None:
        cls().last_penalized_ts = time.monotonic()
        logger.error(
            f"Rate limit exceeded. No Order/Cancel request for next {config.sleep_at_api_limit} seconds."
        )

    @property
    def is_being_penalized(self) -> bool:
        return time.monotonic() - self.last_penalized_ts < config.sleep_at_api_limit

    @property
    def is_being_suspended(self) -> bool:
        return time.monotonic() - self.last_order_ts < config.order_interval


class OrderPricerReceiveData(
    BuySellRatioEstimatorSendData,
    ExtendedPositionStatusData,
    OrderStatusData,
    OHLCVData,
):
    ...


class OrderPriceData(TypedDict):
    buy_price: float
    sell_price: float


class OrderPricerSendData(OrderPricerReceiveData):
    buy_price: float
    sell_price: float


class OrderPricer(actchain.Function[OrderPricerReceiveData, OrderPricerSendData]):
    def __init__(self, max_position_size: float = 0.02):
        super(OrderPricer, self).__init__()
        self._max_position_size = max_position_size

    async def handle(
        self, event: actchain.Event[OrderPricerReceiveData]
    ) -> OrderPricerSendData:
        price_data = self.estimate_prices(
            event.data["df_ohlcv"]["volatility"].iloc[-1],
            event.data["mid"],
            event.data["buy_sell_ratio"],
            event.data["net_position"],
        )
        return OrderPricerSendData(
            **{
                **event.data,
                **price_data,
            }
        )

    def estimate_prices(
        self, vola: float, mid: float, buy_sell_ratio: float, net_position: float
    ) -> OrderPriceData:
        # net_position=0 -> position_alpha=0.5
        # net_position=max short(-self._max_position_size) -> position_alpha=0
        # net_position=max long(self._max_position_size) -> position_alpha=1
        position_alpha = (net_position - -self._max_position_size) / (
            self._max_position_size * 2
        )
        adjust = (buy_sell_ratio + position_alpha) * 0.5
        sell_price_base = mid - vola * 0.5
        center = vola * adjust + sell_price_base
        return {
            "buy_price": center - vola * 0.5,
            "sell_price": center + vola * 0.5,
        }


class LimitOrderCommand(TypedDict):
    symbol: str
    side: str
    price: float
    size: float


class CancelOrderCommand(TypedDict):
    symbol: str
    order_id: str


class LimitOrderCommanderSendData(OrderPricerSendData):
    limit_order_commands: list[LimitOrderCommand]


class LimitOrderCommander(
    actchain.Function[OrderPricerSendData, LimitOrderCommanderSendData]
):
    def __init__(
        self,
        order_size: float,
        max_position_size: float,
        reorder_price_diff: float = 100,
        symbol: str = "FX_BTC_JPY",
    ):
        super(LimitOrderCommander, self).__init__()
        self._symbol = symbol
        self._order_size = order_size
        self._max_position_size = max_position_size
        self._reorder_price_diff = reorder_price_diff

    async def handle(
        self, event: actchain.Event[OrderPricerSendData]
    ) -> LimitOrderCommanderSendData | None:
        limit_order_commands = self.create_commands(
            event.data["orders"],
            event.data["buy_price"],
            event.data["sell_price"],
            event.data["BUY"][0]["price"],
            event.data["SELL"][0]["price"],
            event.data["buy_position"],
            event.data["sell_position"],
        )

        if len(limit_order_commands):
            return LimitOrderCommanderSendData(
                **{
                    **event.data,
                    "limit_order_commands": limit_order_commands,
                }
            )
        else:
            return None

    def create_commands(
        self,
        orders: list[OrderItem],
        buy_price: float,
        sell_price: float,
        best_ask: float,
        best_bid: float,
        buy_position: float,
        sell_position: float,
    ) -> list[LimitOrderCommand]:
        buy_orders = [
            o for o in orders if o["side"] == "BUY" and o["symbol"] == self._symbol
        ]
        sell_orders = [
            o for o in orders if o["side"] == "SELL" and o["symbol"] == self._symbol
        ]

        limit_order_commands: list[LimitOrderCommand] = []
        keep_buy_orders, keep_sell_orders = [], []
        buy_order_sizes, sell_order_sizes = 0.0, 0.0

        for bo in buy_orders:
            buy_order_sizes += bo["size"]
            diff = abs(bo["price"] - buy_price)
            if diff < self._reorder_price_diff:
                keep_buy_orders.append(bo)

        for so in sell_orders:
            sell_order_sizes += so["size"]
            diff = abs(so["price"] - sell_price)
            if diff < self._reorder_price_diff:
                keep_sell_orders.append(so)

        # 雑な部分約定清算処理
        buy_hasu = float("0.00" + str(buy_position)[4:])
        sell_hasu = float("0.00" + str(sell_position)[4:])

        # new limit orders
        ordered = False
        if (
            buy_position + buy_order_sizes < self._max_position_size
            and not RateLimitState().is_being_suspended
        ):
            ordered = True
            limit_order_commands.append(
                {
                    "symbol": self._symbol,
                    "side": "BUY",
                    "price": min(best_bid, buy_price),
                    "size": self._order_size + sell_hasu,
                }
            )

        if (
            sell_position + sell_order_sizes < self._max_position_size
            and not RateLimitState().is_being_suspended
        ):
            ordered = True
            limit_order_commands.append(
                {
                    "symbol": self._symbol,
                    "side": "SELL",
                    "price": max(best_ask, sell_price),
                    "size": self._order_size + buy_hasu,
                }
            )

        if ordered:
            RateLimitState.suspended()

        return limit_order_commands


class CancelOrderCommanderSendData(OrderPricerSendData):
    cancel_order_commands: list[CancelOrderCommand]


class CancelOrderCommander(
    actchain.Function[OrderPricerSendData, CancelOrderCommanderSendData]
):
    def __init__(
        self,
        max_position_size: float,
        reorder_price_diff: float = 100,
        symbol: str = "FX_BTC_JPY",
    ):
        super(CancelOrderCommander, self).__init__()
        self._symbol = symbol
        self._max_position_size = max_position_size
        self._reorder_price_diff = reorder_price_diff

    async def handle(
        self, event: actchain.Event[OrderPricerSendData]
    ) -> CancelOrderCommanderSendData | None:
        cancel_order_commands = self.create_commands(
            event.data["orders"],
            event.data["buy_price"],
            event.data["sell_price"],
            event.data["buy_position"],
            event.data["sell_position"],
            event.data["df_ohlcv"],
        )
        if len(cancel_order_commands):
            return CancelOrderCommanderSendData(
                **{
                    **event.data,
                    "cancel_order_commands": cancel_order_commands,
                }
            )
        else:
            return None

    def create_commands(
        self,
        orders: list[OrderItem],
        buy_price: float,
        sell_price: float,
        buy_position: float,
        sell_position: float,
        df_ohlcv: pd.DataFrame,
    ) -> list[CancelOrderCommand]:
        volatility = df_ohlcv["volatility"].iloc[-1]

        reorder_price_diff = volatility * self._reorder_price_diff

        buy_orders = [
            o for o in orders if o["side"] == "BUY" and o["symbol"] == self._symbol
        ]
        sell_orders = [
            o for o in orders if o["side"] == "SELL" and o["symbol"] == self._symbol
        ]

        cancel_order_commands: list[CancelOrderCommand] = []

        # cancel orders if position size is over max position size
        if buy_position >= self._max_position_size:
            for bo in buy_orders:
                cancel_order_commands.append(
                    {
                        "symbol": self._symbol,
                        "order_id": bo["id"],
                    }
                )

        if sell_position >= self._max_position_size:
            for so in sell_orders:
                cancel_order_commands.append(
                    {
                        "symbol": self._symbol,
                        "order_id": so["id"],
                    }
                )

        # cancel orders if price is too far from limit prices
        for bo in buy_orders:
            diff = abs(bo["price"] - buy_price)
            if diff >= reorder_price_diff:
                cancel_order_commands.append(
                    {
                        "symbol": self._symbol,
                        "order_id": bo["id"],
                    }
                )

        for so in sell_orders:
            diff = abs(so["price"] - sell_price)
            if diff >= reorder_price_diff:
                cancel_order_commands.append(
                    {
                        "symbol": self._symbol,
                        "order_id": so["id"],
                    }
                )

        return cancel_order_commands


class OrderRequesterReceiveData(LimitOrderCommanderSendData):
    ...


class OrderRequesterSendData(TypedDict):
    responses: list[LimitOrderAPIResponse]


class OrderRequester(
    actchain.Function[OrderRequesterReceiveData, OrderRequesterSendData]
):
    def __init__(self, sleep_after_order: int = 1):
        super(OrderRequester, self).__init__()
        self._sleep_after_order = sleep_after_order

    async def handle(
        self, event: Event[OrderRequesterReceiveData]
    ) -> OrderRequesterSendData | None:
        if RateLimitState().is_being_penalized:
            return None

        results = await asyncio.gather(
            *[self.limit_order(cmd) for cmd in event.data["limit_order_commands"]]
        )
        await asyncio.sleep(self._sleep_after_order)

        return {"responses": results}

    @classmethod
    async def limit_order(cls, command: LimitOrderCommand) -> LimitOrderAPIResponse:
        async with pbw.create_client() as client:
            api = pbw.create_api("bitflyer", client, verbose=True)
            resp = await api.limit_order(**command)
            if resp.resp.status == 429:
                RateLimitState().penalized()
            return resp


class OrderCancelerReceiveData(CancelOrderCommanderSendData):
    ...


class OrderCancelerSendData(TypedDict):
    responses: list[CancelOrderAPIResponse]


class OrderCanceler(actchain.Function[OrderCancelerReceiveData, OrderCancelerSendData]):
    def __init__(self):
        super(OrderCanceler, self).__init__()
        self._canceling = set()

    async def handle(
        self, event: Event[OrderCancelerReceiveData]
    ) -> OrderCancelerSendData | None:
        responses = []
        for coro in asyncio.as_completed(
            [self.cancel_order(cmd) for cmd in event.data["cancel_order_commands"]]
        ):
            result = await coro
            if result is not None:
                responses.append(result)
        return OrderCancelerSendData(responses=responses)

    async def cancel_order(
        self, command: CancelOrderCommand
    ) -> CancelOrderAPIResponse | None:
        if RateLimitState().is_being_penalized:
            return None

        id = command["order_id"]

        if id not in self._canceling:
            self._canceling.add(id)
            resp = await self._cancel_order(command)
            self._canceling.remove(id)
            return resp
        else:
            return None

    @classmethod
    async def _cancel_order(
        self, command: CancelOrderCommand
    ) -> CancelOrderAPIResponse:
        async with pbw.create_client() as client:
            api = pbw.create_api("bitflyer", client, verbose=True)
            resp = await api.cancel_order(**command)
            if resp.resp.status == 429:
                RateLimitState.penalized()
            return resp
