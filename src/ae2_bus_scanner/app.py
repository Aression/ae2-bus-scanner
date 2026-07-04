import multiprocessing

from .gui.main_window import launch


def main():
    launch()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
