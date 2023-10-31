from __future__ import annotations

import asyncio
import uuid
from abc import ABCMeta, abstractmethod
from enum import StrEnum
from typing import Any, Callable, Generic, Type, overload

from loguru import logger

from actchain.event import Event, TDefaultEventData, TReceiveEventData, TSendEventData
from actchain.exceptions import ChainableAlreadyRunningError, EventHandleError


class ChainableStatus(StrEnum):
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


class Connection:
    def __init__(self):
        self._parents: list[Chainable] = []
        self._children: list[Chainable] = []

    def add_parent(self, chainable: Chainable) -> None:
        self._parents.append(chainable)

    def add_child(self, chainable: Chainable) -> None:
        self._children.append(chainable)

    @property
    def parents(self) -> list[Chainable]:
        return self._parents

    @property
    def children(self) -> list[Chainable]:
        return self._children


class Chainable(Generic[TReceiveEventData, TSendEventData], metaclass=ABCMeta):
    """Chainable is a base class for chainable objects.

    Chainable objects are objects that can be chained with other chainable objects.
    Chainable objects can emit events to other chainable objects.

    Args:
        name (str): Name of the chainable object.

    Attributes:
        name (str): Name of the chainable object.
        status (ChainableStatus): Status of the chainable object.
        last_event (Event): Last event emitted by the chainable object.
    """

    @overload
    def __init__(self: Chainable[dict, dict], name: str):
        ...

    @overload
    def __init__(
        self: Chainable[TReceiveEventData, TSendEventData],
        name: str,
        *,
        type_receive: Type[TReceiveEventData] | None = None,
        type_send: Type[TSendEventData] | None = None,
    ) -> None:
        ...

    def __init__(
        self: Chainable[TReceiveEventData, TSendEventData],
        name: str,
        *,
        type_receive: Type[TReceiveEventData] | None = None,
        type_send: Type[TSendEventData] | None = None,
    ):
        self._name = name or str(uuid.uuid4())
        self._queue: asyncio.Queue = asyncio.Queue()
        self._connection = Connection()
        self._last_emit_event: Event[TSendEventData] | None = None
        self._last_trigger_event: Event[TReceiveEventData] | None = None
        self._status = ChainableStatus.STOPPING

        self._type_receive = type_receive | dict
        self._type_send = type_send | dict

    def __repr__(self):
        return f"{self.__class__.__name__}({self._name})"

    @abstractmethod
    async def _run_impl(self) -> None:
        raise NotImplementedError

    async def run(self) -> None:
        """Run the chainable object."""
        if self._status == ChainableStatus.RUNNING:
            raise ChainableAlreadyRunningError(self._name)

        self._status = ChainableStatus.RUNNING
        await self._run_impl()
        self._status = ChainableStatus.STOPPING

    async def run_forever(
        self,
        cooldown: int = 15,
        onstart: Callable[..., None] | None = None,
        onerror: Callable[[BaseException], None] | None = None,
        clear_queue: bool = True,
    ) -> None:
        """Run the chainable object forever.  # noqa: E501

        Args:
            cooldown (int, optional): Cooldown time in seconds. Defaults to 15.
            onstart (Callable[..., None], optional): Start handler. Defaults to None.
            onerror (Callable[[BaseException], None], optional): Error handler. Defaults to None.
            clear_queue (bool, optional): Clear the queue when the chainable object is down. Defaults to True.
        """

        @logger.catch(onerror=onerror)
        async def _run() -> None:
            if onstart is not None:
                onstart()
            await self.run()

        while True:
            await _run()  # type: ignore
            self._status = ChainableStatus.ERROR
            logger.error(f"Chain {self._name} is down, restarting...")
            await asyncio.sleep(cooldown)

            if clear_queue:
                while self._queue.qsize() > 0:
                    await self._queue.get()

    def emit(self, data: TSendEventData) -> None:
        """Emit an event to the next chainable objects."""
        event = self.to_event(data)
        self._last_emit_event = event
        for c in self.next_chains:
            c.trigger(event)

    def trigger(self, event: Event[TReceiveEventData]) -> None:
        """Trigger an event to the chainable object."""
        if not isinstance(event, Event):
            raise TypeError(f"event must be an instance of Event, not {type(event)}")

        self._last_trigger_event = event
        self._queue.put_nowait(event)

    def chain(self, child: Chainable[TSendEventData, Any]) -> None:
        """Chain the chainable object with another chainable object."""
        self._create_connection_as_parent(child)
        child._create_connection_as_child(self)

    def to_event(self, data: TSendEventData) -> Event[TSendEventData]:
        return Event(self._name, data)

    async def next(self) -> Event[TReceiveEventData]:
        """Wait for the next event."""
        return await self._queue.get()

    @property
    def name(self) -> str:
        return self._name

    @property
    def status(self) -> ChainableStatus:
        return self._status

    @property
    def queue_size(self) -> int:
        return self._queue.qsize()

    @property
    def connection(self) -> Connection:
        return self._connection

    @property
    def next_chains(self) -> list[Chainable]:
        return self._connection.children

    @property
    def prev_chains(self) -> list[Chainable]:
        return self._connection.parents

    @property
    def last_emit_event(self) -> Event[TSendEventData] | None:
        return self._last_emit_event

    @property
    def last_trigger_event(self) -> Event[TReceiveEventData] | None:
        return self._last_trigger_event

    @property
    def last_event(self) -> Event[TReceiveEventData] | None:
        return self._last_trigger_event

    def _create_connection_as_parent(
        self, child: Chainable[TSendEventData, Any]
    ) -> None:
        self._connection.add_child(child)

    def _create_connection_as_child(
        self, parent: Chainable[TSendEventData, Any]
    ) -> None:
        self._connection.add_parent(parent)


class Chain(
    Generic[TReceiveEventData, TSendEventData],
    Chainable[TReceiveEventData, TSendEventData],
    metaclass=ABCMeta,
):
    @overload
    def __init__(self: Chain[TDefaultEventData, TDefaultEventData], name: str):
        ...

    @overload
    def __init__(
        self: Chain[TReceiveEventData, TSendEventData],
        name: str,
        *,
        type_receive: Type[TReceiveEventData] | None = None,
        type_send: Type[TSendEventData] | None = None,
    ) -> None:
        ...

    def __init__(
        self,
        name: str,
        *,
        type_receive: Type[TReceiveEventData] | None = None,
        type_send: Type[TSendEventData] | None = None,
    ):
        super(Chain, self).__init__(
            name, type_receive=type_receive, type_send=type_send
        )
        self._last_handle_event: Event[TReceiveEventData] | None = None

    async def _run_impl(self) -> None:
        while True:
            await self._process_event()

    async def _process_event(self) -> None:
        event = await self._on_wait()
        try:
            data = await self._on_handle(event)
        except Exception:
            raise EventHandleError(event)
        else:
            if data is None:
                return

            await self._on_emit(data)

    async def _on_wait(self) -> Event[TReceiveEventData]:
        return await self.next()

    async def _on_emit(self, data: TSendEventData) -> None:
        self.emit(data)

    def _emit_after_task(self, task: asyncio.Task) -> None:
        result = task.result()
        if result is not None:
            self.emit(result)

    @abstractmethod
    async def _on_handle(
        self, event: Event[TReceiveEventData]
    ) -> TSendEventData | None:
        raise NotImplementedError

    @property
    def last_handle_event(self) -> Event[TReceiveEventData] | None:
        return self._last_handle_event
