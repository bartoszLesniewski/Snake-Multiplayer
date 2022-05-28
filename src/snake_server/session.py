from __future__ import annotations

import asyncio
import datetime
import itertools
import logging
import random
from collections import defaultdict, deque
from collections.abc import Collection, Generator
from typing import TYPE_CHECKING, Any

from .enums import Direction

if TYPE_CHECKING:
    from .app import App
    from .connection import Connection

log = logging.getLogger(__name__)


class SessionPlayer:
    def __init__(self, conn: Connection, name: str) -> None:
        self.conn = conn
        self.name = name
        self.chunks: deque[tuple[int, int]] = deque()
        self.direction = Direction.UP

    @property
    def head(self) -> tuple[int, int]:
        return self.chunks[0]

    @property
    def tail(self) -> list[tuple[int, int]]:
        if not self.chunks:
            return []
        head, *tail = self.chunks
        return tail

    @property
    def key(self) -> str:
        return self.conn.key

    @property
    def session(self) -> str:
        return self.conn.session

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "name": self.name,
            "chunks": [list(chunk) for chunk in self.chunks],
            "direction": self.direction.value,
        }

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, self.__class__):
            return NotImplemented
        return self.conn is other.conn

    def move(self) -> None:
        head_x, head_y = self.head
        offset_x, offset_y = self.direction.offset
        self.chunks.appendleft((head_x + offset_x, head_y + offset_y))

        for apple_pos in self.session.apples:
            if apple_pos == self.head:
                self.session.apples.remove(apple_pos)
                break
        else:
            self.chunks.pop()


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
        #: list of leaderboard places in reverse order (last place is first entry)
        self.leaderboard: list[list[SessionPlayer]] = []
        #: list of deaths that happened at current tick (used for accurate leaderboard)
        self.current_deaths: list[SessionPlayer] = []
        self.apples: set[tuple[int, int]] = set()

        self.running = False
        self.task: asyncio.Task | None = None
        self.tick = 0
        #: this might be a time in the past or future
        self.last_tick_time = datetime.datetime.min

    def is_name_taken(self, name: str) -> bool:
        return any(player.name == name for player in self.players.values())

    async def start(self) -> None:
        self.running = True
        self.generate_player_chunks()
        await asyncio.gather(
            *(
                player.conn.send_session_start(self)
                for player in self.players.values()
            )
        )
        self.task = asyncio.create_task(self.run())
        self.task.add_done_callback(self._task_error_handler)

    def stop(self) -> None:
        if self.task is not None:
            self.task.cancel()
        self.running = False
        for player in self.players.values():
            if player.conn.session is self:
                player.conn.session = None

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
                if player.conn.session is self:
                    player.conn.session = None
                asyncio.create_task(player.conn.close())
            asyncio.create_task(self.app.remove_session(self))

    def generate_player_chunks(self) -> None:
        distance = self.app.grid_width / (len(self.alive_players) + 1)
        y_center = self.app.grid_height // 2
        chunk_amount = self.app.initial_chunk_amount
        y_start = y_center - (chunk_amount // 2)
        y_stop = y_center + (chunk_amount // 2) + (chunk_amount % 2)

        for idx, player in enumerate(self.alive_players.values(), start=1):
            x = int(distance * idx)
            for y in range(y_start, y_stop):
                player.chunks.append((x, y))

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
            "apples": [list(apple_pos) for apple_pos in self.apples],
            "alive_players": [
                player.to_dict() for player in self.alive_players.values()
            ],
        }

    async def run(self) -> None:
        self.last_tick_time = datetime.datetime.now(datetime.timezone.utc)
        while len(self.alive_players) > 1:
            self.update_leaderboard()
            self.tick += 1

            if self.update_positions():
                self.handle_wall_deaths()
                self.handle_tail_self_cutting()
                self.handle_collision_deaths()

            self.generate_apples()

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

        await self.finish_game()

    async def finish_game(self) -> None:
        self.update_leaderboard()
        if self.alive_players:
            # this loop should always only have a single iteration
            for player in self.alive_players.values():
                self.current_deaths.append(player)
            self.update_leaderboard()

        leaderboard_data = [
            [p.to_dict() for p in place] for place in reversed(self.leaderboard)
        ]
        await asyncio.gather(
            *(
                player.conn.send_session_end(self, leaderboard_data)
                for player in self.players.values()
            )
        )

        await self.app.remove_session(self)

    def update_leaderboard(self) -> None:
        if not self.current_deaths:
            return
        keyfunc = lambda p: len(p.chunks)
        self.current_deaths.sort(key=keyfunc)
        for _, place in itertools.groupby(self.current_deaths, key=keyfunc):
            self.leaderboard.append(list(place))
        self.current_deaths.clear()

    def update_positions(self) -> bool:
        if self.tick % self.app.game_speed:
            return False

        for player in self.alive_players.values():
            player.move()

        return True

    def handle_wall_deaths(self) -> None:
        to_remove: list[str] = []
        for player in self.alive_players.values():
            x, y = player.head
            if x < 0 or x >= self.app.grid_width or y < 0 or y >= self.app.grid_height:
                to_remove.append(player.key)
        for key in to_remove:
            self.current_deaths.append(self.alive_players.pop(key))

    def handle_tail_self_cutting(self) -> None:
        """Handle a collision with your own tail by cutting it in that spot."""
        for player in self.alive_players.values():
            try:
                idx = player.chunks.index(player.head, 1)
            except ValueError:
                pass
            else:
                for _ in range(len(player.chunks) - idx):
                    player.chunks.pop()

    def handle_collision_deaths(self) -> None:
        self.handle_tail_collisions()
        self.handle_head_overlap_collisions()
        self.handle_head_on_collisions()

    def handle_tail_collisions(self) -> None:
        """
        Handle 'tail collisions'.

        Collision description:
            Player 1's head overlaps player 2's tail or they both overlap
            each other's tails.

        Examples:
            1. Player 1's head overlaps player 2's tail.
                - Before collision:
                    --->
                      ^
                      |

                - After collision:
                     -^->
                      |

            2. Player 1's head overlaps player 2's tail
               *and* player 2's head overlaps player 1's tail.
                - Before collision:
                      |
                      |
                    +>|
                    |<+
                    |
                    |

                - After collision 2:
                      |
                    +->
                    <-+
                    |

        Condition:
            p1.head in p2.tail AND (p1, p2) are not head overlap or head-on colliding

        Result:
            Death of the player whose head is in other player's tail.
            If both of the heads are in each other's tails, choose randomly.
        """
        deaths: set[str] = set()
        for p1, p2 in itertools.combinations(self.alive_players.values(), 2):
            if p1.key in deaths or p2.key in deaths:
                continue
            if (
                # head overlap collision
                p1.head != p2.head
                # head-on collision
                and (p1.chunks[0] != p2.chunks[1] and p2.chunks[0] != p1.chunks[1])
            ):
                potential_losers = []
                if p1.head in p2.chunks:
                    potential_losers.append(p1)
                if p2.head in p1.chunks:
                    potential_losers.append(p2)
                deaths.update(choose_losers(potential_losers))

        for key in deaths:
            self.current_deaths.append(self.alive_players.pop(key))

    def handle_head_overlap_collisions(self) -> None:
        """
        Handle 'head overlap collisions'.

        Collision description:
            Heads overlap.

        Example:
            - Before collision:
                ---> <---

            - After collision:
                 ---X---

        Condition:
            p1.head == p2.head

        Result:
            Death of the shorter player. For players of same length, choose randomly.
        """
        overlapping_heads: defaultdict[
            tuple[int, int], list[SessionPlayer]
        ] = defaultdict(list)
        for player in self.alive_players.values():
            overlapping_heads[player.head].append(player)

        for players in overlapping_heads.values():
            if len(players) > 1:
                for key in choose_losers(players):
                    self.current_deaths.append(self.alive_players.pop(key))

    def handle_head_on_collisions(self) -> None:
        """
        Handle 'head-on collisions'.

        Collision description:
            Heads overlap with the first tail element of their opponent.
            This can only happen when two players drove at each other
            from opposite directions.

        Example:
            - Before collision:
                ---><---

            - After collision:
                ---<>---

        Condition:
            p1.head == p2.chunks[1] AND p2.head == p1.chunks[1]

        Result:
            Death of the shorter player. For players of same length, choose randomly.
        """
        deaths: set[str] = set()
        for p1, p2 in itertools.combinations(self.alive_players.values(), 2):
            if p1.key in deaths or p2.key in deaths:
                continue
            if p1.chunks[0] == p2.chunks[1] and p2.chunks[0] == p1.chunks[1]:
                deaths.update(choose_losers((p1, p2)))

        for key in deaths:
            self.current_deaths.append(self.alive_players.pop(key))

    def generate_apples(self) -> None:
        # for now, there can only be one apple in the game
        if self.apples:
            return

        taken_positions = set()
        for player in self.alive_players.values():
            taken_positions.update(player.chunks)
        taken_positions.update(self.apples)

        while True:
            apple_pos = (
                random.randrange(self.app.grid_width),
                random.randrange(self.app.grid_height),
            )
            if apple_pos not in taken_positions:
                break

        self.apples.add(apple_pos)

    async def connect(self, connection: Connection, name: str) -> None:
        if self.running:
            raise RuntimeError("Can't connect while the game is running.")
        player = SessionPlayer(connection, name)
        self.players[player.key] = player
        self.alive_players[player.key] = player
        await asyncio.gather(
            *(
                player.conn.send_session_join(self, player)
                for player in self.players.values()
            )
        )

    async def disconnect(self, connection: Connection) -> None:
        if self.running:
            await self._disconnect_from_running(connection)
        else:
            await self._disconnect_from_not_running(connection)

    async def _disconnect_from_running(self, connection: Connection) -> None:
        try:
            player = self.alive_players.pop(connection.key)
        except KeyError:
            if connection.key in self.players:
                log.warning(
                    "disconnect() called for connection (%s) that is no longer"
                    " in the session.",
                    connection.key,
                )
                return
            else:
                # tried to disconnect a player that is not part of the session
                raise

        self.current_deaths.append(player)

        if self.alive_players and self.owner == player:
            self.owner = next(iter(self.alive_players.values()))

        await asyncio.gather(
            *(
                player.conn.send_session_leave(self, connection.key)
                for player in self.players.values()
            )
        )

        if len(self.alive_players) <= 1:
            # make sure we don't give back control to the caller
            # before we send session_end message
            await self.task

    async def _disconnect_from_not_running(self, connection: Connection) -> None:
        del self.players[connection.key]
        player = self.alive_players.pop(connection.key)

        if not self.players:
            await self.app.remove_session(self)
        elif self.owner == player:
            self.owner = next(iter(self.players.values()))

        await asyncio.gather(
            *(
                player.conn.send_session_leave(self, connection.key)
                for player in self.players.values()
            )
        )

        # we deleted connection from self.players above already
        # so we need to make sure the message is sent to it as well
        await connection.send_session_leave(self, connection.key)


def choose_losers(players: Collection[SessionPlayer]) -> Generator[str, None, None]:
    if not players:
        return

    m = max(len(p.chunks) for p in players)
    winner = random.choice([p for p in players if len(p.chunks) == m])
    for player in players:
        if player != winner:
            yield player.key
