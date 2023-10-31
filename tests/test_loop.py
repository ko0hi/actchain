from typing import AsyncGenerator

import pytest

import actchain


@pytest.mark.asyncio
async def test_override() -> None:
    class TestLoop(actchain.Loop):
        async def loop(self) -> AsyncGenerator[int, None]:
            yield 1
            yield 2
            yield 3

    loop = TestLoop()
    aiterator = loop.loop()

    assert await anext(aiterator) == 1
    assert await anext(aiterator) == 2
    assert await anext(aiterator) == 3


@pytest.mark.asyncio
async def test_specify_with_argument() -> None:
    async def loop_fn() -> AsyncGenerator[int, None]:
        yield 1
        yield 2
        yield 3

    loop = actchain.Loop(loop_fn=loop_fn)  # type: ignore
    aiterator = loop.loop()

    assert await anext(aiterator) == 1
    assert await anext(aiterator) == 2
    assert await anext(aiterator) == 3


@pytest.mark.asyncio
async def test_as_chain() -> None:
    class TestLoop(actchain.Loop):
        async def loop(self) -> AsyncGenerator[int, None]:
            yield 1
            yield 2
            yield 3

    loop = TestLoop()
    chain = loop.as_chain()

    assert chain.name == "loop"
    assert chain._loop == loop
    assert isinstance(chain, actchain.LoopChain)


@pytest.mark.asyncio
async def test_raises_error_if_loop_fn_is_not_async() -> None:
    class TestLoop(actchain.Loop):
        def loop(self):
            yield 1
            yield 2
            yield 3

    with pytest.raises(actchain.exceptions.InvalidOverrideError):
        TestLoop().as_chain()
