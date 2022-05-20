import sys
import pygame

from Apple import Apple
from Snake import Snake
from constans import *


class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Snake Multiplayer")
        self.background = pygame.image.load("img/background.jpg")

        self.snake = Snake(WIDTH / 2, HEIGHT / 2)
        self.apple = Apple()
        self.fps = pygame.time.Clock()

    def play(self):
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()

            self.update_screen()

    def update_screen(self):
        # self.screen.fill((0, 0, 0))
        self.screen.blit(self.background, (0, 0))
        # screen.blit(snake.surface, snake.rect)
        self.snake.draw(self.screen)
        self.apple.draw(self.screen)
        self.snake.change_direction(pygame.key.get_pressed())
        self.snake.move()
        pygame.display.update()
        self.fps.tick(FPS)
