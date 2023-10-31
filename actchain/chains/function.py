from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from actchain.function import Function

from actchain.chains.base import Chain
from actchain.event import Event, TReceiveEventData, TSendEventData


class FunctionChain(Chain[TReceiveEventData, TSendEventData]):
    """FunctionChain is a chain that handles events with a function."""

    def __init__(
        self,
        name: str,
        function: Function[TReceiveEventData, TSendEventData],
    ):
        super(FunctionChain, self).__init__(name)
        self._function = function

    async def _on_handle(
        self, event: Event[TReceiveEventData]
    ) -> TSendEventData | None:
        self._last_handle_event = event
        data = await self._function.handle(event)
        return data


class ConcurrentFunctionChain(FunctionChain[TReceiveEventData, TSendEventData]):
    """ConcurrentFunctionChain is a chain that handles events concurrently.

    Events are handled concurrently and emitted in the order they are completed.
    """

    async def _on_handle(self, event: Event[TReceiveEventData]) -> None:
        self._last_handle_event = event
        task = asyncio.create_task(self._function.handle(event))
        task.add_done_callback(self._emit_after_task)


class ExclusiveFunctionChain(FunctionChain[TReceiveEventData, TSendEventData]):
    """ExclusiveFunctionChain is a chain that handles events exclusively.

    Events are handled exclusively and emitted in the order they are completed. Events
    are ignored when at most one event is being handled.
    """

    def __init__(
        self,
        name: str,
        function: Function[TReceiveEventData, TSendEventData],
    ):
        super(ExclusiveFunctionChain, self).__init__(name, function)
        self._task: asyncio.Task | None = None

    async def _on_handle(self, event: Event[TReceiveEventData]) -> None:
        if self._task is None or self._task.done():
            self._last_handle_event = event
            self._task = asyncio.create_task(self._function.handle(event))
            self._task.add_done_callback(self._emit_after_task)
        return None
