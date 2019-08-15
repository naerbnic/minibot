from typing import TypeVar, Type, Dict, Any

T = TypeVar("T")

class Model(object):
    @classmethod
    def from_dict(cls: Type[T], dict: Dict[Any, Any]) -> T:
        ...

    def to_dict(self) -> Dict[Any, Any]:
        ...