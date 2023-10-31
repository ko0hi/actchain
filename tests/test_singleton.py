from dataclasses import dataclass

import actchain


def test_basic_singleton_behavior() -> None:
    @dataclass
    class MyState(actchain.State):
        count: int = 0

    s = MyState()
    s_ = MyState()
    s.count += 1

    assert s_.count == 1
    assert MyState().count == 1


def test_independent_singletons() -> None:
    @dataclass
    class State1(actchain.State):
        count: int = 0

    @dataclass
    class State2(actchain.State):
        count: int = 0

    State1().count += 1

    assert State1().count == 1
    assert State2().count == 0
