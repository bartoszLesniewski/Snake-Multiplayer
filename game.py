import sys
import pygame
import pygame_menu
from pygame_menu import Theme

from apple import Apple
from connection import Connection
from messages import Message
from player import Player
from constans import *


class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Snake Multiplayer")
        self.background = pygame.image.load("img/background.jpg")

        self.player = None
        self.connection = Connection()
        self.host = None
        self.opponents = []
        self.apple = None
        self.fps = pygame.time.Clock()

    def menu(self):
        menu = self.set_menu_parameters(60, "Main menu")
        menu.add.button("New game", self.menu_with_input, "NEW_GAME",  background_color=GREEN)
        menu.add.button("Join game", self.menu_with_input, "JOIN_GAME", background_color=GREEN)
        menu.add.button("Exit", pygame_menu.events.EXIT, background_color=GREEN)
        menu.mainloop(self.screen)

    @staticmethod
    def set_menu_parameters(font_size, title):
        font = pygame_menu.font.FONT_OPEN_SANS_BOLD
        my_theme = Theme(title_font=font, widget_font=font, widget_font_size=font_size, widget_margin=(0, 30),
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
        self.update_menu()

        menu = self.set_menu_parameters(50, "Main menu")
        menu.add.label("Enter your nickname: ")
        player_input = menu.add.text_input("", default="Player", maxchar=10)
        code = None

        if choice == "JOIN_GAME":
            menu.add.label("Enter the code: ")
            code = menu.add.text_input("", default="code...", maxchar=10)

        menu.add.button("Confirm", self.lobby, player_input, choice, code, background_color=GREEN)
        menu.mainloop(self.screen)

    def update_menu(self):
        self.screen.blit(self.background, (0, 0))
        pygame.display.update()

    def lobby(self, player_input, choice, code):
        player_key = self.connection.connect()
        self.player = Player(player_input.get_value(), player_key)

        if choice == "NEW_GAME":
            self.connection.create_session(self.player.name)
            self.host = self.player
        elif choice == "JOIN_GAME":
            msg_data = self.connection.join_session(self.player.name, code.get_value())
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

            self.update_lobby()

    def update_lobby(self):
        self.screen.blit(self.background, (0, 0))
        menu = self.set_menu_parameters(30, "Lobby")
        menu.add.label("Waiting players:")
        info = " (you)"
        info += " (host)" if self.player == self.host else ""
        menu.add.label("- " + self.player.name + info)

        for opponent in self.opponents:
            info = " (host)" if opponent == self.host else ""
            menu.add.label("- " + opponent.name + info)

        if self.player == self.host:
            menu.add.label("Your lobby code: " + self.connection.session_code)
            menu.add.label("Pass it to your friends so they can join the game!")
            menu.add.button("Start game", self.start, background_color=GREEN)

        else:
            menu.add.label("Wait for the host to start a game...")

        events = pygame.event.get()
        for event in events:
            if event.type == pygame.QUIT:
                exit()

        if menu.is_enabled():
            menu.update(events)
            menu.draw(self.screen)

        pygame.display.update()

    def add_opponents(self, players):
        print(str(players))
        for opponent in players:
            if opponent["name"] != self.player.name:
                self.opponents.append(Player(opponent["name"], opponent["key"]))
            print(str(opponent["name"]) + " " + str(opponent["key"]))

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
                # result = self.connection.check_for_message()
                # print(result)

                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        pygame.quit()
                        sys.exit()

                # if not self.check_game_over():
                self.update_screen()
        else:
            self.play()

    def update_screen(self):
        # self.screen.fill((0, 0, 0))
        self.screen.blit(self.background, (0, 0))
        # screen.blit(snake.surface, snake.rect)

        self.player.snake.draw(self.screen)

        for opponent in self.opponents:
            opponent.snake.draw(self.screen)

        self.apple.draw(self.screen)

        # self.player.snake.change_direction(pygame.key.get_pressed())

        # self.player.snake.move(self.check_collision())

        # print(self.snake.head.rect.x, self.snake.head.rect.y)
        # print("Apple position: " + str(self.apple.rect.x) + " " + str(self.apple.rect.y))
        pygame.display.update()
        self.fps.tick(FPS)

    def update_game_state(self, data):
        self.apple = Apple(data["apples"][0])
        alive_players = data["alive_players"]
        is_player_alive = False

        for alive_player in alive_players:
            if alive_player["key"] == self.player.key:
                is_player_alive = True
                self.player.snake.update_segments(alive_player["chunks"])

        if not is_player_alive:
            self.show_game_over_screen()

        else:
            alive_opponents = []
            for alive_player in alive_players:
                alive_opponents.append(Player(alive_player["name"], alive_player["key"]))
                alive_opponents[-1].snake.update_segments(alive_player["chunks"])

            self.opponents = alive_opponents

    def check_collision(self):
        if self.player.snake.head.rect.colliderect(self.apple.rect):
            self.apple = Apple()
            return True

        for cnt, segment in enumerate(self.player.snake.segments):
            if segment != self.player.snake.head and self.player.snake.head.rect.colliderect(segment.rect):
                self.player.snake.segments = [self.player.snake.segments[i] for i in range(cnt)]
                return False

        return False

    def check_game_over(self):
        result = False
        if self.player.snake.head.rect.x < 0 or self.player.snake.head.rect.x + SEGMENT_SIZE > WIDTH \
                or self.player.snake.head.rect.y < 0 or self.player.snake.head.rect.y + SEGMENT_SIZE > HEIGHT:
            result = True

        # game over when collision with tail
        # for segment in self.snake.segments:
        #    if segment != self.snake.head and self.snake.head.rect.colliderect(segment.rect):
        #        result = True
        #       break

        if result:
            self.show_game_over_screen()

        return result

    def show_game_over_screen(self):
        self.screen.blit(self.background, (0, 0))
        font = pygame.font.SysFont("Arial", 120)
        surface = font.render("GAME OVER", True, WHITE)
        rect = surface.get_rect(center=(WIDTH / 2, HEIGHT / 2))
        self.screen.blit(surface, rect)
        pygame.display.update()

