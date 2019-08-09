from typing import Dict, List, NewType, Optional

from .oauth import OAuthProvider, RefreshableToken, Timestamp, OAuthToken

class Error(BaseException):
    pass

class UserAlreadyExistsError(Error):
    pass

class NoSuchUserError(Error):
    pass

class TwitchUser:
    twitch_id: str
    _user_token: RefreshableToken

    def __init__(self, twitch_id: str, token: RefreshableToken):
        self._twitch_id = twitch_id
        self._user_token = token

    async def GetToken(self, current_time: Timestamp, provider: OAuthProvider) -> OAuthToken:
        return await self._user_token.Get(current_time, provider)

UserId = NewType("UserId", int)

class User:
    user_id: UserId
    created_at: Timestamp
    twitch_user: TwitchUser
    twitch_bot: Optional[TwitchUser]

    def __init__(self, *, user_id: UserId, created_at: Timestamp, twitch_user: TwitchUser, twitch_bot: Optional[TwitchUser] = None):
        self.user_id = user_id
        self.created_at = created_at
        self.twitch_user = twitch_user
        self.twitch_bot = twitch_bot

    def AddBot(self, twitch_bot: TwitchUser) -> None:
        self.twitch_bot = twitch_bot

class UserStore:
    _users: Dict[UserId, User]
    _by_twitch_id: Dict[str, UserId]
    _next_user_id: int

    def __init__(self) -> None:
        self._users = {}
        self._by_twitch_id = {}
        self._next_user_id = 1

    def CreateUser(self, current_time: Timestamp, twitch_user: TwitchUser) -> User:
        if twitch_user.twitch_id in self._by_twitch_id:
            raise UserAlreadyExistsError()

        user = User(
            user_id = UserId(self._next_user_id),
            created_at = current_time,
            twitch_user = twitch_user,
        )

        self._next_user_id += 1
        self._users[user.user_id] = user
        self._by_twitch_id[user.twitch_user.twitch_id] = user.user_id

        return user.user_id

    def DeleteUser(self, user_id: UserId) -> None:
        try:
            user = self._users[user_id]
        except KeyError:
            raise NoSuchUserError()

        del self._by_twitch_id[user.twitch_user.twitch_id]

    def GetUser(self, user_id: UserId) -> User:
        try:
            return self._users[user_id]
        except KeyError:
            raise NoSuchUserError()

    def GetUserByTwitchId(self, twitch_id: str) -> User:
        try:
            return self._users[self._by_twitch_id[twitch_id]]
        except KeyError:
            raise NoSuchUserError()