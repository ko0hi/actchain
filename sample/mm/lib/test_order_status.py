import os

import pytest

from .order_status import OrderStatusLoop

os.environ["PYBOTTERS_APIS"] = os.path.join(
    os.path.abspath(os.path.dirname(__file__)), "../pybotters-apis.json"
)


@pytest.mark.asyncio
@pytest.mark.skip(reason="This test is for manual testing")
async def test_position() -> None:
    async for msg in OrderStatusLoop("bitflyer", "FX_BTC_JPY").loop():
        print(msg)
        assert msg["orders"] is not None
