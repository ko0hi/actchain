from __future__ import annotations

from enum import StrEnum
from typing import Any, Callable, Literal, Type, cast

from actchain.chains.base import Chain, Chainable
from actchain.event import Event, TDefaultEventData, TReceiveEventData, TSendEventData
from actchain.exceptions import UnsupportedOperationError


class JunctionChain(Chain[TReceiveEventData, TSendEventData]):
    """JunctionChain "junctions" events from multiple chains. JunctionChain emits an  # noqa: E501
    event when all or any of the previous chains emit an event.

    Args:
        name (str): Name of the chain.
        mode (str): Mode of the junction. "all" or "any".
        transform_fn (Callable[[dict[str, Event]], Any]): Function that generates event data.
    """

    class Mode(StrEnum):
        ALL = "all"
        ANY = "any"

    def __init__(
        self: JunctionChain[TDefaultEventData, TDefaultEventData],
        name: str,
        *,
        mode: Literal["all", "any"] = "all",
        transform_fn: Callable[[dict[str, Event]], Any] | None = None,
        type_receive: Type[TReceiveEventData] | None = None,
        type_send: Type[TSendEventData] | None = None,
    ):
        super(JunctionChain, self).__init__(
            name, type_receive=type_receive, type_send=type_send
        )
        self._mode = mode
        self._last_events: dict[str, Event] = {}
        self._transform_fn = transform_fn

    async def _on_handle(
        self, event: Event[TReceiveEventData]
    ) -> TSendEventData | None:
        self._last_handle_event = event
        self._last_events[event.name] = event
        _last_events = [
            self._last_events.get(c.name, None) is not None for c in self.prev_chains
        ]
        if self._mode == self.Mode.ALL:
            if all(_last_events):
                return self.transform(self._last_events)
            else:
                return None
        elif self._mode == self.Mode.ANY:
            if any(_last_events):
                return self.transform(self._last_events)
            else:
                return None
        else:
            raise UnsupportedOperationError(f"invalid mode: {self._mode}")

    def transform(self, events: dict[str, Event]) -> TSendEventData | None:
        if self._transform_fn is None:
            return cast(TSendEventData, {e.name: e.data for e in events.values()})
        else:
            return self._transform_fn(events)


class AccompanyChain(Chain[TReceiveEventData, TSendEventData]):
    """AccompanyChain accompanies the last event of another chain to the event stream.

    Args:
        name (str): Name of the chain.
        chainable (Chainable): Chainable object to interchange.
    """

    class Mode(StrEnum):
        FLAT = "flat"
        NESTED = "nested"

    def __init__(
        self: AccompanyChain[TDefaultEventData, TDefaultEventData],
        name: str,
        chainable: Chainable,
        *,
        mode: Literal["flat", "nested"] = "flat",
        transform_fn: Callable[[TReceiveEventData, Chainable], TSendEventData | None]
        | None = None,
    ):
        super(AccompanyChain, self).__init__(name)
        self._chainable = chainable
        self._mode = mode
        self._transform_fn = transform_fn

    async def _on_handle(
        self, event: Event[TReceiveEventData]
    ) -> TSendEventData | None:
        if self._chainable.last_emit_event is None:
            return None
        self._last_handle_event = event
        return self._transform(event)

    def _transform(self, event: Event[TReceiveEventData]) -> TSendEventData | None:
        if self._transform_fn is not None:
            return self._transform_fn(event.data, self._chainable)
        elif self._mode == self.Mode.FLAT:
            return cast(
                TSendEventData,
                {
                    **self._chainable.last_emit_event.data,
                    **event.data,
                },
            )
        elif self._mode == self.Mode.NESTED:
            return cast(
                TSendEventData,
                {
                    **event.data,
                    self._chainable.name: self._chainable.last_emit_event.data,
                },
            )
        else:
            raise UnsupportedOperationError(f"Unsupported concatenation: {self._mode}")
