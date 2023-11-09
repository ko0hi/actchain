from typing import AsyncGenerator, TypedDict

import pybotters_wrapper as pbw
from pybotters_wrapper.core.typedefs import OrderItem

import actchain


class OrderStatusData(TypedDict):
    orders: list[OrderItem]


class OrderStatusLoop(actchain.Loop[OrderStatusData]):
    def __init__(self, exchange: str = "bitflyer", symbol: str = "FX_BTC_JPY"):
        super(OrderStatusLoop, self).__init__()
        self._exchange = exchange
        self._symbol = symbol

    async def loop(self) -> AsyncGenerator[OrderStatusData, None]:
        async with pbw.create_client() as client:
            store = pbw.create_store(self._exchange)
            await store.initialize_order(client, product_code=self._symbol)
            await store.subscribe("order", self._symbol).connect(
                client, auto_reconnect=True
            )
            while True:
                yield {"orders": store.order.find({"symbol": self._symbol})}
                await store.order.wait()
