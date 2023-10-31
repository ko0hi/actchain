import asyncio
from typing import Any, AsyncGenerator

import pytest
import pytest_mock

import actchain
from actchain import Event
from actchain.chains.base import Chain


def pass_through_function_chain() -> actchain.FunctionChain:
    return actchain.Function[dict, dict](fn=lambda e: e.data).as_chain("dummy")


class TestChain:
    @pytest.mark.asyncio
    async def test_emit_return_value_of_on_handle_event(
        self, mocker: pytest_mock.MockerFixture
    ) -> None:
        class ChainImpl(Chain):
            async def _on_handle(self, event: Event) -> dict:
                return {"msg": "_on_handle_event"}

        c = ChainImpl("c")
        spy = mocker.spy(c, "emit")

        data = {"msg": "hello"}
        c.trigger(c.to_event(data))
        await c._process_event()

        spy.assert_called_once_with({"msg": "_on_handle_event"})

    @pytest.mark.asyncio
    async def test_no_emit_when_on_handle_event_returns_none(
        self, mocker: pytest_mock.MockerFixture
    ) -> None:
        class ChainImpl(Chain):
            async def _on_handle(self, event: Event) -> None:
                return None

        c = ChainImpl("c")
        spy = mocker.spy(c, "emit")

        c.trigger(c.to_event({}))
        await c._process_event()

        spy.assert_not_called()

    @pytest.mark.asyncio
    async def test_raise_event_handle_error_for_exception_in_on_handle_event(
        self,
    ) -> None:
        class ChainImpl(Chain):
            async def _on_handle(self, event: Event) -> None:
                raise RuntimeError

        c = ChainImpl("c")
        c.trigger(c.to_event({}))
        with pytest.raises(actchain.exceptions.EventHandleError):
            await c._process_event()


class TestLoopChain:
    @pytest.mark.asyncio
    async def test_ok(self, mocker: pytest_mock.MockerFixture) -> None:
        class TestLoop(actchain.Loop):
            async def loop(self):
                yield 1
                yield 2
                yield 3

        loop = TestLoop()
        chain = loop.as_chain()

        spy = mocker.spy(chain, "emit")

        await chain.run()

        assert spy.call_count == 3

    @pytest.mark.asyncio
    async def test_stop_by_error(self, mocker: pytest_mock.MockerFixture) -> None:
        class TestLoop(actchain.Loop):
            async def loop(self):
                yield 1
                yield 2
                raise RuntimeError
                yield 3

        loop = TestLoop()
        chain = loop.as_chain()

        spy = mocker.spy(chain, "emit")

        with pytest.raises(RuntimeError):
            await chain.run()

        assert spy.call_count == 2


class TestFunctionChain:
    @pytest.mark.asyncio
    async def test_serial_processing(self, mocker: pytest_mock.MockerFixture) -> None:
        class TestFunction(actchain.Function):
            async def handle(self, event: actchain.Event) -> actchain.Event:
                return event.data

        chain = TestFunction().as_chain()
        spy = mocker.spy(chain, "emit")

        task = asyncio.create_task(chain.run())
        chain.trigger(chain.to_event({"msg": "1"}))
        chain.trigger(chain.to_event({"msg": "2"}))
        while chain.queue_size > 0:
            await asyncio.sleep(0.1)

        assert spy.call_args_list[0][0][0] == {"msg": "1"}
        assert spy.call_args_list[1][0][0] == {"msg": "2"}
        assert chain.last_emit_event == chain.to_event({"msg": "2"})
        assert chain.last_trigger_event == chain.to_event({"msg": "2"})
        assert chain.last_handle_event == chain.to_event({"msg": "2"})

        task.cancel()

    @pytest.mark.asyncio
    async def test_raise_error_with_non_async_handle_override(self) -> None:
        class TestFunction(actchain.Function):
            def handle(self, event: actchain.Event) -> None:  # type: ignore
                pass

        with pytest.raises(actchain.exceptions.InvalidOverrideError):
            TestFunction().as_chain()

    @pytest.mark.asyncio
    async def test_accept_non_async_handle_with_argument(self) -> None:
        def fn(event: actchain.Event) -> None:
            ...

        actchain.Function(fn).as_chain()


class TestConcurrentFunctionChain:
    @pytest.mark.asyncio
    async def test_concurrent_processing(
        self, mocker: pytest_mock.MockerFixture
    ) -> None:
        class TestFunction(actchain.Function):
            async def handle(self, event: actchain.Event) -> actchain.Event:
                if event.data["msg"] == "1":
                    await asyncio.sleep(0.1)
                else:
                    await asyncio.sleep(0.05)
                return event.data

        chain = TestFunction().as_chain(chain_type="concurrent")
        spy = mocker.spy(chain, "emit")

        task = asyncio.create_task(chain.run())
        chain.trigger(chain.to_event({"msg": "1"}))
        chain.trigger(chain.to_event({"msg": "2"}))
        while spy.call_count < 2:
            await asyncio.sleep(0.1)

        assert spy.call_args_list[0][0][0] == {"msg": "2"}
        assert spy.call_args_list[1][0][0] == {"msg": "1"}
        # 2の方が先に終わるので、last_emit_eventは1になる
        assert chain.last_emit_event == chain.to_event({"msg": "1"})
        # triggerは2が最後に呼ばれているのでlast_trigger_eventは2になる
        assert chain.last_trigger_event == chain.to_event({"msg": "2"})
        # handle自体は1が最初に始まっているのでlast_handle_eventは2になる
        assert chain.last_handle_event == chain.to_event({"msg": "2"})

        task.cancel()


class TestExclusiveFunctionChain:
    @pytest.mark.asyncio
    async def test_exclusive_processing(self, mocker: pytest_mock.MockerFixture):
        class TestFunction(actchain.Function):
            async def handle(self, event: actchain.Event) -> dict:
                await asyncio.sleep(0.05)
                return event.data

        chain = TestFunction().as_chain(chain_type="exclusive")
        spy_on_emit = mocker.spy(chain, "_on_emit")
        spy_handle = mocker.spy(chain._function, "handle")
        spy_emit_after_task = mocker.spy(chain, "_emit_after_task")
        spy_emit = mocker.spy(chain, "emit")

        task = asyncio.create_task(chain.run())
        chain.trigger(chain.to_event({"msg": "1"}))
        chain.trigger(chain.to_event({"msg": "2"}))
        chain.trigger(chain.to_event({"msg": "3"}))
        chain.trigger(chain.to_event({"msg": "4"}))

        assert chain.queue_size == 4
        while chain.queue_size > 0:
            await asyncio.sleep(0.1)

        # exclusive chainは_on_emit eventを発生させない
        spy_on_emit.assert_not_called()
        # handlerは{"msg": "1"}に対して一度だけ呼ばれている
        spy_handle.assert_called_once_with(chain.to_event({"msg": "1"}))
        # emit_after_taskが一度だけ呼ばれている
        spy_emit_after_task.assert_called_once()
        # emitも一度だけ呼ばれている
        spy_emit.assert_called_once_with({"msg": "1"})

        # 1のみが処理されているので、last_emit_eventは1になる
        assert chain.last_emit_event == chain.to_event({"msg": "1"})
        # triggerは4が最後に呼ばれているのでlast_trigger_eventは4になる
        assert chain.last_trigger_event == chain.to_event({"msg": "4"})
        # 1のみが処理されているので、last_handle_eventは1になる
        assert chain.last_handle_event == chain.to_event({"msg": "1"})

        task.cancel()


class TestJunctionChain:
    @pytest.fixture
    def chain1(self) -> actchain.FunctionChain:
        return actchain.Function[dict, dict](fn=lambda e: e.data).as_chain(
            name="chain1"
        )

    @pytest.fixture
    def chain2(self) -> actchain.FunctionChain:
        return actchain.Function[dict, dict](fn=lambda e: e.data).as_chain(
            name="chain2"
        )

    @pytest.mark.asyncio
    async def test_all_mode(
        self,
        chain1: actchain.Chain,
        chain2: actchain.Chain,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        junction_chain = actchain.JunctionChain("junction", mode="all")
        spy_emit = mocker.spy(junction_chain, "emit")
        chain1.chain(junction_chain)
        chain2.chain(junction_chain)
        chain1.trigger(chain1.to_event({"msg": 1}))
        chain2.trigger(chain2.to_event({"msg": 2}))
        chain2.trigger(chain2.to_event({"msg": 22}))

        # chain1を発火({"msg": 1})
        await chain1._process_event()
        # junction_chainはqueue_sizeが1になる
        assert junction_chain.queue_size == 1
        # junction_chainを発火
        await junction_chain._process_event()
        # junction_chainはqueue_sizeが0になる
        assert junction_chain.queue_size == 0
        # chain2のイベントが空なのでemitされない
        spy_emit.assert_not_called()
        # junction_chainはchain1のイベントをlast_eventとして保持する
        assert junction_chain._last_events == {"chain1": chain1.to_event({"msg": 1})}
        # chain2を発火({"msg": 2})
        await chain2._process_event()
        # junction_chainはqueue_sizeが1になる
        assert junction_chain.queue_size == 1
        # junction_chainを発火
        await junction_chain._process_event()
        # junction_chainはqueue_sizeが0になる
        assert junction_chain.queue_size == 0
        # chain1/chain2のイベントがあるのでemitされる + 1回目のcall
        spy_emit.assert_called_once_with(
            {
                "chain1": {"msg": 1},
                "chain2": {"msg": 2},
            }
        )
        # junction_chainはchain1/chain2のイベントをlast_eventとして保持する
        assert junction_chain._last_events == {
            "chain1": chain1.to_event({"msg": 1}),
            "chain2": chain2.to_event({"msg": 2}),
        }
        # chain2を発火({"msg": 22})
        await chain2._process_event()
        # junction_chainはqueue_sizeが1になる
        assert junction_chain.queue_size == 1
        # junction_chainを発火
        await junction_chain._process_event()
        # junction_chainはqueue_sizeが0になる
        assert junction_chain.queue_size == 0
        # chain1/chain2のイベントがあるのでemitされる
        spy_emit.assert_called_with(
            {
                "chain1": {"msg": 1},
                "chain2": {"msg": 22},
            }
        )
        # junction_chainはchain1/chain2のイベントをlast_eventとして保持する
        assert junction_chain._last_events == {
            "chain1": chain1.to_event({"msg": 1}),
            "chain2": chain2.to_event({"msg": 22}),
        }

    @pytest.mark.asyncio
    async def test_any_mode(
        self,
        chain1: actchain.Chain,
        chain2: actchain.Chain,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        junction_chain: actchain.JunctionChain = actchain.JunctionChain(
            "junction", mode="any"
        )
        spy_emit = mocker.spy(junction_chain, "emit")
        chain1.chain(junction_chain)
        chain2.chain(junction_chain)
        chain1.trigger(chain1.to_event({"msg": 1}))
        chain2.trigger(chain2.to_event({"msg": 2}))
        chain2.trigger(chain2.to_event({"msg": 22}))

        # chain1を発火({"msg": 1})
        await chain1._process_event()
        # junction_chainはqueue_sizeが1になる
        assert junction_chain.queue_size == 1
        # junction_chainを発火
        await junction_chain._process_event()
        # junction_chainはqueue_sizeが0になる
        assert junction_chain.queue_size == 0
        # chain1のイベントがあるのでemitされる + 1回目のcall
        spy_emit.assert_called_once_with({"chain1": {"msg": 1}})
        # junction_chainはchain1のイベントをlast_eventとして保持する
        assert junction_chain._last_events == {"chain1": chain1.to_event({"msg": 1})}
        # chain2を発火({"msg": 2})
        await chain2._process_event()
        # junction_chainはqueue_sizeが1になる
        assert junction_chain.queue_size == 1
        # junction_chainを発火
        await junction_chain._process_event()
        # junction_chainはqueue_sizeが0になる
        assert junction_chain.queue_size == 0
        # chain1/chain2のイベントがあるのでemitされる
        spy_emit.assert_called_with(
            {
                "chain1": {"msg": 1},
                "chain2": {"msg": 2},
            }
        )
        # junction_chainはchain1/chain2のイベントをlast_eventとして保持する
        assert junction_chain._last_events == {
            "chain1": chain1.to_event({"msg": 1}),
            "chain2": chain2.to_event({"msg": 2}),
        }
        # chain2を発火({"msg": 22})
        await chain2._process_event()
        # junction_chainはqueue_sizeが1になる
        assert junction_chain.queue_size == 1
        # junction_chainを発火
        await junction_chain._process_event()
        # junction_chainはqueue_sizeが0になる
        assert junction_chain.queue_size == 0
        # chain1/chain2のイベントがあるのでemitされる
        spy_emit.assert_called_with(
            {
                "chain1": {"msg": 1},
                "chain2": {"msg": 22},
            }
        )
        # junction_chainはchain1/chain2のイベントをlast_eventとして保持する
        assert junction_chain._last_events == {
            "chain1": chain1.to_event({"msg": 1}),
            "chain2": chain2.to_event({"msg": 22}),
        }


class TestAccompanyChain:
    @pytest.mark.asyncio
    async def test_flat_mode(self) -> None:
        chain1 = pass_through_function_chain()
        chain2 = pass_through_function_chain()
        chain3 = pass_through_function_chain()

        # accompany_chain <- chain3
        accompany_chain = actchain.AccompanyChain("accompany", chain3)

        # chain1 -> chain2
        chain1.chain(chain2)
        # chain2 -> accompany_chain
        # chain3 ------|
        chain2.chain(accompany_chain)
        chain1.trigger(chain1.to_event({"msg1": 1}))
        chain1.trigger(chain2.to_event({"msg1": 12}))
        chain3.trigger(chain3.to_event({"msg3": 31}))
        chain3.trigger(chain3.to_event({"msg3": 32}))

        # chain1を発火({"msg1": 1} -> chain2)
        await chain1._process_event()
        # chain2を発火({"msg1": 1} -> accompany_chain)
        await chain2._process_event()
        # chain3を発火({"msg3": 31} -> accompany_chain)
        await chain3._process_event()
        # accompany_chainはqueue_sizeが1になる
        assert accompany_chain.queue_size == 1
        # accompany_chainを発火
        await accompany_chain._process_event()
        # accompany_chainはqueue_sizeが0になる
        assert accompany_chain.queue_size == 0
        # 本流のイベント（{"msg1": 1}）に支流のラストイベント（{"msg3": 31}）が足される
        assert accompany_chain.last_emit_event == accompany_chain.to_event(
            {"msg1": 1, "msg3": 31}
        )
        # chain1を発火({"msg2": 12} -> chain2)
        await chain1._process_event()
        # chain2を発火({"msg2": 12} -> accompany_chain)
        await chain2._process_event()
        # accompany_chainはqueue_sizeが1になる
        assert accompany_chain.queue_size == 1
        # chain3を発火({"msg3": 32} -> accompany_chain)
        await chain3._process_event()
        # accompany_chainを発火
        await accompany_chain._process_event()
        # accompany_chainはqueue_sizeが0になる
        assert accompany_chain.queue_size == 0
        # 本流のイベント（{"msg1": 12}）に支流のラストイベント（{"msg3": 32}）が足される
        assert accompany_chain.last_emit_event == accompany_chain.to_event(
            {"msg1": 12, "msg3": 32}
        )

    @pytest.mark.asyncio
    async def test_nested_mode(self) -> None:
        chain1 = pass_through_function_chain()
        chain2 = pass_through_function_chain()
        chain3 = pass_through_function_chain()

        # accompany_chain <- chain3
        accompany_chain = actchain.AccompanyChain("accompany", chain3, mode="nested")

        # chain1 -> chain2
        chain1.chain(chain2)
        # chain2 -> accompany_chain
        # chain3 ------|
        chain2.chain(accompany_chain)
        chain1.trigger(chain1.to_event({"msg1": 1}))
        chain1.trigger(chain2.to_event({"msg1": 12}))
        chain3.trigger(chain3.to_event({"msg3": 31}))
        chain3.trigger(chain3.to_event({"msg3": 32}))

        # chain1を発火({"msg1": 1} -> chain2)
        await chain1._process_event()
        # chain2を発火({"msg1": 1} -> accompany_chain)
        await chain2._process_event()
        # chain3を発火({"msg3": 31} -> accompany_chain)
        await chain3._process_event()
        # accompany_chainはqueue_sizeが1になる
        assert accompany_chain.queue_size == 1
        # accompany_chainを発火
        await accompany_chain._process_event()
        # accompany_chainはqueue_sizeが0になる
        assert accompany_chain.queue_size == 0
        # 本流のイベント（{"msg1": 1}）に支流のラストイベント（{"msg3": 31}）が足される
        assert accompany_chain.last_emit_event == accompany_chain.to_event(
            {"msg1": 1, "dummy": {"msg3": 31}}
        )
        # chain1を発火({"msg2": 12} -> chain2)
        await chain1._process_event()
        # chain2を発火({"msg2": 12} -> accompany_chain)
        await chain2._process_event()
        # accompany_chainはqueue_sizeが1になる
        assert accompany_chain.queue_size == 1
        # chain3を発火({"msg3": 32} -> accompany_chain)
        await chain3._process_event()
        # accompany_chainを発火
        await accompany_chain._process_event()
        # accompany_chainはqueue_sizeが0になる
        assert accompany_chain.queue_size == 0
        # 本流のイベント（{"msg1": 12}）に支流のラストイベント（{"msg3": 32}）が足される
        assert accompany_chain.last_emit_event == accompany_chain.to_event(
            {"msg1": 12, "dummy": {"msg3": 32}}
        )


class TestIntervalSamplingChain:
    @pytest.fixture
    def loop(self) -> actchain.LoopChain:
        class _Loop(actchain.Loop):
            async def loop(self) -> AsyncGenerator[Any, None]:
                yield {"n": 1}
                await asyncio.sleep(0.1)
                yield {"n": 2}
                await asyncio.sleep(0.9)
                yield {"n": 3}

        return _Loop().as_chain()

    @pytest.mark.asyncio
    async def test_ok(
        self, loop: actchain.LoopChain, mocker: pytest_mock.MockerFixture
    ) -> None:
        sampling_chain = actchain.IntervalSamplingChain[dict]("sample", interval=1)
        spy_sampling_chain_emit = mocker.spy(sampling_chain, "emit")
        spy_sampling_chain_trigger = mocker.spy(sampling_chain, "trigger")
        loop.chain(sampling_chain)

        loop_task = asyncio.create_task(loop.run())
        sampling_task = asyncio.create_task(sampling_chain.run())

        await asyncio.sleep(1.2)

        # イベントのトリガー（受信）は3回
        assert spy_sampling_chain_trigger.call_count == 3
        # イベントのエミット（送信）は2回
        assert spy_sampling_chain_emit.call_count == 2
        # {"n": 2} は飛ばされている
        assert spy_sampling_chain_emit.call_args_list[0][0][0] == {"n": 1}
        assert spy_sampling_chain_emit.call_args_list[1][0][0] == {"n": 3}

        loop_task.cancel()
        sampling_task.cancel()
