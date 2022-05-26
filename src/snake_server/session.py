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

    async def start(self) -> None:
        self.running = True
        await asyncio.gather(
            *(conn.send_session_start(self) for conn in self.connections.values())
        )
        self.task = asyncio.create_task(self.run())
        self.task.add_done_callback(self._task_error_handler)

    def _task_error_handler(self, task: asyncio.Task) -> None:
        try:
            task.result()
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            log.error(
                "Unexpected error occurred while running session with code %r.",
                exc_info=exc,
            )

            self.running = False
            for conn in self.connections.values():
                conn.session = None
                asyncio.create_task(conn.close())

    async def run(self) -> None:
        # TODO: implement game loop along with proper syncing
        ...

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

    async def disconnect(self, connection: Connection) -> None:
        self.connections.pop(connection.key, None)
        if self.connections:
            if self.owner is connection:
                self.owner = next(iter(self.connections))
            await asyncio.gather(
                *(
                    conn.send_session_leave(self, connection.key)
                    for conn in self.connections.values()
                )
            )
        else:
            self.stop()
            await self.app.remove_session(self)
            log.info("Session with code %r ended.", self.code)

        await connection.send_session_leave(self, connection.key)
        if self.running and len(self.connections) == 1:
            self.winner = self.owner
            await self.owner.send_session_end(self)
            await self.app.remove_session(self)
            log.info("Session with code %r ended.", self.code)
