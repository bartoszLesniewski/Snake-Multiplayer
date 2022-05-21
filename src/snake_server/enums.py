from __future__ import annotations

import enum


class MsgType(enum.Enum):
    """Represents types of messages that can be sent by the server."""

    #: *Some* client joined a session. Possibly after creating it.
    SESSION_JOIN = "session_join"
