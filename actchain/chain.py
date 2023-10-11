from __future__ import annotations

import asyncio
import time
import traceback
from abc import ABCMeta, abstractmethod
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Callable

from loguru import logger

if TYPE_CHECKING:
    from actchain.function import Function
    from actchain.loop import Loop

from actchain.chainable import Chainable
from actchain.event import Event, TEventData
from actchain.exceptions import UnsupportedError, InvalidOverrideError


class Chain(Chainable, metaclass=ABCMeta):
    async def run(self, forever: bool = False) -> None:
        while True:
            event = await self._on_wait_event()
            try:
                result = await self._on_handle_event(event)
            except Exception:
                logger.error(
                    f"Chain {self.name} failed to handle event {event}: "
                    f"{traceback.format_exc()}"
                )
            else:
                await self._on_emit_event(result)

    async def _on_wait_event(self) -> Event:
        return await self._queue.get()

    async def _on_emit_event(self, result: Any) -> None:
        if result is not None:
            self.emit(result)

    def _emit_callback(self, task: asyncio.Task) -> None:
        result = task.result()
        if result is not None:
            self.emit(result)

    @abstractmethod
    async def _on_handle_event(self, event: Event) -> Any:
        raise NotImplementedError


class LoopChain(Chainable):
    def __init__(self, name: str, loop: Loop):
        super(LoopChain, self).__init__(name)
        self._loop = loop

    async def run(self, forever: bool = False) -> None:
        while True:
            try:
                async for data in self._loop.loop():
                    self.emit(data)
            except Exception as e:
                logger.error(
                    f"Chain {self.name} failed to handle loop: {traceback.format_exc()}"
                )
                if not forever:
                    raise e

            if not forever:
                break


class FunctionChain(Chain):
    def __init__(self, name: str, function: Function):
        super(FunctionChain, self).__init__(name)
        self._function = function
        if not asyncio.iscoroutinefunction(self._function.handle):
            raise InvalidOverrideError(
                "Function's handle method must be a coroutine function"
            )

    async def _on_handle_event(self, event: Event) -> Any:
        return await self._function.handle(event)


class ConcurrentFunctionChain(FunctionChain):
    async def _on_handle_event(self, event: Event) -> asyncio.Task:
        return asyncio.create_task(self._function.handle(event))

    async def _on_emit_event(self, result: asyncio.Task) -> None:
        result.add_done_callback(self._emit_callback)


class ExclusiveFunctionChain(FunctionChain):
    def __init__(self, name: str, function: Function):
        super(ExclusiveFunctionChain, self).__init__(name, function)
        self._task: asyncio.Task | None = None

    async def _on_handle_event(self, event: Event) -> asyncio.Task | None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._function.handle(event))
            return self._task
        else:
            return None

    async def _on_emit_event(self, result: asyncio.Task | None) -> None:
        if result is not None:
            result.add_done_callback(self._emit_callback)


class JunctionChain(Chain):
    class Mode(StrEnum):
        ALL = "all"

    def __init__(
        self,
        name: str,
        *,
        mode: str = "all",
        event_data_generator: Callable[[dict[str, Event]], Any] | None = None,
    ):
        super(JunctionChain, self).__init__(name)
        self._mode = mode
        self._last_events: dict[str, Event] = {}
        self._event_data_generator = event_data_generator

    async def _on_handle_event(self, event: Event[TEventData]) -> Any:
        self._last_events[event.name] = event
        if self._mode == self.Mode.ALL:
            if all(
                [
                    self._last_events.get(c._name, None) is not None
                    for c in self._prev_chains
                ]
            ):
                return self._generate_event_data(self._last_events)
            else:
                return None
        else:
            raise UnsupportedError(f"invalid mode: {self._mode}")

    def _generate_event_data(self, events: dict[str, Event]) -> Any:
        if self._event_data_generator is None:
            return {e.name: e.data for e in events.values()}
        else:
            return self._event_data_generator(events)


class InterchangeChain(Chain):
    class Mode(StrEnum):
        FLAT = "flat"
        NESTED = "nested"

    def __init__(self, name: str, chainable: Chainable, *, mode: str = "flat"):
        super(InterchangeChain, self).__init__(name)
        self._chainable = chainable
        self._mode = mode

    async def _on_handle_event(self, event: Event) -> Any:
        if self._mode == self.Mode.FLAT:
            return {
                **self._chainable.last_event.data,
                **event.data,
            }
        elif self._mode == self.Mode.NESTED:
            return {
                **event.data,
                self._chainable.last_event.name: self._chainable.last_event.data,
            }
        else:
            raise UnsupportedError(f"Unsupported concatenation: {self._mode}")


class IntervalThinningChain(Chain):
    def __init__(self, name: str, interval: int):
        super(IntervalThinningChain, self).__init__(name)
        self._interval = interval
        self._last_emit_ts: int = None

    async def _on_handle_event(self, event: Event) -> Any:
        if self._should_thinning_out():
            return None
        else:
            self._last_emit_ts = time.time()
            return event.data

    def _should_thinning_out(self) -> bool:
        if self._last_emit_ts is None:
            return False
        else:
            return time.time() - self._last_emit_ts < self._interval
