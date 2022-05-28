from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Mapping, MutableMapping
from typing import TYPE_CHECKING, Any

from .enums import Direction, MsgType

if TYPE_CHECKING:
    from .app import App
    from .session import Session, SessionPlayer

_log = logging.getLogger(__name__)


class ConnectionLoggerAdapter(logging.LoggerAdapter):
    extra: Mapping[str, Any]

    def process(
        self, msg: Any, kwargs: MutableMapping[str, Any]
    ) -> tuple[Any, MutableMapping[str, Any]]:
        return f"(Connection {self.extra['connection_key']}) {msg}", kwargs


class Connection:
    def __init__(
        self, app: App, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        self.app = app
        self.reader = reader
        self.writer = writer
        self.host, self.port = writer.transport.get_extra_info("peername")
        self.session: Session | None = None
        self.log = ConnectionLoggerAdapter(_log, {"connection_key": self.key})

    @property
    def key(self) -> str:
        return f"{self.host}:{self.port}"

    async def run(self) -> None:
        while not self.reader.at_eof():
            try:
                payload = (await self.reader.readuntil()).decode()
            except asyncio.IncompleteReadError:
                # reached EOF - this is a clean close by the client
                await self.on_socket_close()
                return
            except OSError as exc:
                # connection error occurred - client has been disconnected abruptly
                await self.on_socket_close(exc)
                return

            try:
                message = json.loads(payload)
            except json.JSONDecodeError as exc:
                self.log.warning(
                    "Received a malformed JSON payload from the client: %s", exc
                )
                break
            if not isinstance(message, dict):
                self.log.warning(
                    "Received a JSON payload that wasn't a dictionary from the client."
                )
                break

            try:
                msg_type = message["type"]
                data = message["data"]
            except KeyError as exc:
                self.log.warning(
                    "Received a message with a missing %r key, disconnecting...",
                    exc.args[0],
                )
                break
            try:
                handler_func = getattr(self, f"handle_{msg_type}")
            except AttributeError:
                self.log.warning(
                    "Received a message of invalid type %r, disconnecting...",
                    msg_type,
                )
                break

            try:
                await handler_func(data)
            except KeyError as exc:
                self.log.warning(
                    "Message of type %r requires a %r key but it's missing,"
                    " disconnecting...",
                    msg_type,
                    exc.args[0],
                )
                # this break is necessary to skip the else clause
                break
        else:
            # reached EOF - this is a clean close by the client
            await self.on_socket_close()
            return

        # breaked out of the loop, server is the one that needs to close the connection
        await self.close()

    async def on_socket_close(self, exc: OSError | None = None) -> None:
        if exc is None:
            self.log.info("Connection closed cleanly.")
        else:
            self.log.warning("Connection closed abruptly. Reason: %s", str(exc))

        await self.close(closed_by_client=True)

    async def close(self, *, closed_by_client: bool = False) -> None:
        if self.session is not None:
            await self.session.disconnect(self)
        self.writer.close()
        try:
            await self.writer.wait_closed()
        except OSError:
            # This is the exact same exception that we handle in run(),
            # we don't need to handle it here.
            pass
        self.app.connections.pop(self.key, None)
        if not closed_by_client:
            self.log.info("Connection closed by the server.")

    async def send_message(self, msg_type: MsgType, data: dict[str, Any]) -> None:
        serialized = json.dumps(
            {"type": msg_type.value, "data": data}, separators=(",", ":")
        )
        self.writer.write(f"{serialized}\n".encode())
        await self.writer.drain()

    async def handle_join(self, data: dict[str, Any]) -> None:
        code = data["code"]
        player_name = data["player_name"]
        try:
            session = self.app.sessions[code]
        except KeyError:
            await self.send_message(MsgType.INVALID_SESSION, {"exists": False})
            return
        if session.running:
            await self.send_message(MsgType.INVALID_SESSION, {"exists": True})
            return

        previous_session = self.session
        if previous_session is session or self.key in session.players:
            self.log.warning("Client seems to already be in this session.")
        if previous_session is not None and previous_session is not session:
            await previous_session.disconnect(self)

        if session.is_name_taken(player_name):
            await self.send_message(MsgType.PLAYER_NAME_ALREADY_TAKEN, {})
            return

        self.session = session
        await self.session.connect(self, player_name)

    async def handle_create_session(self, data: dict[str, Any]) -> None:
        player_name = data["player_name"]
        self.session = await self.app.create_session(self, player_name)
        self.log.info("Created and joined a session with code %r", self.session.code)

    async def handle_start_session(self, data: dict[str, Any]) -> None:
        if self.session is None:
            await self.send_message(MsgType.NOT_IN_SESSION, {})
            return

        if self.session.running:
            await self.send_message(MsgType.INVALID_SESSION, {"exists": True})
            return

        if self.session.owner.conn is not self:
            await self.send_message(MsgType.NOT_SESSION_OWNER, {})
            return

        await self.session.start()
        self.log.info("Started a session with code %r", self.session.code)

    async def handle_input(self, data: dict[str, Any]) -> None:
        direction_value = data["new_direction"]
        if self.session is None:
            await self.send_message(MsgType.NOT_IN_SESSION, {})
            return
        if not self.session.running:
            await self.send_message(MsgType.INVALID_SESSION, {"exists": True})
            return

        try:
            new_direction = Direction(direction_value)
        except ValueError:
            self.log.warning(
                "Received a message with invalid value of 'new_direction' key."
            )
            await self.close()
            return

        try:
            player = self.session.alive_players[self.key]
        except KeyError:
            self.log.warning(
                "Received an input message from a player that is not alive."
            )
            # this is unnecessary traffic but it's harmless so let's just ignore it
            return

        if new_direction in (player.direction, player.direction.opposite):
            return
        player.direction = new_direction
        self.log.info("Updated player's direction to %s.", new_direction.name)

    async def send_session_join(self, session: Session, player: SessionPlayer) -> None:
        payload: dict[str, Any] = {
            "code": session.code,
            "player": player.to_dict(),
            "owner_key": session.owner.key,
        }
        if player.key == self.key:
            self.log.info("Joined a session with code %r", session.code)
            payload["players"] = [
                player.to_dict() for player in session.players.values()
            ]
        await self.send_message(
            MsgType.SESSION_JOIN,
            payload,
        )

    async def send_session_leave(self, session: Session, key: str) -> None:
        if key == self.key:
            self.log.info("Left a session with code %r", session.code)
            self.session = None
        if not self.writer.is_closing():
            await self.send_message(
                MsgType.SESSION_LEAVE,
                {"code": session.code, "key": key, "owner_key": session.owner.key},
            )

    async def send_session_end(
        self, session: Session, leaderboard_data: list[list[dict[str, Any]]]
    ) -> None:
        self.session = None
        if not self.writer.is_closing():
            await self.send_message(
                MsgType.SESSION_END,
                {"code": session.code, "leaderboard": leaderboard_data},
            )
            await self.close()

    async def send_session_start(self, session: Session) -> None:
        await self.send_message(
            MsgType.SESSION_START,
            {"code": session.code, "state": session.get_state()},
        )

    async def send_session_state_update(
        self, session: Session, state: dict[str, Any]
    ) -> None:
        if not self.writer.is_closing():
            await self.send_message(MsgType.SESSION_STATE_UPDATE, state)
