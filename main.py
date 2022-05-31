import sys
import logging
from game import Game

logging.basicConfig(format='%(asctime)s - %(message)s', datefmt='%d-%b-%y %H:%M:%S')


def main():
    if len(sys.argv) < 2:
        logging.error("Server IP not specified!")
        exit(-1)

    game = Game(sys.argv[1])
    #game.show_menu()
    game.show_end_screen()


if __name__ == "__main__":
    main()
