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

            if not self.check_game_over():
                self.update_screen()

    def update_screen(self):
        # self.screen.fill((0, 0, 0))
        self.screen.blit(self.background, (0, 0))
        # screen.blit(snake.surface, snake.rect)
        self.snake.draw(self.screen)
        self.apple.draw(self.screen)
        self.snake.change_direction(pygame.key.get_pressed())
        self.snake.move(self.check_collision())
        print("Apple position: " + str(self.apple.rect.x) + " " + str(self.apple.rect.y))
        pygame.display.update()
        self.fps.tick(FPS)

    def check_collision(self):
        if self.snake.head.rect.colliderect(self.apple.rect):
            self.apple = Apple()
            return True

        return False

    def check_game_over(self):
        if self.snake.head.rect.x < 0 or self.snake.head.rect.x > WIDTH \
                or self.snake.head.rect.y < 0 or self.snake.head.rect.y > HEIGHT:
            self.screen.blit(self.background, (0, 0))
            font = pygame.font.SysFont("Arial", 120)
            surface = font.render("GAME OVER", True, (255, 255, 255))
            rect = surface.get_rect(center=(WIDTH/2, HEIGHT/2))
            self.screen.blit(surface, rect)
            pygame.display.update()

            return True

        return False


