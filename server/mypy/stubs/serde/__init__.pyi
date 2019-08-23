from typing import TypeVar, Type, Dict, Any

T = TypeVar("T")

class Model(object):
    @classmethod
    def from_dict(cls: Type[T], dict: Dict[Any, Any]) -> T:
        ...

    @classmethod
    def from_json(cls: Type[T], json: str) -> T:
        ...

    def to_dict(self) -> Dict[Any, Any]:
        ...

    def to_json(self) -> str:
        ...