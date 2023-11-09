import os

import pytest

from .position_status import ExtendPositionStatusFunction, PositionStatusLoop

os.environ["PYBOTTERS_APIS"] = os.path.join(
    os.path.abspath(os.path.dirname(__file__)), "../pybotters-apis.json"
)


@pytest.mark.asyncio
@pytest.mark.skip(reason="This test is for manual testing")
async def test_position() -> None:
    async for msg in PositionStatusLoop("bitflyer", "FX_BTC_JPY").loop():
        print(msg)
        assert msg["positions"] is not None


@pytest.mark.asyncio
async def test_extend_position_status_function() -> None:
    positions = [
        {
            "symbol": "FX_BTC_JPY",
            "side": "SELL",
            "size": 0.01,
            "price": 1000000,
        },
        {"symbol": "FX_BTC_JPY", "side": "SELL", "size": 0.01, "price": 1000000},
    ]

    expected = {
        "positions": positions,
        "buy_position": 0.0,
        "sell_position": 0.02,
        "net_position": -0.02,
    }

    actual = ExtendPositionStatusFunction.to_extend_position_status_data(positions)

    assert expected == actual
