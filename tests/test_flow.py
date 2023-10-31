import asyncio
from typing import AsyncGenerator

import pytest
import pytest_mock

import actchain


class TestFlow:
    @pytest.fixture
    def loop_123(self) -> actchain.LoopChain:
        class Loop123(actchain.Loop):
            async def loop(self) -> AsyncGenerator[int, None]:
                yield 1
                yield 2
                yield 3

        return Loop123().as_chain("loop_123")

    @pytest.fixture
    def add_1(self) -> actchain.FunctionChain:
        class Add1Function(actchain.Function):
            async def handle(self, event: actchain.Event) -> int:
                return event.data + 1

        return Add1Function().as_chain("add_1_function")

    @pytest.fixture
    def add_2(self) -> actchain.FunctionChain:
        class Add2Function(actchain.Function):
            async def handle(self, event: actchain.Event) -> int:
                return event.data + 2

        return Add2Function().as_chain("add_2_function")

    class TestMethodAdd:
        def test_single_chain(
            self,
            loop_123: actchain.LoopChain,
            add_1: actchain.FunctionChain,
            add_2: actchain.FunctionChain,
        ) -> None:
            flow = actchain.Flow("test").add(loop_123).add(add_1).add(add_2)
            assert [[loop_123], [add_1], [add_2]] == flow.chainables()
            assert loop_123.prev_chains == []
            assert loop_123.next_chains == [add_1]
            assert add_1.prev_chains == [loop_123]
            assert add_1.next_chains == [add_2]
            assert add_2.prev_chains == [add_1]
            assert add_2.next_chains == []

        def test_multiple_chains(
            self,
            loop_123: actchain.LoopChain,
            add_1: actchain.FunctionChain,
            add_2: actchain.FunctionChain,
        ) -> None:
            flow = actchain.Flow("test").add(loop_123).add(add_1, add_2)
            assert [[loop_123], [add_1, add_2]] == flow.chainables()
            assert loop_123.prev_chains == []
            assert loop_123.next_chains == [add_1, add_2]
            assert add_1.prev_chains == [loop_123]
            assert add_1.next_chains == []
            assert add_2.prev_chains == [loop_123]
            assert add_2.next_chains == []

        def test_raises_error_if_adding_chain_after_freeze(
            self,
            loop_123: actchain.LoopChain,
            add_1: actchain.FunctionChain,
            add_2: actchain.FunctionChain,
        ) -> None:
            flow = actchain.Flow("test").add(loop_123).add(add_1).freeze()
            with pytest.raises(actchain.exceptions.UnsupportedOperationError):
                flow.add(add_2)

    class TestMethodFreeze:
        def test_adds_anchor_chain_at_the_last_layer(
            self, loop_123: actchain.LoopChain, add_1: actchain.FunctionChain
        ) -> None:
            flow = actchain.Flow("test").add(loop_123).add(add_1)
            assert [[loop_123], [add_1]] == flow.chainables()
            assert not flow.is_frozen
            assert flow.anchor_chain is None

            flow.freeze()
            assert flow.is_frozen
            assert flow.anchor_chain is not None
            assert [[loop_123], [add_1], [flow._anchor_chain]] == flow.chainables()
            assert flow.anchor_chain.prev_chains == [add_1]

        def test_changes_nothing_if_already_frozen(
            self, loop_123: actchain.LoopChain, add_1: actchain.FunctionChain
        ) -> None:
            flow = actchain.Flow("test").add(loop_123).add(add_1)
            flow.freeze()
            assert flow.is_frozen
            assert flow.anchor_chain is not None
            assert [[loop_123], [add_1], [flow._anchor_chain]] == flow.chainables()
            assert flow.anchor_chain.prev_chains == [add_1]

            flow.freeze()
            assert flow.is_frozen
            assert flow.anchor_chain is not None
            assert [[loop_123], [add_1], [flow._anchor_chain]] == flow.chainables()
            assert flow.anchor_chain.prev_chains == [add_1]

        def test_adds_pass_through_chain_when_the_last_layer_has_a_single_chain(
            self, loop_123: actchain.LoopChain, add_1: actchain.FunctionChain
        ) -> None:
            flow = actchain.Flow("test").add(loop_123).add(add_1).freeze()
            assert isinstance(flow.chainables(flat=True)[-1], actchain.PassThroughChain)

        def test_adds_junction_chain_when_the_last_layer_has_multiple_chains(
            self, loop_123: actchain.LoopChain, add_1: actchain.FunctionChain
        ) -> None:
            flow = actchain.Flow("test").add(loop_123).add(add_1, add_1).freeze()
            assert isinstance(flow.chainables(flat=True)[-1], actchain.JunctionChain)

        def test_creates_chain_on_a_specified_anchor_chain(
            self, loop_123: actchain.LoopChain, add_1: actchain.FunctionChain
        ) -> None:
            anchor_chain = actchain.PassThroughChain("pass_through")
            flow = (
                actchain.Flow("test", anchor_chain=anchor_chain)
                .add(loop_123)
                .add(add_1)
            )
            assert flow.anchor_chain == anchor_chain
            assert anchor_chain.prev_chains == []
            assert flow.anchor_chain.prev_chains == []

            flow.freeze()

            assert anchor_chain.prev_chains == [add_1]
            assert flow.anchor_chain.prev_chains == [add_1]

        def test_raises_error_if_flow_is_empty(self) -> None:
            flow = actchain.Flow("test")
            with pytest.raises(actchain.exceptions.UnsupportedOperationError):
                flow.freeze()

        def test_raises_error_with_pass_through_anchor_chain_and_multiple_chainables_at_the_last_layer(
            self,
            loop_123: actchain.LoopChain,
            add_1: actchain.FunctionChain,
            add_2: actchain.FunctionChain,
        ) -> None:
            flow = (
                actchain.Flow(
                    "test", anchor_chain=actchain.PassThroughChain("pass_through")
                )
                .add(loop_123)
                .add(add_1, add_2)
            )

            with pytest.raises(actchain.exceptions.UnsupportedOperationError):
                flow.freeze()

        def test_raises_error_with_junction_anchor_chain_and_single_chainable_at_the_last_layer(
            self, loop_123: actchain.LoopChain, add_1: actchain.FunctionChain
        ):
            flow = (
                actchain.Flow(
                    "test", anchor_chain=actchain.JunctionChain("junction", mode="all")
                )
                .add(loop_123)
                .add(add_1)
            )

            with pytest.raises(actchain.exceptions.UnsupportedOperationError):
                flow.freeze()

    class TestMethodChainables:
        def test_layered(
            self, loop_123: actchain.LoopChain, add_1: actchain.FunctionChain
        ) -> None:
            flow = actchain.Flow("test").add(loop_123).add(add_1).freeze()
            assert [[loop_123], [add_1], [flow.anchor_chain]] == flow.chainables()

        def test_flat(
            self, loop_123: actchain.LoopChain, add_1: actchain.FunctionChain
        ):
            flow = actchain.Flow("test").add(loop_123).add(add_1).freeze()
            assert [loop_123, add_1, flow.anchor_chain] == flow.chainables(flat=True)

    class TestMethodChain:
        def test_calls_freeze_and_adds_chain_to_anchor_chain(
            self,
            loop_123: actchain.LoopChain,
            add_1: actchain.FunctionChain,
            add_2: actchain.FunctionChain,
            mocker: pytest_mock.MockerFixture,
        ) -> None:
            flow = actchain.Flow("test").add(loop_123).add(add_1)
            spy_freeze = mocker.spy(flow, "freeze")
            assert flow.next_chains == []

            flow.chain(add_2)

            spy_freeze.assert_called_once()
            assert flow.next_chains == [add_2]

    @pytest.mark.asyncio
    async def test_simple_flow(
        self, loop_123: actchain.LoopChain, add_1: actchain.FunctionChain
    ) -> None:
        flow = actchain.Flow[dict, dict]("test").add(loop_123).add(add_1).freeze()

        task = asyncio.create_task(flow.run())

        while not loop_123.done():
            await asyncio.sleep(0.1)

        task.cancel()

    def test_chained_by_other_chainable(
        self,
        add_1: actchain.FunctionChain,
        add_2: actchain.FunctionChain,
    ) -> None:
        flow = actchain.Flow("test").add(add_1).freeze()

        add_2.chain(flow)

        assert flow.prev_chains == [add_2]
        assert add_2.next_chains == [flow]

    def test_raises_error_if_passing_invalid_anchor_chain(
        self, add_1: actchain.FunctionChain
    ) -> None:
        with pytest.raises(actchain.exceptions.UnsupportedOperationError):
            actchain.Flow(
                "test",
                anchor_chain=add_1,  # type: ignore
            )
