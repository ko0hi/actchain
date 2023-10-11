from __future__ import annotations

from abc import ABCMeta
from typing import Any, AsyncGenerator, Callable

from actchain.chain import LoopChain


class Loop(metaclass=ABCMeta):
    def __init__(
        self,
        loop_fn: Callable[..., AsyncGenerator[Any, None]] | None = None,
        *args,
        **kwargs,
    ):
        self._loop_fn = loop_fn
        self._args = args
        self._kwargs = kwargs

    def loop(self) -> AsyncGenerator[Any, None]:
        assert self._loop_fn is not None, "Loop function is not defined."
        return self._loop_fn(*self._args, **self._kwargs)

    def as_chain(self, name: str | None = None) -> LoopChain:
        return LoopChain(name or self.__class__.__name__, self)
