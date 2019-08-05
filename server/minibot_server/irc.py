import asyncio
import re
from typing import Tuple, Optional, Union, Dict, List, Awaitable
import typing


class BytesMuncher:
    _bytestr: bytes

    def __init__(self, bytestr: bytes):
        self._bytestr = bytestr

    def SplitToSpace(self) -> bytes:
        m = re.match(rb'([^ ]+)($|[ ]+)', self._bytestr)
        if m:
            self._bytestr = self._bytestr[m.end():]
            return m.group(1)
        else:
            raise ValueError()

    def HasFirstChar(self, firstchar: bytes) -> bool:
        if not self._bytestr:
            return False
        return self._bytestr[0] == ord(firstchar)

    def IsEmpty(self) -> bool:
        return not self._bytestr

    def Rest(self) -> bytes:
        return self._bytestr


def UnescapeTagValue(tag_value: bytes) -> bytes:
    result = bytearray()
    curr_index = 0
    while curr_index < len(tag_value):
        curr_byte = tag_value[curr_index]
        curr_index += 1
        if curr_byte != ord(b'\\'):
            result.append(curr_byte)
        elif curr_index != len(tag_value):
            next_byte = tag_value[curr_index]
            curr_index += 1
            if next_byte == ord(b':'):
                result.append(ord(b';'))
            elif next_byte == ord(b's'):
                result.append(ord(b' '))
            elif next_byte == ord(b'\\'):
                result.append(ord(b'\\'))
            elif next_byte == ord(b'r'):
                result.append(ord(b'\r'))
            elif next_byte == ord(b'n'):
                result.append(ord(b'\n'))
            else:
                result.append(next_byte)
    return bytes(result)


def EscapeTagValue(tag_value: bytes) -> bytes:
    result = bytearray()
    for b in tag_value:
        if b == ord(b';'):
            result.extend(rb'\:')
        elif b == ord(b' '):
            result.extend(rb'\s')
        elif b == ord(b'\\'):
            result.extend(rb'\\')
        elif b == ord(b'\r'):
            result.extend(rb'\r')
        elif b == ord(b'\n'):
            result.extend(rb'\n')
        else:
            result.append(b)
    return bytes(result)


class Message:
    @staticmethod
    def Parse(msg_data: bytes) -> "Message":
        tags_part = None  # type: Union[bytes, None]
        prefix = None  # type: Union[bytes, None]
        args = []  # type: List[bytes]
        muncher = BytesMuncher(msg_data)
        if muncher.HasFirstChar(b'@'):
            tags_part = muncher.SplitToSpace()[1:]
        if muncher.HasFirstChar(b':'):
            prefix = muncher.SplitToSpace()[1:]
        command = muncher.SplitToSpace().upper()
        while not muncher.IsEmpty() and not muncher.HasFirstChar(b':'):
            arg = muncher.SplitToSpace()
            if arg is None:
                raise ValueError()
            args.append(arg)
        if not muncher.IsEmpty():
            args.append(muncher.Rest()[1:])

        tags = {}  # type: Dict[bytes, bytes]
        if tags_part is not None:
            for tag_entry in tags_part.split(b';'):
                entry_parts = tag_entry.split(b'=', 1)
                if len(entry_parts) == 1:
                    tags[entry_parts[0]] = b''
                else:
                    (key, value) = entry_parts
                    tags[key] = UnescapeTagValue(value)

        return Message(command, *args, tags=tags, prefix=prefix)

    tags: Dict[bytes, bytes]
    prefix: Optional[bytes]
    command: bytes
    args: List[bytes]

    def __init__(self, command: bytes, *args: bytes, tags: Dict[bytes, bytes] = {}, prefix: Optional[bytes] = None):
        self.tags = tags
        self.prefix = prefix
        self.command = command
        self.args = list(args)

    def __str__(self) -> str:
        return f"Message({self.command}, {self.args}, tags={self.tags}, prefix={self.prefix})"

    def ToWireFormat(self) -> bytes:
        tag_pieces = []  # type: List[bytes]
        for (k, v) in self.tags.items():
            if v:
                tag_pieces.append(k + b'=' + EscapeTagValue(v))
            else:
                tag_pieces.append(k)

        line_pieces = []  # type: List[bytes]
        if tag_pieces:
            line_pieces.append(b'@' + b';'.join(tag_pieces))

        if self.prefix is not None:
            line_pieces.append(b':' + self.prefix)

        line_pieces.append(self.command)

        for arg in self.args[:-1]:
            line_pieces.append(arg)

        if self.args:
            line_pieces.append(b':' + self.args[-1])

        return b' '.join(line_pieces)


_T = typing.TypeVar("_T")


class CloseableQueue(typing.Generic[_T]):
    _inner_queue: asyncio.Queue[_T]
    _close_event: asyncio.Event
    _empty_event: asyncio.Event

    def __init__(self, maxsize: int = 0):
        self._inner_queue = asyncio.Queue(maxsize)
        self._close_event = asyncio.Event()
        self._empty_event = asyncio.Event()

    async def Get(self) -> Optional[_T]:
        if not self._close_event.is_set():
            async def closing() -> None:
                await self._close_event.wait()
                return None
            for f in asyncio.as_completed((self._inner_queue.get(), closing())):
                value = await f
                if value is not None:
                    # self._inner_queue.task_done()
                    return value
                else:
                    if not self._close_event.is_set():
                        raise RuntimeError(
                            "Close event should be set on a none value")
                    # We're closed
                    break
        if not self._inner_queue.empty():
            value = self._inner_queue.get_nowait()
            if self._inner_queue.empty():
                self._empty_event.set()
            if value is True:
                raise ValueError()
            return value
        return None

    async def Put(self, val: _T) -> None:
        if self._close_event.is_set():
            raise RuntimeError()
        await self._inner_queue.put(val)

    def Close(self) -> None:
        self._close_event.set()
        if self._inner_queue.empty():
            self._empty_event.set()

    async def WaitUntilEmpty(self) -> None:
        await self._empty_event.wait()


class IrcClientChannel:
    """A low-level channel connected to an IRC server.

    Can read messages from and write messages to the channel. Does no other
    protocol parsing.
    """
    @classmethod
    async def Connect(cls, host: str, port: int) -> "IrcClientChannel":
        reader, writer = await asyncio.open_connection(host, port, ssl=True)

        client = cls(reader, writer)
        await client._Start()
        return client

    _read_task: asyncio.Task[None]
    _write_task: asyncio.Task[None]
    _read_queue: CloseableQueue[Message]
    _write_queue: CloseableQueue[Message]
    _reader: asyncio.StreamReader
    _writer: asyncio.StreamWriter

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self._reader = reader
        self._writer = writer
        self._read_queue = CloseableQueue(10)
        self._write_queue = CloseableQueue(10)

    async def _Start(self) -> None:
        self._read_task = asyncio.create_task(self._process_reader())
        self._write_task = asyncio.create_task(self._process_writer())

    def Write(self, msg: Message) -> Awaitable[None]:
        """Writes a message to the server.

        The returned future can be used for flow control.
        """
        return asyncio.create_task(self._write_queue.Put(msg))

    async def Read(self) -> Optional[Message]:
        """Reads a message from the server, or returns None if
        there are no more messages to read.
        """
        return await self._read_queue.Get()

    def CloseWrite(self) -> None:
        """Closes the write half of the connection.
        """
        self._write_queue.Close()

    async def _process_reader(self) -> None:
        # Read a single IRC message and remove the trailing newline
        try:
            while True:
                data = await self._reader.readuntil(b'\r\n')
                data = data[:-2]
                await self._read_queue.Put(Message.Parse(data))
        except asyncio.IncompleteReadError:
            # We could close for a ton of reasons. Just ignore any incomplete
            # data
            pass
        self._read_queue.Close()
        self._write_queue.Close()

    async def _process_writer(self) -> None:
        while True:
            message = await self._write_queue.Get()  # type: Optional[Message]
            if message is None:
                break
            wire_message = message.ToWireFormat()
            await self._writer.drain()
            self._writer.write(wire_message + b'\r\n')

        if self._writer.can_write_eof():
            await self._writer.drain()
            self._writer.write_eof()
        else:
            self._writer.close()
            await self._writer.wait_closed()

    async def WaitForExit(self) -> None:
        await self._read_task
        await self._write_task
        await self._read_queue.WaitUntilEmpty()


async def TestTwitchIrc() -> None:
    client = await IrcClientChannel.Connect("irc.chat.twitch.tv", 6697)
    await client.Write(Message(b'CAP', b'REQ', b'twitch.tv/membership twitch.tv/tags twitch.tv/commands'))
    await client.Write(Message(b'PASS', b'oauth:' + b''))
    await client.Write(Message(b'NICK', b''))
    await client.Write(Message(b'CAP', b'END'))
    await client.Write(Message(b'QUIT'))
    while True:
        msg = await client.Read()
        if msg is None:
            break
        print(msg)
    await client.WaitForExit()


def TestTwitchIrcMain() -> None:
    asyncio.run(TestTwitchIrc())
