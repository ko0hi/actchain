import asyncio
from typing import Self

from actchain.chainable import Chainable
from actchain.event import Event, TSendEventData
from actchain.exceptions import UnsupportedError


class Flow(Chainable):
    def __init__(self, name: str | None = None):
        super(Flow, self).__init__(name)
        self._chainables: list[tuple[Chainable]] = []

    def __repr__(self) -> str:
        _str = "Flow(\n"
        for chainables in self._chainables:
            _str += f"  {chainables}\n"
        _str += ")"
        return _str

    def add(self, *chainables: Chainable) -> Self:
        layer = len(self._chainables)
        if layer > 0:
            for prev_chainable in self._chainables[layer - 1]:
                for chainable in chainables:
                    prev_chainable.chain(chainable)
        self._chainables.append(chainables)
        return self

    async def run(self, forever: bool = False) -> None:
        coros = []
        for chainables in self._chainables:
            for chainable in chainables:
                if isinstance(chainable, Flow):
                    continue
                coros.append(chainable.run(forever))
        await asyncio.gather(*coros)

    async def emit(self, data: TSendEventData) -> None:
        raise UnsupportedError("Flow cannot emit events")

    def trigger(self, event: Event) -> None:
        raise UnsupportedError("Flow cannot trigger events")

    def chain(self, other: Chainable) -> None:
        assert (
            len(self._chainables) > 0
        ), "Flow must have at least one layer for chaining"
        for chainable in self._chainables[-1]:
            chainable.chain(other)

    @property
    def last_event(self) -> Event:
        data = {}
        for c in self._chainables[-1]:
            data.update(c.last_event.data)
        return Event(self.name, data)
