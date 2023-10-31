from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from actchain.loop import Loop

from actchain.chains.base import Chainable
from actchain.event import TDefaultEventData, TSendEventData


class LoopChain(Chainable[TDefaultEventData, TSendEventData]):
    def __init__(
        self: LoopChain[TDefaultEventData],
        name: str,
        loop: Loop[TSendEventData],
    ):
        super(LoopChain, self).__init__(name)
        self._loop = loop
        self._done = False

    async def _run_impl(self) -> None:
        gen = self._loop.loop()
        async for data in gen:
            self.emit(data)
        self._done = True

    def done(self) -> bool:
        return self._done
