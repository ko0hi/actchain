from __future__ import annotations

from typing import Callable, Type

from actchain.chains.base import Chain
from actchain.event import Event, TDefaultEventData, TReceiveEventData


class PassThroughChain(Chain[TReceiveEventData, TReceiveEventData]):
    """PassThroughChain is a chain that passes through events."""

    def __init__(
        self: PassThroughChain[TDefaultEventData],
        name: str,
        *,
        on_handle_cb: Callable[[Event[TReceiveEventData]], None] | None = None,
        type: Type[TReceiveEventData] | None = None,
    ):
        super(PassThroughChain, self).__init__(name, type_receive=type, type_send=type)
        self._on_handle_cb = on_handle_cb

    async def _on_handle(
        self, event: Event[TReceiveEventData]
    ) -> TReceiveEventData | None:
        self._last_handle_event = event
        if self._on_handle_cb:
            self._on_handle_cb(event)
        return event.data
