from __future__ import annotations

import asyncio
from abc import ABCMeta
from typing import Any, Callable, Coroutine, Generic, Literal, Optional, Union, overload

from actchain.chains import (
    ConcurrentFunctionChain,
    ExclusiveFunctionChain,
    FunctionChain,
)
from actchain.event import Event, TDefaultEventData, TReceiveEventData, TSendEventData
from actchain.exceptions import InvalidOverrideError


class Function(Generic[TReceiveEventData, TSendEventData], metaclass=ABCMeta):
    @overload
    def __init__(self):
        ...

    @overload
    def __init__(self: Function[TDefaultEventData, TDefaultEventData]):
        ...

    @overload
    def __init__(
        self: Function[TReceiveEventData, TSendEventData],
        fn: Callable[[Event[TReceiveEventData]], TSendEventData | None],
    ):
        ...

    @overload
    def __init__(
        self: Function[TReceiveEventData, TSendEventData],
        fn: Callable[
            [Event[TReceiveEventData]], Coroutine[Any, Any, TSendEventData | None]
        ],
    ):
        ...

    def __init__(
        self: Function[TDefaultEventData, TDefaultEventData],
        fn: Optional[
            Union[
                Callable[[Event[TReceiveEventData]], TSendEventData | None],
                Callable[
                    [Event[TReceiveEventData]],
                    Coroutine[Any, Any, TSendEventData | None],
                ],
            ]
        ] = None,
    ):
        self._fn = fn

    async def handle(self, event: Event[TReceiveEventData]) -> TSendEventData | None:
        assert self._fn is not None, "Function is not defined."
        if asyncio.iscoroutinefunction(self._fn):
            return await self._fn(event)
        else:
            return self._fn(event)

    @overload
    def as_chain(self) -> FunctionChain[TReceiveEventData, TSendEventData]:
        ...

    @overload
    def as_chain(self, name: str) -> FunctionChain[TReceiveEventData, TSendEventData]:
        ...

    @overload
    def as_chain(
        self, *, chain_type: Literal["function"]
    ) -> FunctionChain[TReceiveEventData, TSendEventData]:
        ...

    @overload
    def as_chain(
        self, *, chain_type: Literal["concurrent"]
    ) -> ConcurrentFunctionChain[TReceiveEventData, TSendEventData]:
        ...

    @overload
    def as_chain(
        self, *, chain_type: Literal["exclusive"]
    ) -> ExclusiveFunctionChain[TReceiveEventData, TSendEventData]:
        ...

    @overload
    def as_chain(
        self, name: str, chain_type: Literal["exclusive"]
    ) -> ExclusiveFunctionChain[TReceiveEventData, TSendEventData]:
        ...

    def as_chain(
        self,
        name: str | None = None,
        chain_type: Literal["function", "concurrent", "exclusive"] = "function",
    ) -> (
        FunctionChain[TReceiveEventData, TSendEventData]
        | ConcurrentFunctionChain[TReceiveEventData, TSendEventData]
        | ExclusiveFunctionChain[TReceiveEventData, TSendEventData]
    ):
        if name is None:
            if self._fn is not None:
                name = self._fn.__name__
            else:
                name = "function"

        if not asyncio.iscoroutinefunction(self.handle):
            raise InvalidOverrideError("Function is not a coroutine function.")

        if chain_type.startswith("function"):
            return FunctionChain(name, self)
        elif chain_type.startswith("concurrent"):
            return ConcurrentFunctionChain(name, self)
        elif chain_type.startswith("exclusive"):
            return ExclusiveFunctionChain(name, self)
        else:
            raise ValueError(f"Unknown chain name: {chain_type}")
