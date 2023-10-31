import pytest

import actchain
from actchain.chains.base import Chainable


class ChainableImpl(Chainable):
    async def _run_impl(self) -> None:
        pass


class TestChainable:
    @pytest.mark.asyncio
    async def test_chain(self) -> None:
        c1 = ChainableImpl("c1")
        c2 = ChainableImpl("c2")
        c1.chain(c2)

        assert c1.next_chains == [c2]
        assert c2.prev_chains == [c1]

    @pytest.mark.asyncio
    async def test_emit(self) -> None:
        c1 = ChainableImpl("c1")
        c2 = ChainableImpl("c2")
        c1.chain(c2)
        data1 = {"msg": "hello"}

        c1.emit(data1)
        event2 = await c2.next()

        assert c1.last_emit_event == actchain.Event("c1", data1)
        assert c1.last_trigger_event is None
        assert c2.last_emit_event is None
        assert c2.last_trigger_event == actchain.Event("c1", data1)
        assert event2 == actchain.Event("c1", data1)

    @pytest.mark.asyncio
    async def test_trigger(self) -> None:
        c = ChainableImpl("c")
        data = {"msg": "hello"}
        expected = actchain.Event("c", data)

        c.trigger(expected)
        actual = await c.next()

        assert expected == actual

    @pytest.mark.asyncio
    async def test_raises_type_error_if_non_event_is_passed_to_trigger(self) -> None:
        c = ChainableImpl("c")
        with pytest.raises(TypeError):
            c.trigger({"msg": "hello"})  # type: ignore
