from enum import Enum


class Message(Enum):
    # messages send to server
    CREATE_SESSION = "create_session"
    JOIN_SESSION = "join"
    START_SESSION = "start_session"

    # messages receive from server
    SESSION_JOIN = "session_join"
    SESSION_LEAVE = "session_leave"
    SESSION_START = "session_start"
    SESSION_END = "session_end"
