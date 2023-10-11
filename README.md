# actchain: Asynchronous Crypto Trading Chain

```python
from typing import AsyncGenerator

import asyncio
import actchain
import ccxt.async_support as ccxt
import ccxt.pro as ccxt_pro


async def loop_binance_orderbook() -> AsyncGenerator[dict, None]:
    exchange = ccxt_pro.binance()
    while True:
        yield await exchange.watch_order_book("BTC/USDT")
        await asyncio.sleep(5)


async def order_book_feature_computation(event: actchain.Event) -> dict:
    best_ask = event.data["asks"][0]
    best_bid = event.data["bids"][0]

    w_mid = (best_ask[0] * best_ask[1] + best_bid[0] * best_bid[1]) / (
        best_ask[1] + best_bid[1]
    )
    mid = (event.data["asks"][0][0] + event.data["bids"][0][0]) / 2
    return {"w_mid": w_mid, "mid": mid}


async def order_request(event: actchain.Event) -> dict:
    if event.data["w_mid"] > event.data["mid"]:
        return {"side": "buy", "size": 0.1}
    else:
        return {"side": "sell", "size": 0.1}


async def send_order(event: actchain.Event) -> None:
    exchange = ccxt.binance({...})
    await exchange.create_order(
        symbol="BTC/USDT",
        type="market",
        side=event.data["side"],
        amount=event.data["size"],
    )


async def main() -> None:
    flow = (
        actchain.Flow()
        .add(actchain.Loop(loop_binance_orderbook).as_chain())
        .add(actchain.Function(order_book_feature_computation).as_chain())
        .add(actchain.Function(order_request).as_chain())
        .add(actchain.Function(send_order).as_chain())
    )

    await flow.run()


if __name__ == "__main__":
    asyncio.run(main())

```