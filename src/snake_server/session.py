from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .app import App
    from .connection import Connection

log = logging.getLogger(__name__)


class Session:
    def __init__(self, app: App, owner: Connection, code: str) -> None:
        self.app = app
        self.owner = owner
        self.code = code
        self.running = False
        self.connections: dict[str, Connection] = {}
        self.winner: Connection | None = None
        self.task: asyncio.Task | None = None

    def stop(self) -> None:
        if self.task is not None:
            self.task.cancel()
        self.running = False

    async def connect(self, connection: Connection) -> None:
        self.connections[connection.key] = connection
        await asyncio.gather(
            *(
                conn.send_session_join(self, connection.key)
                for conn in self.connections.values()
                if conn != connection.key
            )
        )