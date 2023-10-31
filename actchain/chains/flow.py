from __future__ import annotations

import asyncio
from itertools import chain
from typing import Any, Callable, Self, Type

from actchain.chains.base import Chainable, ChainableStatus
from actchain.chains.junction import JunctionChain
from actchain.chains.pass_through import PassThroughChain
from actchain.event import Event, TDefaultEventData, TReceiveEventData, TSendEventData
from actchain.exceptions import UnsupportedOperationError


class Flow(Chainable[TReceiveEventData, TSendEventData]):
    def __init__(
        self: Flow[TDefaultEventData, TDefaultEventData],
        name: str,
        *,
        anchor_chain: JunctionChain | PassThroughChain | None = None,
        type_receive: Type[TReceiveEventData] | None = None,
        type_send: Type[TSendEventData] | None = None,
    ):
        super(Flow, self).__init__(name, type_receive=type_receive, type_send=type_send)
        self._chainables: list[list[Chainable]] = []
        self._freeze = False
        if anchor_chain is not None and not isinstance(
            anchor_chain, (JunctionChain, PassThroughChain)
        ):
            raise UnsupportedOperationError(
                "anchor_chain must be JunctionChain or PassThroughChain"
            )

        self._anchor_chain: JunctionChain | PassThroughChain | None = anchor_chain

    def __repr__(self) -> str:
        _str = "Flow<"
        for idx, chainables in enumerate(self._chainables):
            _str += f"{list(chainables)}"
            if idx < len(self._chainables) - 1:
                _str += " -> "
        _str += ">"
        return _str

    async def _run_impl(self) -> None:
        coros = []
        for chainables in self._chainables:
            for chainable in chainables:
                if isinstance(chainable, Flow):
                    continue
                coros.append(chainable.run())

        self._status = ChainableStatus.RUNNING
        await asyncio.gather(*coros)
        self._status = ChainableStatus.STOPPING

    def add(self, *chainables: Chainable) -> Self:
        if self._freeze:
            raise UnsupportedOperationError("Cannot add chainable to frozen flow")
        layer = len(self._chainables)
        if layer > 0:
            for prev_chainable in self._chainables[layer - 1]:
                for chainable in chainables:
                    prev_chainable.chain(chainable)
        self._chainables.append(list(chainables))
        return self

    def freeze(self) -> Self:
        """Freeze the flow by placing an anchor chain at the end of the flow.

        After freezing, you cannot add chainables to the flow.
        """
        if self._freeze:
            return self
        if len(self._chainables) == 0:
            raise UnsupportedOperationError("Cannot freeze empty flow")
        self._set_anchor_chain()
        assert self._anchor_chain is not None
        self.add(self._anchor_chain)
        self._freeze = True
        return self

    async def run_forever(
        self,
        cooldown: int = 15,
        onstart: Callable[..., None] | None = None,
        onerror: Callable[[BaseException], None] | None = None,
        clear_queue: bool = True,
    ) -> None:
        coros = []

        if onstart is None:
            _onstart = self._onstart_in_run_forever
        else:

            def _onstart() -> None:
                self._onstart_in_run_forever()
                onstart()

        if onerror is None:
            _onerror = self._onerror_in_run_forever
        else:

            def _onerror(e: BaseException) -> None:
                self._onerror_in_run_forever(e)
                onerror(e)

        for chainables in self._chainables:
            for chainable in chainables:
                if isinstance(chainable, Flow):
                    continue
                coros.append(
                    chainable.run_forever(cooldown, _onstart, _onerror, clear_queue)
                )
        # error handling&restartは各chainableのrun_foreverで行われるので、Flowの中で行う必要はない
        await asyncio.gather(*coros)

    def emit(self, data: TSendEventData) -> None:
        event = self.to_event(data)
        self._last_emit_event = event
        for c in self.next_chains:
            c.trigger(event)

    def trigger(self, event: Event) -> None:
        for c in self._chainables[0]:
            c.trigger(event)

    def chain(self, child: Chainable) -> None:
        # junction chainを最後に追加してFlowをfreezeする。以降addできない。
        self.freeze()
        assert self._anchor_chain is not None
        self._anchor_chain.chain(child)

    def chainables(
        self, *, flat: bool = False
    ) -> list[Chainable] | list[list[Chainable]]:
        if flat:
            return list(chain.from_iterable(self._chainables))
        else:
            return self._chainables

    @property
    def last_event(self) -> Event:
        data = {}
        for c in self._chainables[-1]:
            if c.last_event is not None:
                data.update(c.last_event.data)
        return Event(self.name, data)

    @property
    def next_chains(self) -> list[Chainable]:
        return [] if self._anchor_chain is None else self._anchor_chain.next_chains

    @property
    def prev_chains(self) -> list[Chainable]:
        return [] if len(self._chainables) == 0 else self._chainables[0][0].prev_chains

    @property
    def last_emit_event(self) -> Event[TSendEventData] | None:
        return (
            None if self._anchor_chain is None else self._anchor_chain.last_emit_event
        )

    @property
    def last_trigger_event(self) -> Event[TReceiveEventData] | None:
        return (
            None
            if len(self._chainables) == 0
            else self._chainables[0][0].last_trigger_event
        )

    @property
    def anchor_chain(self) -> JunctionChain | PassThroughChain | None:
        return self._anchor_chain

    @property
    def is_frozen(self) -> bool:
        return self._freeze

    def to_event(self, data: TSendEventData) -> Event[TSendEventData]:
        raise UnsupportedOperationError("Flow cannot convert data to event")

    async def next(self) -> Event[TReceiveEventData]:
        raise UnsupportedOperationError("Flow cannot get next event")

    def _create_connection_as_child(
        self, parent: Chainable[TSendEventData, Any]
    ) -> None:
        if len(self._chainables) == 0:
            raise UnsupportedOperationError("Cannot chain to empty flow")
        for chainable in self._chainables[0]:
            chainable._create_connection_as_child(parent)

    def _onstart_in_run_forever(self) -> None:
        self._status = ChainableStatus.RUNNING

    def _onerror_in_run_forever(self, e: BaseException) -> None:
        self._status = ChainableStatus.ERROR

    def _set_anchor_chain(self) -> None:
        assert len(self._chainables) > 0

        if self._anchor_chain is None:
            # 最後のchainableが複数の場合はjunction chain、単数の場合はpassthrough chain
            if len(self._chainables[-1]) > 1:
                self._anchor_chain = JunctionChain[dict, TSendEventData](
                    f"{self.name}_anchor",
                    mode="all",
                )
            else:
                self._anchor_chain = PassThroughChain[TSendEventData](
                    f"{self.name}_anchor"
                )
        else:
            # 指定の場合はtypeチェック
            if len(self._chainables[-1]) > 1:
                if not isinstance(self._anchor_chain, JunctionChain):
                    raise UnsupportedOperationError(
                        "anchor_chain must be JunctionChain when the last layer has "
                        "multiple chainables"
                    )
            else:
                if not isinstance(self._anchor_chain, PassThroughChain):
                    raise UnsupportedOperationError(
                        "anchor_chain must be PassThroughChain when the last layer has "
                        "a single chainable"
                    )
