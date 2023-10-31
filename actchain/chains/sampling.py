from __future__ import annotations

import time
from typing import Type

from actchain.chains.base import Chain
from actchain.event import Event, TDefaultEventData, TReceiveEventData


class IntervalSamplingChain(Chain[TReceiveEventData, TReceiveEventData]):
    """IntervalSamplingChain samples events by a given interval.

    Args:
        name (str): Name of the chain.
        interval (int): Interval in seconds.
    """

    def __init__(
        self: IntervalSamplingChain[TDefaultEventData],
        name: str,
        interval: int,
        *,
        type: Type[TReceiveEventData] | None = None,
    ):
        super(IntervalSamplingChain, self).__init__(
            name, type_receive=type, type_send=type
        )
        self._interval = interval
        self._last_emit_ts: float | None = None

    async def _on_handle(
        self, event: Event[TReceiveEventData]
    ) -> TReceiveEventData | None:
        if self._should_thinning_out():
            return None
        else:
            self._last_handle_event = event
            self._last_emit_ts = time.time()
            return event.data

    def _should_thinning_out(self) -> bool:
        if self._last_emit_ts is None:
            return False
        else:
            return time.time() - self._last_emit_ts < self._interval
