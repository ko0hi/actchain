from typing import TypedDict

import pytest

import actchain


@pytest.mark.asyncio
async def test_calls_async_function() -> None:
    expected = {"msg": "hello"}

    async def async_fnc(event: actchain.Event[dict]) -> dict | None:
        return expected

    fnc = actchain.Function(async_fnc)

    actual = await fnc.handle(actchain.Event("test", {}))

    assert expected == actual


@pytest.mark.asyncio
async def test_calls_sync_function() -> None:
    expected = {"msg": "hello"}

    def sync_fnc(event: actchain.Event) -> dict:
        return expected

    fnc = actchain.Function(sync_fnc)

    actual = await fnc.handle(actchain.Event("test", {}))

    assert expected == actual


@pytest.mark.asyncio
@pytest.mark.skip(reason="typecheck check")
async def test_type() -> None:
    class InputData(TypedDict):
        inp: str

    class OutputData(TypedDict):
        out: str

    def sync_fnc(event: actchain.Event[InputData]) -> OutputData:
        # return 1  # mypy error
        return {"out": event.data["inp"]}

    fnc = actchain.Function[InputData, OutputData](sync_fnc)

    # ok
    resp = await fnc.handle(actchain.Event("test", {"inp": "hello"}))
    # mypy error
    # await fnc.handle(actchain.Event("test",  {"inp": "hello", "inp2": "hello2"}))

    assert resp is not None

    print(resp["out"])
    # print(resp["out2"])  # mypy error
