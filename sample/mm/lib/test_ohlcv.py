import numpy as np
import pandas as pd
import pytest

from .ohlcv import (
    OHLCVLoop,
    ExtendOHLCVFunction,
    TInterval,
    _interval_to_seconds,
)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "interval", ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "8h"]
)
async def test_bitflyer_ohlcv(interval: TInterval):
    df = await OHLCVLoop(interval).fetch_ohlcv()
    assert df is not None
    assert df.index.name == "timestamp"
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert (df.index[1] - df.index[0]).total_seconds() == _interval_to_seconds(interval)


@pytest.mark.asyncio
async def test_extend_ohlcv_function():
    df_input = pd.DataFrame(
        {
            "open": [1, 2, 3],
            "high": [2, 3, 4],
            "low": [0, 1, 2],
            "close": [1, 2, 3],
        }
    )
    df_expected = pd.DataFrame(
        {
            "open": [1, 2, 3],
            "high": [2, 3, 4],
            "low": [0, 1, 2],
            "close": [1, 2, 3],
            "high_minus_low": [1.0, 1.0, 1.0],
            "volatility": [np.nan, np.nan, 1.0],
        }
    )

    df_actual = ExtendOHLCVFunction(volatility_window=3).compute_features(df_input)
    pd.testing.assert_frame_equal(df_actual, df_expected)
