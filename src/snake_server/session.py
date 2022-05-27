from __future__ import annotations

import asyncio
import datetime
import logging
from collections import deque
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .app import App
    from .connection import Connection

log = logging.getLogger(__name__)


class SessionPlayer:
    def __init__(self, conn: Connection, name: str) -> None:
        self.conn = conn
        self.name = name
        self.alive = True
        self.chunks: deque[tuple[int, int]] = deque()

    @property
    def key(self) -> str:
        return self.conn.key

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "name": self.name,
            "chunks": [list(chunk) for chunk in self.chunks],
        }

    def __eq__(self, other: SessionPlayer) -> bool:
        return self.conn is other.conn


class Session:
    def __init__(
        self, *, app: App, owner: Connection, owner_name: str, code: str
    ) -> None:
        self.app = app
        self.owner = SessionPlayer(owner, owner_name)
        self.code = code

        #: stores all players that were ever in the running session,
        #: regardless of whether they're still connected
        self.players: dict[str, SessionPlayer] = {self.owner.key: self.owner}
        #: stores alive (and still connected) players
        self.alive_players: dict[str, SessionPlayer] = self.players.copy()
        #: list of deaths ordered by death time (most recent death is the last entry)
        self.dead_players: list[SessionPlayer] = []

        self.running = False
        self.task: asyncio.Task | None = None
        self.tick = 0
        #: this might be a time in the past or future
        self.last_tick_time = datetime.datetime.min

    def is_name_taken(self, name: str) -> bool:
        return any(player.name == name for player in self.players.values())

    async def start(self) -> None:
        self.running = True
        await asyncio.gather(
            *(
                player.conn.send_session_start(self)
                for player in self.alive_players.values()
            )
        )
        self.task = asyncio.create_task(self.run())
        self.task.add_done_callback(self._task_error_handler)

    def stop(self) -> None:
        if self.task is not None:
            self.task.cancel()
        self.running = False

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
            for player in self.players.values():
                player.conn.session = None
                asyncio.create_task(player.conn.close())

    def get_next_sleep_time(self) -> float:
        self.last_tick_time += self.app.tick_interval
        sleep_delta = self.last_tick_time - datetime.datetime.now(datetime.timezone.utc)
        ret = sleep_delta.total_seconds()
        if ret < 0:
            log.warning("Session %r is behind!", self.code)
        return ret

    def get_state(self) -> dict[str, Any]:
        return {
            "tick": self.tick,
            "alive_players": [
                player.to_dict() for player in self.alive_players.values()
            ],
        }

    async def run(self) -> None:
        # TODO: implement game loop along with proper syncing
        self.last_tick_time = datetime.datetime.now(datetime.timezone.utc)
        while True:
            self.tick += 1

            # broadcast the state update to all connections
            state = self.get_state()
            await asyncio.gather(
                *(
                    player.conn.send_session_state_update(self, state)
                    for player in self.players.values()
                )
            )

            # sleep until next tick
            await asyncio.sleep(self.get_next_sleep_time())

    async def connect(self, connection: Connection, name: str) -> None:
        player = SessionPlayer(connection, name)
        self.players[player.key] = player
        self.alive_players[player.key] = player
        await asyncio.gather(
            *(
                player.conn.send_session_join(self, player)
                for player in self.alive_players.values()
            )
        )

    async def disconnect(self, connection: Connection) -> None:
        if not self.running:
            del self.players[connection.key]

        try:
            player = self.alive_players.pop(connection.key)
        except KeyError:
            if self.running and connection.key in self.players:
                log.warning(
                    "disconnect() called for connection that is no longer"
                    " in the session."
                )
            else:
                # tried to disconnect a player that is not part of the session
                raise
        else:
            player.alive = False
            self.dead_players.append(player)

        if self.alive_players:
            if self.owner == player:
                self.owner = next(iter(self.alive_players.values()))
            await asyncio.gather(
                *(
                    player.conn.send_session_leave(self, connection.key)
                    for player in self.alive_players.values()
                )
            )
        else:
            self.stop()
            await self.app.remove_session(self)
            log.info("Session with code %r ended.", self.code)

        await connection.send_session_leave(self, connection.key)
        if self.running and len(self.alive_players) == 1:
            self.dead_players.append(self.owner)
            await self.owner.send_session_end(self)
            await self.app.remove_session(self)
            log.info("Session with code %r ended.", self.code)
