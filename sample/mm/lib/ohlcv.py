import asyncio
from abc import ABCMeta
from typing import AsyncGenerator, Literal, TypeAlias, TypedDict

import httpx
import pandas as pd
from loguru import logger

import actchain
from actchain import Event


class OHLCVData(TypedDict):
    df_ohlcv: pd.DataFrame


TInterval: TypeAlias = Literal["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "8h"]


def _interval_to_seconds(interval: TInterval) -> int:
    if interval.endswith("m"):
        return int(interval[:-1]) * 60
    elif interval.endswith("h"):
        return int(interval[:-1]) * 60 * 60
    else:
        raise ValueError(f"Invalid interval: {interval}")


class _OHLCVLoopBase(actchain.Loop[OHLCVData], metaclass=ABCMeta):
    def __init__(self, interval: TInterval):
        super(_OHLCVLoopBase, self).__init__()
        self._interval = interval
        self._interval_seconds = _interval_to_seconds(interval)

    async def loop(self) -> AsyncGenerator[OHLCVData, None]:
        while True:
            df = await self.fetch_ohlcv()
            if df is not None:
                yield {"df_ohlcv": df}
            await asyncio.sleep(self._interval_seconds)

    async def fetch_ohlcv(self) -> pd.DataFrame | None:
        raise NotImplementedError

    @classmethod
    def _interval_to_seconds(cls, interval: TInterval) -> int:
        if interval.endswith("m"):
            return int(interval[:-1]) * 60
        elif interval.endswith("h"):
            return int(interval[:-1]) * 60 * 60
        else:
            raise ValueError(f"Invalid interval: {interval}")


class CryptoCompareOHLCVLoop(_OHLCVLoopBase):
    def __init__(self, interval: TInterval, exchange: str, fsym: str, tsym: str):
        super(CryptoCompareOHLCVLoop, self).__init__(interval)
        self._exchange = exchange
        self._fsym = fsym
        self._tsym = tsym

    async def fetch_ohlcv(self) -> pd.DataFrame | None:
        async with httpx.AsyncClient() as client:
            uri = "histominute" if self._interval.endswith("m") else "histohour"
            agg = int(self._interval[:-1])
            endpoint = f"https://min-api.cryptocompare.com/data/v2/{uri}"
            resp = await client.get(
                endpoint,
                params={
                    "fsym": self._fsym,
                    "tsym": self._tsym,
                    "limit": 2000,
                    "e": self._exchange,
                    "toTs": -1,
                    "aggregate": agg,
                },
            )

            if resp.status_code == 200:
                return (
                    pd.DataFrame(resp.json()["Data"]["Data"])
                    .rename(columns={"time": "timestamp", "volumefrom": "volume"})[
                        ["timestamp", "open", "high", "low", "close", "volume"]
                    ]
                    .assign(
                        timestamp=lambda _df: pd.to_datetime(_df["timestamp"], unit="s")
                    )
                    .set_index("timestamp")
                )
            else:
                logger.error(f"Failed to fetch OHLCV: {resp}")


class OHLCVLoop(CryptoCompareOHLCVLoop):
    def __init__(self, interval: TInterval, currency: str = "BTC"):
        super(OHLCVLoop, self).__init__(interval, "bitFlyerFX", currency, "JPY")


class ExtendOHLCVFunction(actchain.Function[OHLCVData, OHLCVData]):
    def __init__(self, volatility_window: int = 10):
        super(ExtendOHLCVFunction, self).__init__()
        self._volatility_window = volatility_window

    async def handle(self, event: Event[OHLCVData]) -> OHLCVData | None:
        return {"df_ohlcv": self.compute_features(event.data["df_ohlcv"])}

    def compute_features(self, df: pd.DataFrame) -> pd.DataFrame:
        df["high_minus_low"] = (df["high"] - df["low"]) / 2
        df["volatility"] = df["high_minus_low"].rolling(self._volatility_window).mean()
        return df
