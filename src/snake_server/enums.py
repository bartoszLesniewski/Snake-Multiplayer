from __future__ import annotations

import enum


class MsgType(enum.Enum):
    """Represents types of messages that can be sent by the server."""

    #: Code provided by the client is either invalid or refers to a running session.
    INVALID_SESSION = "invalid_session"
    #: *Some* client joined a session. Possibly after creating it.
    SESSION_JOIN = "session_join"
    #: *Some* client left a session. Possibly while joining a different session.
    SESSION_LEAVE = "session_leave"
    #: Session ended. Either someone won or all other players left the session.
    SESSION_END = "session_end"
