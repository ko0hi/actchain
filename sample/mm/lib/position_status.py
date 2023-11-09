from typing import AsyncGenerator, TypedDict

import pybotters_wrapper as pbw
from pybotters_wrapper.core.typedefs import PositionItem

import actchain


class PositionStatusData(TypedDict):
    positions: list[PositionItem]


class PositionStatusLoop(actchain.Loop[PositionStatusData]):
    def __init__(self, exchange: str = "bitflyer", symbol: str = "FX_BTC_JPY"):
        super(PositionStatusLoop, self).__init__()
        self._exchange = exchange
        self._symbol = symbol

    async def loop(self) -> AsyncGenerator[PositionStatusData, None]:
        async with pbw.create_client() as client:
            store = pbw.create_store(self._exchange)
            await store.initialize_position(client, product_code=self._symbol)
            await store.subscribe("position", self._symbol).connect(
                client, auto_reconnect=True
            )
            while True:
                yield {"positions": store.position.find({"symbol": self._symbol})}
                await store.position.wait()


class ExtendedPositionStatusData(TypedDict):
    positions: list[PositionItem]
    buy_position: float
    sell_position: float
    net_position: float


class ExtendPositionStatusFunction(
    actchain.Function[PositionStatusData, ExtendedPositionStatusData]
):
    async def handle(
        self, event: actchain.Event[PositionStatusData]
    ) -> ExtendedPositionStatusData:
        return self.to_extend_position_status_data(event.data["positions"])

    @classmethod
    def to_extend_position_status_data(
        cls, positions: list[PositionItem]
    ) -> ExtendedPositionStatusData:
        buy_posi = sum([o["size"] for o in positions if o["side"] == "BUY"])
        sell_posi = sum([o["size"] for o in positions if o["side"] == "SELL"])
        net = buy_posi - sell_posi
        return {
            "positions": positions,
            "buy_position": buy_posi,
            "sell_position": sell_posi,
            "net_position": net,
        }
