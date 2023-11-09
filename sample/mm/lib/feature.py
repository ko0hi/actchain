import actchain
from actchain import Event

from .orderbook import ExtendedOrderbookData, ExtendedOrderbookItem


class BuySellRatioEstimatorReceiveData(ExtendedOrderbookData):
    ...


class BuySellRatioEstimatorSendData(BuySellRatioEstimatorReceiveData):
    buy_sell_ratio: float


class BuySellRatioEstimator(
    actchain.Function[BuySellRatioEstimatorReceiveData, BuySellRatioEstimatorSendData]
):
    def __init__(self, k: int = 10):
        super(BuySellRatioEstimator, self).__init__()
        self._k = k

    async def handle(
        self, event: Event[BuySellRatioEstimatorReceiveData]
    ) -> BuySellRatioEstimatorSendData | None:
        return BuySellRatioEstimatorSendData(
            **event.data,
            buy_sell_ratio=self.estimate_by_orderbook(
                event.data["BUY"], event.data["SELL"]
            ),
        )

    def estimate_by_orderbook(
        self,
        buy_items: list[ExtendedOrderbookItem],
        sell_items: list[ExtendedOrderbookItem],
    ) -> float:
        buy_strength = buy_items[self._k - 1]["size_cum_exp_cum"]
        sell_strength = sell_items[self._k - 1]["size_cum_exp_cum"]
        return buy_strength / (buy_strength + sell_strength)
