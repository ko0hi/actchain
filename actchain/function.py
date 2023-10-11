import asyncio
from abc import ABCMeta
from typing import Callable, Generic

from actchain.chain import (
    ConcurrentFunctionChain,
    ExclusiveFunctionChain,
    FunctionChain,
)
from actchain.event import Event, TReceiveEventData, TSendEventData


class Function(Generic[TReceiveEventData, TSendEventData], metaclass=ABCMeta):
    def __init__(
        self,
        fn: Callable[[Event[TReceiveEventData]], TSendEventData | None] | None = None,
    ):
        self._fn = fn

    async def handle(self, event: Event[TReceiveEventData]) -> TSendEventData | None:
        assert self._fn is not None, "Function is not defined."
        if asyncio.iscoroutinefunction(self._fn):
            return await self._fn(event)
        else:
            return self._fn(event)

    def as_chain(
        self, name: str | None = None, chain_type: str = "function"
    ) -> FunctionChain | ConcurrentFunctionChain | ExclusiveFunctionChain:
        if chain_type.startswith("function"):
            return FunctionChain(name or self.__class__.__name__, self)
        elif chain_type.startswith("concurrent"):
            return ConcurrentFunctionChain(name or self.__class__.__name__, self)
        elif chain_type.startswith("exclusive"):
            return ExclusiveFunctionChain(name or self.__class__.__name__, self)
        else:
            raise ValueError(f"Unknown chain name: {chain_type}")
