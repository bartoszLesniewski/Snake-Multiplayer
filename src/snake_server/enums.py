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

    #: *Some* client joined a session. Possibly after creating it.
    SESSION_JOIN = "session_join"
    #: *Some* client left a session. Possibly while joining a different session.
    SESSION_LEAVE = "session_leave"
    #: Session started.
    SESSION_START = "session_start"
    #: Session ended. Either someone won or all other players left the session.
    SESSION_END = "session_end"
    #: A message with current state of session's world. This is sent at tick rate.
    SESSION_STATE_UPDATE = "session_state_update"


class Direction(enum.Enum):
    UP = 1
    DOWN = 2
    RIGHT = 3
    LEFT = 4

    @property
    def offset(self) -> tuple[int, int]:
        match self:
            case Direction.UP:
                return (0, -1)
            case Direction.DOWN:
                return (0, 1)
            case Direction.RIGHT:
                return (1, 0)
            case Direction.LEFT:
                return (-1, 0)

    @property
    def opposite(self) -> Direction:
        match self:
            case Direction.UP:
                return Direction.DOWN
            case Direction.DOWN:
                return Direction.UP
            case Direction.RIGHT:
                return Direction.LEFT
            case Direction.LEFT:
                return Direction.RIGHT
