import asyncio

from typing import Generic, TypeVar, Optional, Awaitable, Generator, cast, Callable, Dict, Tuple

import secrets

T = TypeVar("T")

class Error(BaseException):
    pass

class AlreadyFinishedError(Error):
    pass

class OneShot(Generic[T]):
    evt: asyncio.Event
    value: Optional[T]
    is_cancelled: bool

    def __init__(self) -> None:
        self.evt = asyncio.Event()
        self.value = None
        self.is_cancelled = False

    def Send(self, value: T) -> None:
        if self.evt.is_set():
            raise AlreadyFinishedError()
        self.value = value
        self.evt.set()

    def Cancel(self) -> None:
        if self.evt.is_set():
            raise AlreadyFinishedError()
        self.is_cancelled = True
        self.evt.set()

    async def Wait(self) -> T:
        await self.evt.wait()
        if self.is_cancelled:
            raise asyncio.CancelledError()
        return cast(T, self.value)

class CallbackSet(Generic[T]):
    callbacks: Dict[str, OneShot[T]]

    def MakeCallback(self) -> Tuple[str, Awaitable[T]]:
        oneshot = OneShot() # type: OneShot[T]
        nonce = secrets.token_urlsafe(30)

        self.callbacks[nonce] = oneshot

        return (nonce, oneshot.Wait())

    def SendCallback(self, nonce: str, value: T) -> None:
        self.callbacks[nonce].Send(value)
        del self.callbacks[nonce]
