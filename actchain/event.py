from dataclasses import dataclass
from typing import Generic, TypeVar

TEventData = TypeVar("TEventData", bound=dict)
TReceiveEventData = TypeVar("TReceiveEventData", bound=dict)
TSendEventData = TypeVar("TSendEventData", bound=dict)


@dataclass
class Event(Generic[TEventData]):
    name: str
    data: TEventData

    def __repr__(self):
        return f"{self.__class__.__name__}({self.name})"
