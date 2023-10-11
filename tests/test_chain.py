import asyncio

import pytest
import pytest_mock


import actchain
from actchain.exceptions import InvalidOverrideError


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
                return event

        chain = TestFunction().as_chain()
        spy = mocker.spy(chain, "emit")

        task = asyncio.create_task(chain.run())
        chain.trigger(actchain.Event("test", {"msg": "1"}))
        chain.trigger(actchain.Event("test", {"msg": "2"}))
        while spy.call_count < 2:
            await asyncio.sleep(0.1)

        assert spy.call_args_list[0][0][0].data["msg"] == "1"
        assert spy.call_args_list[1][0][0].data["msg"] == "2"

        task.cancel()

    @pytest.mark.asyncio
    async def test_raise_error_with_non_async_handle_override(self) -> None:
        class TestFunction(actchain.Function):
            def handle(self, event: actchain.Event) -> None:  # type: ignore
                pass

        with pytest.raises(InvalidOverrideError):
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
                return event

        chain = TestFunction().as_chain(chain_type="concurrent")
        spy = mocker.spy(chain, "emit")

        task = asyncio.create_task(chain.run())
        chain.trigger(actchain.Event("test", {"msg": "1"}))
        chain.trigger(actchain.Event("test", {"msg": "2"}))
        while spy.call_count < 2:
            await asyncio.sleep(0.1)

        # ２の方が先に終わるはず
        assert spy.call_args_list[0][0][0].data["msg"] == "2"
        assert spy.call_args_list[1][0][0].data["msg"] == "1"

        task.cancel()


class TestExclusiveFunctionChain:
    @pytest.mark.asyncio
    async def test_exclusive_processing(self, mocker: pytest_mock.MockerFixture):
        class TestFunction(actchain.Function):
            async def handle(self, event: actchain.Event) -> dict:
                await asyncio.sleep(0.1)
                return {"msg": "a"}

        chain = TestFunction().as_chain(chain_type="exclusive")
        spy = mocker.spy(chain, "_on_emit_event")

        task = asyncio.create_task(chain.run())
        chain.trigger(actchain.Event("test", {"msg": "1"}))
        chain.trigger(actchain.Event("test", {"msg": "2"}))
        chain.trigger(actchain.Event("test", {"msg": "3"}))
        chain.trigger(actchain.Event("test", {"msg": "4"}))
        await asyncio.sleep(0.05)

        assert isinstance(spy.call_args_list[0][0][0], asyncio.Task)
        # 1を実行中なので、2・3・4はスキップされる
        assert spy.call_args_list[1][0][0] is None
        assert spy.call_args_list[2][0][0] is None
        assert spy.call_args_list[3][0][0] is None

        task.cancel()
