import math
from typing import AsyncGenerator, Generator, TypedDict

import pybotters_wrapper as pbw
from pybotters_wrapper.core.typedefs import OrderbookItem

import actchain


class OrderbookData(TypedDict):
    BUY: list[OrderbookItem]
    SELL: list[OrderbookItem]


class OrderbookLoop(actchain.Loop[OrderbookData]):
    def __init__(self, exchange: str = "bitflyer", symbol: str = "FX_BTC_JPY"):
        super(OrderbookLoop, self).__init__()
        self._exchange = exchange
        self._symbol = symbol

    async def loop(self) -> AsyncGenerator[OrderbookData, None]:
        async with pbw.create_client() as client:
            store = pbw.create_store(self._exchange)
            await store.subscribe("orderbook", self._symbol).connect(
                client, auto_reconnect=True
            )
            while True:
                await store.orderbook.wait()
                yield store.orderbook.sorted({"symbol": self._symbol})


class ExtendedOrderbookItem(OrderbookItem):
    size_cum: float
    size_cum_exp: float
    size_cum_exp_cum: float


class ExtendedOrderbookData(TypedDict):
    BUY: list[ExtendedOrderbookItem]
    SELL: list[ExtendedOrderbookItem]
    mid: float
    spread: float


class ExtendOrderbookFunction(actchain.Function[OrderbookData, ExtendedOrderbookData]):
    def __init__(self, k: int = 10, alpha: float = 1):
        super(ExtendOrderbookFunction, self).__init__()
        self._k = k
        self._alpha = alpha

    async def handle(
        self, event: actchain.Event[OrderbookData]
    ) -> ExtendedOrderbookData:
        return self.extend_orderbook_data(event.data)

    def extend_orderbook_data(self, data: OrderbookData) -> ExtendedOrderbookData:
        extended_buy_items = self.extend_orderbook_items(data["BUY"])
        extended_sell_items = self.extend_orderbook_items(data["SELL"])
        return {
            "BUY": extended_buy_items,
            "SELL": extended_sell_items,
            "mid": self._get_mid(data),
            "spread": self._get_spread(data),
        }

    def extend_orderbook_items(
        self, items: list[OrderbookItem]
    ) -> list[ExtendedOrderbookItem]:
        return [
            ExtendedOrderbookItem(
                **item,
                **cum_feats,
            )
            for item, cum_feats in zip(
                items, self._compute_cumulative_size_features(items)
            )
        ]

    def _compute_cumulative_size_features(
        self, item: list[OrderbookItem]
    ) -> Generator[dict, None, None]:
        size_cum = 0.0
        size_cum_exp_cum = 0.0
        for i in item:
            size_cum += i["size"]
            size_cum_exp = math.exp(-self._alpha * size_cum)
            size_cum_exp_cum += size_cum_exp
            yield {
                "size_cum": size_cum,
                "size_cum_exp": size_cum_exp,
                "size_cum_exp_cum": size_cum_exp_cum,
            }

    @classmethod
    def _get_mid(cls, data: OrderbookData) -> float:
        return (data["BUY"][0]["price"] + data["SELL"][0]["price"]) / 2

    @classmethod
    def _get_spread(cls, data: OrderbookData) -> float:
        return (data["SELL"][0]["price"] - data["BUY"][0]["price"]) / cls._get_mid(data)
