from __future__ import annotations

import enum


class MsgType(enum.Enum):
    """Represents types of messages that can be sent by the server."""

    #: Code provided by the client is either invalid or refers to a running session.
    INVALID_SESSION = "invalid_session"
    #: The action failed because the client is not in any session.
    NOT_IN_SESSION = "not_in_session"
    #: Session start failed because the client is not the session owner.
    NOT_SESSION_OWNER = "not_session_owner"
    #: Player name is already taken by someone else in this session.
    PLAYER_NAME_ALREADY_TAKEN = "player_name_already_taken"

    #: *Some* client joined a session. Possibly after creating it.
    SESSION_JOIN = "session_join"
    #: *Some* client left a session. Possibly while joining a different session.
    SESSION_LEAVE = "session_leave"
    #: Session started.
    SESSION_START = "session_start"
    #: Session ended. Either someone won or all other players left the session.
    SESSION_END = "session_end"
