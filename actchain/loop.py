from __future__ import annotations

from abc import ABCMeta
from typing import AsyncGenerator, Callable, Generic

from actchain.chains import LoopChain
from actchain.event import TSendEventData
from actchain.exceptions import InvalidOverrideError


class Loop(Generic[TSendEventData], metaclass=ABCMeta):
    def __init__(
        self,
        loop_fn: Callable[[], AsyncGenerator[TSendEventData, None]] | None = None,
        *args,
        **kwargs,
    ):
        self._loop_fn = loop_fn
        self._args = args
        self._kwargs = kwargs

    async def loop(self) -> AsyncGenerator[TSendEventData, None]:
        assert self._loop_fn is not None, "Loop function is not defined."
        agen = self._loop_fn(*self._args, **self._kwargs)
        async for data in agen:
            yield data

    def as_chain(self, name: str | None = None) -> LoopChain:
        if self.loop().__class__.__name__ != "async_generator":
            raise InvalidOverrideError("Loop is not an async generator.")

        if name is None:
            if self._loop_fn:
                name = self._loop_fn.__name__
            else:
                name = "loop"

        return LoopChain(name, self)
