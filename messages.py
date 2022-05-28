from enum import Enum


class Message(Enum):
    CREATE_SESSION = "create_session"
    JOIN_SESSION = "join"
    START_SESSION = "start_session"
