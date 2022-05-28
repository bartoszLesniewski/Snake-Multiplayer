import pygame

from direction import Direction
from segment import Segment
from constans import *


class Snake (pygame.sprite.Sprite):
    def __init__(self, x_start, y_start):
        super().__init__()
        self.head = self.create_head(x_start, y_start)
        # self.segments = pygame.sprite.Group()
        self.segments = []
        self.segments.append(self.head)
        self.direction = Direction.UP
        # self.test_segments()

    def test_segments(self):
        self.segments.append(Segment(400, 320))
        self.segments.append(Segment(400, 340))
        self.segments.append(Segment(400, 360))

    def update_segments(self, chunks):
        self.segments.clear()
        for segment in chunks:
            self.segments.append(Segment(segment[0] * SEGMENT_SIZE, segment[1] * SEGMENT_SIZE))

        self.head = self.create_head(chunks[0][0] * SEGMENT_SIZE, chunks[0][1] * SEGMENT_SIZE)
        self.segments[0] = self.head

        # self.direction = direction

    def move(self, new_segment):
        # print("Start number of segments: " + str(len(self.segments)))
        new_head = self.create_head(self.head.rect.x, self.head.rect.y)
        if self.direction == Direction.UP:
            new_head.rect.move_ip(0, -SEGMENT_SIZE)
        elif self.direction == Direction.DOWN:
            new_head.rect.move_ip(0, SEGMENT_SIZE)
        elif self.direction == Direction.RIGHT:
            new_head.rect.move_ip(SEGMENT_SIZE, 0)
        elif self.direction == Direction.LEFT:
            new_head.rect.move_ip(-SEGMENT_SIZE, 0)

        self.segments[0] = Segment(self.segments[0].rect.x, self.segments[0].rect.y)
        self.segments.insert(0, new_head)
        self.head = new_head

        if not new_segment:
            self.segments.pop()

        # print("End number of segments: " + str(len(self.segments)))

    @staticmethod
    def create_head(x, y):
        head = Segment(x, y)
        head.surface.blit(pygame.image.load("img/head.png"), (0, 0))
        return head

    def draw(self, screen):
        # print("segments size: " + str(len(self.segments)))
        for segment in self.segments:
            screen.blit(segment.surface, segment.rect)
            # print(segment.rect.x, segment.rect.y)

    def change_direction(self, pressed_keys):
        if pressed_keys[pygame.K_UP] and self.direction != Direction.DOWN:
            self.direction = Direction.UP
        elif pressed_keys[pygame.K_DOWN] and self.direction != Direction.UP:
            self.direction = Direction.DOWN
        elif pressed_keys[pygame.K_RIGHT] and self.direction != Direction.LEFT:
            self.direction = Direction.RIGHT
        elif pressed_keys[pygame.K_LEFT] and self.direction != Direction.RIGHT:
            self.direction = Direction.LEFT

