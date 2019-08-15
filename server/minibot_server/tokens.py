from typing import Dict, Mapping, Any, NewType, Set, Optional, List
from .users import UserId
from .oauth import Timestamp

import secrets
import attr

TokenId = NewType("TokenId", str)

@attr.s(auto_attribs=True)
class Token:
    id: TokenId
    user: UserId
    desc: str
    created_at: Timestamp


class TokenStore:
    _tokens: Dict[TokenId, Token]
    _tokens_by_user: Dict[UserId, Set[TokenId]]

    def __init__(self) -> None:
        self._tokens = {}
        self._tokens_by_user = {}

    def CreateToken(self, user_id: UserId, current_time: Timestamp) -> Token:
        token_id = TokenId(secrets.token_urlsafe(30))
        token = Token(id = token_id, user = user_id, created_at = current_time)
        self._tokens[token_id] = token
        self._tokens_by_user.setdefault(user_id, set()).add(token_id)
        return token

    def FindToken(self, token_id: TokenId) -> Optional[Token]:
        return self._tokens.get(token_id, None)

    def FindUserTokens(self, user_id: UserId) -> List[Token]:
        return [self._tokens[id] for id in self._tokens_by_user.get(user_id, set())]

    def RevokeToken(self, token_id: TokenId) -> None:
        try:
            token = self._tokens[token_id]
        except KeyError:
            return
        del self._tokens[token_id]
        self._tokens_by_user[token.user].remove(token_id)

    def RevokeUserTokens(self, user_id: UserId) -> None:
        try:
            user_tokens = self._tokens_by_user[user_id]
        except KeyError:
            return
        for user_token in user_tokens:
            del self._tokens[user_token]
        del self._tokens_by_user[user_id]