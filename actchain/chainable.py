from __future__ import annotations

import asyncio
import uuid
from abc import ABCMeta, abstractmethod

from actchain.event import Event, TSendEventData


class Chainable(metaclass=ABCMeta):
    def __init__(self, name: str):
        self._name = name or str(uuid.uuid4())
        self._queue: asyncio.Queue = asyncio.Queue()
        self._prev_chains: list[Chainable] = []
        self._next_chains: list[Chainable] = []
        self._last_event: Event = Event(self._name, None)

    def __repr__(self):
        return f"{self.__class__.__name__}({self._name})"

    @abstractmethod
    async def run(self, forever: bool = False) -> None:
        raise NotImplementedError

    async def run_forever(self) -> None:
        await self.run(forever=True)

    def emit(self, data: TSendEventData) -> None:
        event = self.to_event(data)
        self._last_event = event
        for c in self._next_chains:
            c.trigger(event)

    def trigger(self, event: Event) -> None:
        self._queue.put_nowait(event)

    def chain(self, other: Chainable) -> None:
        self._next_chains.append(other)
        other._prev_chains.append(self)

    def to_event(self, data: TSendEventData) -> Event:
        return Event(self._name, data)

    @property
    def name(self) -> str:
        return self._name

    @property
    def last_event(self) -> Event:
        return self._last_event
