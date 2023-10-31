from dataclasses import dataclass
from typing import Any, Generic, Mapping, TypeAlias, TypeVar

TDefaultEventData: TypeAlias = Mapping[Any, Any]
TEventData = TypeVar("TEventData", bound=TDefaultEventData)
TReceiveEventData = TypeVar("TReceiveEventData", bound=TDefaultEventData)
TSendEventData = TypeVar("TSendEventData", bound=TDefaultEventData)


@dataclass
class Event(Generic[TEventData]):
    """Event is a dataclass that represents an event.

    Args:
        name (str): Name of the event.
        data (TEventData): Data of the event.
    """

    name: str
    data: TEventData

    def __repr__(self):
        return f"{self.__class__.__name__}({self.name}/{self.data})"
