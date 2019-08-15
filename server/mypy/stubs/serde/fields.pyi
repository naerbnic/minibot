from typing import Any, TypeVar, Optional as OptTy, Type
from serde import Model

class Field:
    ...

def Str() -> str:
    ...

def Int() -> int:
    ...

T = TypeVar("T")

def Optional(value: T) -> OptTy[T]:
    ...

M = TypeVar("M", bound=Model)

def Nested(ty: Type[M]) -> M:
    ...