# actchain: Asynchronous Crypto Trading Chain

[![pytest](https://github.com/ko0hi/actchain/actions/workflows/pytest.yml/badge.svg)](https://github.com/ko0hi/actchain/actions/workflows/pytest.yml)



## Installation


```bash
pip install actchain
```
Requires Python 3.11 or higher.

## Usage


```python
# An example of using actchain to compute the weighted mid price of the order book

from typing import AsyncGenerator

import asyncio
import actchain
import ccxt.pro as ccxt_pro


async def loop_binance_orderbook() -> AsyncGenerator[dict, None]:
    exchange = ccxt_pro.binance()
    while True:
        yield await exchange.watch_order_book("BTC/USDT")


async def order_book_feature_computation(event: actchain.Event) -> dict:
    best_ask = event.data["asks"][0]
    best_bid = event.data["bids"][0]

    w_mid = (best_ask[0] * best_ask[1] + best_bid[0] * best_bid[1]) / (
        best_ask[1] + best_bid[1]
    )
    mid = (event.data["asks"][0][0] + event.data["bids"][0][0]) / 2
    return {"w_mid": w_mid, "mid": mid}


async def main() -> None:
    flow = (
        actchain.Flow("main")
        .add(actchain.Loop(loop_binance_orderbook).as_chain())
        .add(actchain.Function(order_book_feature_computation).as_chain())
        .add(actchain.Function(lambda event: print(event.data)).as_chain())
    )

    await flow.run()


if __name__ == "__main__":
    asyncio.run(main())


```