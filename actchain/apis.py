import asyncio

from actchain.chains import Flow
from actchain.chains.base import Chainable


async def run(*chainables: Chainable, run_forever: bool = False) -> None:
    coro = []
    for chainable in chainables:
        if isinstance(chainable, Flow) and not chainable.is_frozen:
            chainable.freeze()

        if run_forever:
            coro.append(chainable.run_forever())
        else:
            coro.append(chainable.run())
    await asyncio.gather(*coro)
