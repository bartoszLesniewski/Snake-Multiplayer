import pygame


class Segment(pygame.sprite.Sprite):
    def __init__(self, x_position, y_position):
        super().__init__()
        self.surface = pygame.Surface((20, 20))
        self.surface.fill((0, 100, 0))
        self.rect = self.surface.get_rect(x=x_position, y=y_position)
