import sys
from socket import socket

import pygame
import pygame_menu
from pygame_menu import Theme

from apple import Apple
from connection import Connection
from messages import Message
from player import Player
from constans import *


class Game:
    def __init__(self, server_address):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Snake Multiplayer")
        self.background = pygame.image.load("img/background.jpg")

        self.server_address = server_address
        self.host = None
        self.reset()

    def reset(self):
        self.player = None
        self.connection = Connection(self.server_address)
        self.opponents = []
        self.apple = None
        self.menu = None

    def show_menu(self):
        if self.menu is not None:
            self.menu.disable()
            self.reset()

        self.menu = self.set_menu_parameters(60, "Main menu")
        self.menu.add.button("New game", self.menu_with_input, "NEW_GAME",  background_color=GREEN)
        self.menu.add.button("Join game", self.menu_with_input, "JOIN_GAME", background_color=GREEN)
        self.menu.add.button("Exit", pygame_menu.events.EXIT, background_color=GREEN)
        self.menu.mainloop(self.screen)

    @staticmethod
    def set_menu_parameters(font_size, title, margin=(0, 30)):
        font = pygame_menu.font.FONT_OPEN_SANS_BOLD
        my_theme = Theme(title_font=font, widget_font=font, widget_font_size=font_size, widget_margin=margin,
                         title_font_color=WHITE, widget_font_color=WHITE,
                         title_background_color=GREEN,
                         selection_color=WHITE,
                         focus_background_color=GREEN,
                         background_color=pygame_menu.baseimage.BaseImage(
                             image_path="img/background.jpg",
                             drawing_mode=pygame_menu.baseimage.IMAGE_MODE_REPEAT_XY
                         ))
        menu = pygame_menu.Menu(title, 800, 600, theme=my_theme)

        return menu

    def menu_with_input(self, choice):
        self.menu.disable()
        # self.menu.clear()
        self.menu = self.set_menu_parameters(50, "Main menu")
        self.menu.add.label("Enter your nickname: ")
        player_input = self.menu.add.text_input("", default="Player", maxchar=10)
        code = None

        if choice == "JOIN_GAME":
            self.menu.add.label("Enter the code: ")
            code = self.menu.add.text_input("", default="code...", maxchar=10)

        self.menu.add.button("Confirm", self.lobby, player_input, choice, code, background_color=GREEN)
        # pygame.display.update()
        self.menu.mainloop(self.screen)

    def lobby(self, player_input, choice, code):
        # self.menu.disable()
        player_key = self.connection.connect()
        self.player = Player(player_input.get_value(), player_key)

        if choice == "NEW_GAME":
            self.connection.create_session(self.player.name)
            self.host = self.player
        elif choice == "JOIN_GAME":
            msg_data = self.connection.join_session(self.player.name, code.get_value())
            self.player.name = msg_data["player"]["name"]
            self.add_opponents(msg_data["players"])
            self.find_host(msg_data["owner_key"])

        while True:
            result = self.connection.check_for_message()
            if result is not None:
                if result[0] == Message.SESSION_JOIN:
                    self.add_opponents(result[1])
                elif result[0] == Message.SESSION_LEAVE:
                    self.remove_opponent(result[1]["key"])
                    self.find_host(result[1]["owner_key"])
                elif result[0] == Message.SESSION_START:
                    self.play()
                    break

            self.update_lobby()

    def update_lobby(self):
        self.menu = self.set_menu_parameters(30, "Lobby", (0, 10))
        self.menu.add.label("Waiting players:")
        info = " (you)"
        info += " (host)" if self.player == self.host else ""
        self.menu.add.label("- " + self.player.name + info)

        for i in range(min(3, len(self.opponents))):
            info = " (host)" if self.opponents[i] == self.host else ""
            self.menu.add.label("- " + self.opponents[i].name + info)

        if len(self.opponents) > 3:
            others = len(self.opponents) - 3
            self.menu.add.label("and " + str(others) + " others")

        if self.player == self.host:
            self.menu.add.label("Your lobby code: " + self.connection.session_code)
            self.menu.add.label("Pass it to your friends so they can join the game!")
            self.menu.add.button("Start game", self.start, background_color=GREEN)

        else:
            self.menu.add.label("Wait for the host to start a game...")

        events = pygame.event.get()
        for event in events:
            if event.type == pygame.QUIT:
                exit()

        if self.menu.is_enabled():
            self.menu.update(events)
            self.menu.draw(self.screen)

        pygame.display.update()

    def add_opponents(self, players):
        self.opponents.clear()
        for opponent in players:
            if opponent["name"] != self.player.name:
                self.opponents.append(Player(opponent["name"], opponent["key"]))

    def remove_opponent(self, key):
        for opponent in self.opponents:
            if opponent.key == key:
                self.opponents.remove(opponent)
                break

    def find_host(self, host_key):
        if self.player.key == host_key:
            self.host = self.player
        else:
            for opponent in self.opponents:
                if opponent.key == host_key:
                    self.host = opponent
                    break

    def start(self):
        self.connection.start_session(self.player.name, self.connection.session_code)
        self.play()

    def play(self):
        result = self.connection.check_for_message()
        if result is not None and result[0] == Message.SESSION_STATE_UPDATE:
            self.update_game_state(result[1])
            while True:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        pygame.quit()
                        sys.exit()

                # if not self.check_game_over():
                self.update_screen()

                result = self.connection.check_for_message()
                if result is not None:
                    if result[0] == Message.SESSION_STATE_UPDATE:
                        self.update_game_state(result[1])
                    elif result[0] == Message.SESSION_END:
                        self.show_end_screen(result[1]["leaderboard"])
                        break

        else:
            self.play()

    def update_screen(self):
        self.screen.blit(self.background, (0, 0))

        if self.player.is_alive:
            self.player.snake.draw(self.screen)

        for opponent in self.opponents:
            opponent.snake.draw(self.screen)

        self.apple.draw(self.screen)

        if self.player.is_alive:
            self.connection.send_direction_change(pygame.key.get_pressed(), self.player.snake.direction)

        pygame.display.update()

    def update_game_state(self, data):
        self.apple = Apple(data["apples"][0])
        alive_players = data["alive_players"]
        is_player_alive = False

        for alive_player in alive_players:
            if alive_player["key"] == self.player.key:
                is_player_alive = True
                self.player.snake.update_segments(alive_player["chunks"], alive_player["direction"])

        if not is_player_alive:
            self.player.is_alive = False

        else:
            alive_opponents = []
            for alive_player in alive_players:
                alive_opponents.append(Player(alive_player["name"], alive_player["key"]))
                alive_opponents[-1].snake.update_segments(alive_player["chunks"], alive_player["direction"])

            self.opponents = alive_opponents

    def show_game_over_screen(self):
        self.menu = self.set_menu_parameters(70, "The end")
        self.menu.add.label("GAME OVER")
        self.menu.mainloop(self.screen)

    def show_end_screen(self, leaderboard):
        self.menu = self.set_menu_parameters(20, "The end")
        self.menu.add.label(self.create_table(leaderboard), align=pygame_menu.locals.ALIGN_CENTER)
        self.menu.add.button("Go back to menu", self.show_menu, background_color=GREEN)
        # self.connection.socket = self.connection.socket.shutdown(socket.SHUT_RDWR)
        # self.connection.socket = self.connection.socket.close()
        self.menu.mainloop(self.screen)

    def create_table(self, leaderboard):
        headers = ["Rank", "Player name", "Points"]
        spaces = "                   "
        table = ""

        for header in headers:
            table += self.fill_word(header) + spaces

        table += "\n"

        for i, players in enumerate(leaderboard, start=1):
            for player in players:
                table += self.fill_word(str(i)) + spaces
                table += self.fill_word(player["name"]) + spaces + "          "
                table += self.fill_word(str(len(player["chunks"]))) + spaces
                table += "\n"

        return table

    @staticmethod
    def fill_word(word):
        if len(word) < 11:
            for _ in range(11 - len(word)):
                word += " "

        return word
